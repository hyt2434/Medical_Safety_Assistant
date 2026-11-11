"""Offline NLP regression cases; FakeCore is a test double, never runtime storage."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from uuid import UUID, uuid4

import httpx
import pytest

from module1_intake.nlp.dialogue import Chatbot
from module1_intake.nlp.models import Medication, Understanding, Intent
from module1_intake.nlp.providers import MockProvider, OllamaProvider, InferenceError, understand
from module1_intake.nlp.routing import detect
from module1_intake.nlp.validation import EvidenceError, validate_medication


class FakeCore:
    """Minimal repository spy. Real PostgreSQL assertions live in integration/test_nlp_v4."""
    def __init__(self):
        self.owner = uuid4()
        self.tables = {}
        self.keys = {}

    def put(self, table, **values):
        row = dict(id=uuid4(), user_id=self.owner, **values)
        self.tables.setdefault(table, {})[str(row['id'])] = row
        return deepcopy(row)

    def _owned(self, table, identity, **kw):
        row = self.tables.get(table, {}).get(str(identity))
        if not row or row['user_id'] != self.owner:
            raise PermissionError('Foreign/missing row')
        return deepcopy(row)

    def _one(self, query, params=()):
        if 'pg_try_advisory_lock' in query:
            return {'locked': True}
        if 'pg_advisory_unlock' in query:
            return {'unlocked': True}
        raise AssertionError(query)

    def _all(self, query, params=()):
        if 'FROM msa.conversation_messages' in query:
            rows = [r for r in self.tables.get('conversation_messages', {}).values()
                    if r['conversation_id'] == params[0] and r['user_id'] == params[1]
                    and r['role'] == 'ASSISTANT' and (r.get('metadata') or {}).get('workflow_id') == params[2]
                    and 'application_response' in (r.get('metadata') or {})]
            if len(params) > 3:
                rows = [r for r in rows if r['metadata'].get('action_request_key') == params[3]]
            return deepcopy(rows[-1:])
        assert 'ORDER BY version_no DESC LIMIT 1' in query
        rows = [r for r in self.tables.get('medication_entry_versions', {}).values()
                if r['item_id'] == params[0] and r['user_id'] == self.owner]
        return sorted(deepcopy(rows), key=lambda r: -r['version_no'])[:1]

    def digest(self, value):
        # Test-only digest; never substitute this encoding for pg-jsonb-text-v4.
        return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()

    def create_conversation(self):
        return self.put('conversation_sessions')

    def create_intake(self, conversation=None, **kw):
        self._owned('conversation_sessions', conversation)
        return self.put('intake_sessions', conversation_id=conversation)

    def create_workflow(self, conversation, workflow_type, *, intake=None, origin_message=None):
        assert workflow_type in {'MEDICATION_INTAKE', 'SAFETY_REQUEST', 'Q_AND_A', 'PATIENT_SUMMARY'}
        self._owned('conversation_sessions', conversation)
        return self.put('workflow_instances', conversation_id=conversation, workflow_type=workflow_type,
                        intake_session_id=intake, state='COLLECTING', revision=1,
                        context={'schema': 'workflow.v4', 'draft': None, 'pending_confirmation': None, 'pending_questions': []})

    def append_message(self, conversation, role, body, metadata=None):
        self._owned('conversation_sessions', conversation)
        return self.put('conversation_messages', conversation_id=conversation, role=role, text_content=body, metadata=metadata)

    def transition_workflow(self, workflow, state, *, expected_revision, context=None):
        old = self._owned('workflow_instances', workflow)
        assert old['state'] not in {'COMPLETED', 'CANCELLED', 'FAILED'}
        assert old['revision'] == expected_revision
        ctx = deepcopy(context)
        if state != 'AWAITING_CONFIRMATION':
            ctx['pending_confirmation'] = None
        old.update(state=state, revision=expected_revision + 1, context=ctx)
        self.tables['workflow_instances'][str(workflow)] = old
        return deepcopy(old)

    def record_input(self, intake, modality, original_bytes, **kw):
        assert modality == 'TEXT'
        self._owned('intake_sessions', intake)
        return self.put('intake_inputs', session_id=intake, modality=modality,
                        input_digest=hashlib.sha256(original_bytes).hexdigest(), **kw)

    def record_extraction(self, input_id, name, version, result, **kw):
        return self.put('intake_extractions', input_id=input_id, result=result, **kw)

    def create_item(self, extraction, ordinal, medication_fields, **kw):
        item = self.put('intake_items', extraction_id=extraction, ordinal=ordinal)
        return self.put('medication_entry_versions', item_id=item['id'], version_no=1,
                        medication_fields=medication_fields, content_digest=self.digest(medication_fields),
                        confirmed_at=None, confirmation_key=None, source_extraction_id=extraction)

    def correct_entry(self, entry, medication_fields, *, source_extraction=None):
        prior = self._owned('medication_entry_versions', entry)
        return self.put('medication_entry_versions', item_id=prior['item_id'], version_no=prior['version_no']+1,
                        supersedes_version_id=entry, medication_fields=medication_fields,
                        content_digest=self.digest(medication_fields), confirmed_at=None,
                        confirmation_key=None, source_extraction_id=source_extraction)

    def confirm_entry(self, entry, displayed_digest, request_key, *, explicit_confirmation):
        assert explicit_confirmation is True
        prior = self._owned('medication_entry_versions', entry)
        assert prior['content_digest'] == displayed_digest
        if request_key in self.keys:
            assert self.keys[request_key] == entry
            return prior
        self.keys[request_key] = entry
        prior.update(confirmed_at=datetime.now(timezone.utc), confirmation_key=request_key)
        self.tables['medication_entry_versions'][str(entry)] = prior
        return deepcopy(prior)


def scripted(*meds, ambiguous=False, intents=None):
    return Understanding(medications=list(meds), ambiguous=ambiguous, intents=intents or []).model_dump_json()


def conversation(provider=None):
    repo = FakeCore()
    bot = Chatbot(repo, provider or MockProvider())
    start = bot.start()
    return repo, bot, start


def send(bot, reply, text):
    return bot.send(reply.workflow_id, text, expected_revision=reply.revision)


def test_mock_slots_and_package_quantity():
    text = 'Tôi đang uống Panadol 500mg, dạng viên nén, mỗi sáng một viên, ngày 2 lần, trong 5 ngày; đang dùng B 10mg, 2 hộp x 10 vỉ x 10 viên'
    value = understand(MockProvider(), text, {})
    a, b = value.medications
    assert (a.name_raw, a.strength_raw, a.dose_raw, a.dosage_form_raw) == ('Panadol', '500mg', 'một viên', 'viên nén')
    assert a.administrations[0].timing_raw == 'mỗi sáng'
    assert a.frequency_raw == 'ngày 2 lần' and a.duration_raw == 'trong 5 ngày'
    assert b.quantity_raw == '2 hộp x 10 vỉ x 10 viên' and b.dose_raw is None


@pytest.mark.parametrize('patch', [
    {'name_raw': 'Invented'}, {'strength_raw': '250mg'}, {'dose_raw': '500mg'},
    {'dose_raw': '2 hộp'}, {'frequency_raw': '500mg'}, {'duration_raw': 'một viên'},
    {'uncertain_fields': ['product_id']}, {'negation_raw': 'Panadol'},
])
def test_unsupported_slots_rejected(patch):
    text = 'Panadol 500mg một viên 2 hộp'
    med = Medication(name_raw='Panadol', evidence_text=text, **{k:v for k,v in patch.items() if k != 'name_raw'})
    if 'name_raw' in patch:
        med.name_raw = patch['name_raw']
    with pytest.raises(EvidenceError):
        validate_medication(med, text)


def test_explicit_negation_uncertainty_cannot_be_dropped():
    text = 'Có lẽ không dùng Panadol 500mg'
    value = validate_medication(Medication(name_raw='Panadol', strength_raw='500mg', evidence_text=text), text)
    assert value.negation_raw == 'không dùng'
    assert value.uncertainty_raw == 'Có lẽ'
    assert 'name_raw' in value.uncertain_fields


def test_cross_drug_field_must_belong_to_own_evidence():
    with pytest.raises(EvidenceError):
        validate_medication(Medication(name_raw='A', strength_raw='250mg', evidence_text='A 500mg'), 'A 500mg; B 250mg')


def test_mass_dose_requires_explicit_role_and_quantity_labels_are_enforced():
    text = 'A, mỗi lần 500mg'
    assert validate_medication(Medication(name_raw='A', dose_raw='500mg', evidence_text=text), text).strength_raw is None
    with pytest.raises(EvidenceError):
        validate_medication(Medication(name_raw='A', strength_raw='500mg', evidence_text=text), text)
    with pytest.raises(EvidenceError):
        validate_medication(Medication(name_raw='A', dose_raw='30 viên', evidence_text='A, SL: 30 viên'), 'A, SL: 30 viên')


def test_evidence_cannot_hide_negation_or_overlap_drugs():
    with pytest.raises(EvidenceError):
        validate_medication(Medication(name_raw='A', evidence_text='A 500mg'), 'Không dùng A 500mg')
    overlapping = scripted(Medication(name_raw='A', evidence_text='A 500mg B 250mg'),
                           Medication(name_raw='B', evidence_text='B 250mg'))
    with pytest.raises(InferenceError):
        understand(MockProvider([overlapping, overlapping]), 'A 500mg B 250mg', {})


def test_retry_json_and_unsafe_fields_are_bounded():
    good = scripted(Medication(name_raw='A', evidence_text='A'))
    provider = MockProvider(['{"answer":"stop medication", "product_id":"x"}', 'not json', good])
    with pytest.raises(InferenceError):
        understand(provider, 'A', {}, attempts=2)
    assert provider.calls == 2
    assert understand(provider, 'A', {}).medications[0].name_raw == 'A'


def test_multi_intent_and_unknown():
    intents = detect('Tôi đang uống A, kiểm tra tương tác và nhắc tôi uống thuốc', Understanding())
    assert {Intent.ADD_MEDICATION, Intent.CHECK_INTERACTION, Intent.CREATE_REMINDER} <= set(intents)
    _, bot, r = conversation()
    assert send(bot, r, 'giúp tôi với').state == 'CLARIFYING'


def test_multiturn_missing_correction_confirmation_and_idempotency():
    repo, bot, r = conversation()
    r = send(bot, r, 'Tôi đang uống Panadol')
    assert r.state == 'CLARIFYING'
    r = send(bot, r, '500mg, dạng viên nén')
    assert r.state == 'AWAITING_CONFIRMATION'
    old = repo._owned('workflow_instances', r.workflow_id)['context']['entry_version_ids'][0]
    stale_revision = r.revision
    r = send(bot, r, 'sửa thuốc 1 thành Panadol 250mg')
    new = repo._owned('workflow_instances', r.workflow_id)['context']['entry_version_ids'][0]
    assert new != old
    assert repo._owned('medication_entry_versions', old)['medication_fields']['strength_raw'] == '500mg'
    with pytest.raises(ValueError):
        bot.confirm(r.workflow_id, expected_revision=stale_revision, request_key=uuid4(), explicit_confirmation=True)
    key = uuid4()
    done = bot.confirm(r.workflow_id, expected_revision=r.revision, request_key=key, explicit_confirmation=True)
    assert done.handoff.entries[0].medication.strength_raw == '250mg'
    assert done.handoff.entries[0].identity_status == 'NOT_ATTEMPTED'
    assert bot.confirm(r.workflow_id, expected_revision=r.revision, request_key=key, explicit_confirmation=True).handoff == done.handoff
    r = bot.revise(done.workflow_id)
    r = send(bot, r, 'sửa thuốc 1 thành Panadol 500mg')
    assert r.state == 'AWAITING_CONFIRMATION'
    assert repo._owned('medication_entry_versions', new)['confirmed_at'] is not None


def test_ambiguous_correction_never_updates_wrong_drug():
    repo, bot, r = conversation()
    r = send(bot, r, 'Tôi đang uống A 500mg; đang dùng B 250mg')
    rows_before = deepcopy(repo.tables['medication_entry_versions'])
    r = send(bot, r, 'sửa hàm lượng 100mg')
    assert 'số mấy' in r.text
    assert rows_before == repo.tables['medication_entry_versions']
    r = send(bot, r, 'sửa thuốc 2 thành B 100mg')
    assert len(repo.tables['medication_entry_versions']) == 3


def test_unknown_slots_stay_null_and_no_automatic_confirmation():
    repo, bot, r = conversation()
    r = send(bot, r, 'Tôi đang uống Panadol')
    r = send(bot, r, 'không rõ')
    assert r.state == 'AWAITING_CONFIRMATION'
    assert all(row['confirmed_at'] is None for row in repo.tables['medication_entry_versions'].values())
    r = send(bot, r, 'đúng rồi')
    assert r.handoff is None
    with pytest.raises(ValueError):
        bot.confirm(r.workflow_id, expected_revision=r.revision, request_key=uuid4(), explicit_confirmation=False)


def test_ambiguous_model_requires_clarification_even_with_slots():
    provider = MockProvider([scripted(Medication(name_raw='A', evidence_text='A'), ambiguous=True)])
    repo, bot, r = conversation(provider)
    r = send(bot, r, 'A')
    assert r.state == 'CLARIFYING' and 'medication_entry_versions' not in repo.tables


def test_qa_preserves_review_and_safety_stays_deferred():
    repo, bot, r = conversation()
    r = send(bot, r, 'Tôi đang uống Panadol 500mg, dạng viên nén')
    r = send(bot, r, 'cách xác nhận')
    assert r.state == 'AWAITING_CONFIRMATION'
    r = send(bot, r, 'kiểm tra tương tác')
    assert r.state == 'AWAITING_CONFIRMATION'
    r = send(bot, r, 'xác nhận')
    assert r.handoff and 'SAFETY_REQUEST' in r.handoff.requested_workflows
    assert not any('entry_matches' == t or 'safety_assessments' == t for t in repo.tables)


def test_application_help_works_without_inference_and_same_brand_can_be_added():
    provider = MockProvider([])
    _, bot, r = conversation(provider)
    r = send(bot, r, 'cách thêm thuốc')
    assert 'Module 2' in r.text and provider.calls == 0
    repo, bot, r = conversation()
    r = send(bot, r, 'Tôi đang uống A 500mg, dạng viên nén')
    r = send(bot, r, 'thêm thuốc A 250mg, dạng viên nén')
    assert len(bot.store.entries(bot.store.workflow(r.workflow_id))) == 2


def test_ambiguous_reference_name_is_not_verified_or_expanded():
    from module1_intake.nlp.qa import reference_answer
    class AmbiguousReference:
        def lookup(self, fields):
            assert fields['name_raw'] == 'Para'
            return {'complete_identity': False, 'candidates': [{'id': 'a'}, {'id': 'b'}]}
    assert 'chưa đủ rõ' in reference_answer(AmbiguousReference(), {'name_raw': 'Para'})
    assert 'Chưa cấu hình' in reference_answer(None, {'name_raw': 'Para'})
    value = understand(MockProvider([scripted(Medication(name_raw='Para', evidence_text='Para'))]), 'Para', {})
    assert value.medications[0].name_raw == 'Para'


def test_foreign_owner_and_stale_versions_block_confirmation():
    repo, bot, r = conversation()
    r = send(bot, r, 'Tôi đang uống A 500mg, dạng viên nén')
    row = bot.store.entries(bot.store.workflow(r.workflow_id))[0]
    repo.correct_entry(row['id'], row['medication_fields'])
    with pytest.raises(ValueError, match='newer version'):
        send(bot, r, 'xác nhận')
    repo.owner = uuid4()
    with pytest.raises(PermissionError):
        send(bot, r, 'cách nhập thuốc')


def test_failed_inference_preserves_source_without_model_advice():
    repo, bot, r = conversation(MockProvider(['{"answer":"stop medication"}'] * 2))
    r = send(bot, r, 'input')
    assert r.state == 'CLARIFYING' and 'stop medication' not in r.text
    assert list(repo.tables['intake_extractions'].values())[0]['status'] == 'FAILED'


def test_ollama_schema_transport_is_local_and_json_validated():
    calls = []
    def handler(request):
        body = json.loads(request.content)
        calls.append(body)
        return httpx.Response(200, json={'done': True, 'done_reason': 'stop', 'message': {'content': scripted(Medication(name_raw='A', evidence_text='A'))}})
    provider = OllamaProvider('test-model', transport=httpx.MockTransport(handler))
    assert understand(provider, 'A', {}).medications[0].name_raw == 'A'
    assert calls[0]['stream'] is False and calls[0]['format']['additionalProperties'] is False
    assert calls[0]['options']['temperature'] == 0
    assert calls[0]['think'] is False
    with pytest.raises(ValueError):
        OllamaProvider('test', base_url='https://external.example')


def test_ollama_http_failure_retries_and_malformed_envelope_fails_closed():
    calls = []
    def transient(request):
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(503)
        return httpx.Response(200, json={'done': True, 'done_reason': 'stop', 'message': {'content': scripted(Medication(name_raw='A', evidence_text='A'))}})
    assert understand(OllamaProvider('test', transport=httpx.MockTransport(transient)), 'A', {}).medications
    assert len(calls) == 2
    bad = OllamaProvider('test', transport=httpx.MockTransport(lambda r: httpx.Response(200, json=[])))
    with pytest.raises(InferenceError):
        understand(bad, 'A', {})


def test_verified_core_database_is_rejected_before_connection(monkeypatch):
    from tests.integration.test_nlp_v4 import connection
    monkeypatch.setenv('NLP_TEST_DSN', 'host=127.0.0.1 dbname=msa_core_test_v4checks user=core_fixture_admin')
    monkeypatch.setenv('NLP_TEST_BOOTSTRAP', '1')
    monkeypatch.setattr('psycopg.connect', lambda *a, **k: pytest.fail('Must never connect'))
    with pytest.raises(pytest.fail.Exception, match='Refusing database'):
        next(connection.__wrapped__())
