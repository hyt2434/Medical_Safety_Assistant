"""Phase A policy/service tests: synthetic data and mocked HTTP, no database."""
from copy import deepcopy
import json
from uuid import uuid4

import httpx
import pytest
from pydantic import ValidationError

from module1_intake.nlp.interfaces.application import ApplicationService, ConfirmationRequest, TurnRequest
from module1_intake.nlp.qa_pipeline.composition import GroundedComposer
from module1_intake.nlp.qa_pipeline.pipeline import HybridQA
from module1_intake.nlp.models import DialogueAct, Intent, Medication, Understanding
from module1_intake.nlp.dialogue_management.policy import CONTRACTS
from module1_intake.nlp.understanding.providers import MockProvider, OllamaProvider, understand
from module1_intake.nlp.qa_pipeline.contracts import EvidenceRef, RetrievalQuery, RetrievalResult, VerifiedFact
from module1_intake.nlp.qa_pipeline.structured import CoreReferenceRetriever, Module2FactRetriever
from module1_intake.nlp.qa_pipeline.rag.interface import DisabledDocumentRetriever
from tests.unit.test_nlp import FakeCore, conversation, send


def raw(text, **fields):
    return Understanding(medications=[Medication(evidence_text=text, **fields)]).model_dump_json()


@pytest.mark.parametrize('text,act', [('Tôi được kê Panadol.', DialogueAct.PROVIDE_INFO),
    ('Vui lòng lưu Panadol.', DialogueAct.REQUEST_ACTION), ('Panadol có hoạt chất gì?', DialogueAct.ASK_QUESTION),
    ('Sửa thuốc 2 thành Panadol.', DialogueAct.CORRECT)])
def test_dialogue_act_is_backend_derived(text, act):
    value = Understanding(medications=[Medication(name_raw='Panadol', evidence_text=text)], dialogue_act=DialogueAct.CONFIRM)
    result = understand(MockProvider([value.model_dump_json()]), text, {}, attempts=1)
    assert result.dialogue_act == act


def test_contracts_do_not_require_dose_for_reference_question():
    assert 'dose_raw' in CONTRACTS[Intent.ADD_MEDICATION].optional
    assert 'dose_raw' not in CONTRACTS[Intent.MEDICATION_QA].required
    assert CONTRACTS[Intent.CHECK_INTERACTION].required == ('two_targets',)


def test_purpose_then_slot_fill_review_without_authorized_save():
    first = 'Tôi được kê 2 hộp Panadol 500mg.'
    second = 'Thêm vào danh sách; dạng viên nén.'
    repo = FakeCore()
    service = ApplicationService(repo, MockProvider([
        raw(first, name_raw='Panadol', strength_raw='500mg', quantity_raw='2 hộp'),
        raw(second, dosage_form_raw='viên nén')]))
    r = service.start()
    r = service.send(TurnRequest(workflow_id=r.workflow_id, revision=r.revision, text=first))
    assert r.missing_blockers[0]['field_key'] == 'purpose'
    assert r.dialogue_act == DialogueAct.PROVIDE_INFO and not r.action_authorized
    r = service.send(TurnRequest(workflow_id=r.workflow_id, revision=r.revision, text=second))
    assert r.state == 'AWAITING_CONFIRMATION'
    assert r.entries[0].medication.quantity_raw == '2 hộp'
    assert not r.entries[0].confirmed and not r.action_authorized


def test_action_only_followup_advances_existing_candidate_without_new_record():
    first = 'Tôi đang uống Panadol 500mg, dạng viên nén'
    repo = FakeCore()
    service = ApplicationService(repo, MockProvider([raw(first, name_raw='Panadol', strength_raw='500mg', dosage_form_raw='viên nén'),
                                                     Understanding().model_dump_json()]))
    r = service.start()
    r = service.send(TurnRequest(workflow_id=r.workflow_id, revision=r.revision, text=first))
    original = r.entries[0].entry_version_id
    r = service.send(TurnRequest(workflow_id=r.workflow_id, revision=r.revision, text='Vui lòng lưu'))
    assert r.state == 'AWAITING_CONFIRMATION' and r.entries[0].entry_version_id == original
    assert not r.action_authorized


def test_one_blocker_per_turn_and_two_retries_then_unknown_review():
    text = 'Tôi đang uống Panadol'
    repo, bot, r = conversation(MockProvider([raw(text, name_raw='Panadol')] * 4))
    for count in (1, 2, 3):
        r = send(bot, r, text)
        questions = bot.store.workflow(r.workflow_id)['context']['pending_questions']
        assert len(questions) == 1 and questions[0]['field_key'] == 'strength_raw'
        assert questions[0]['attempt'] == count
        assert 'dạng thuốc' not in r.text
    r = send(bot, r, text)
    assert r.state == 'AWAITING_CONFIRMATION'
    assert bot.store.workflow(r.workflow_id)['context']['pending_questions'] == []
    assert bot.store.entries(bot.store.workflow(r.workflow_id))[0]['medication_fields']['strength_raw'] is None


def test_pending_slot_targets_one_medication_without_cross_drug_merge():
    first, followup = 'A 500mg; B 250mg', 'dạng viên nén'
    provider = MockProvider([Understanding(medications=[Medication(name_raw='A', strength_raw='500mg', evidence_text='A 500mg'),
                    Medication(name_raw='B', strength_raw='250mg', evidence_text='B 250mg')]).model_dump_json(),
                    raw(followup, dosage_form_raw='viên nén')])
    repo, bot, r = conversation(provider)
    r = send(bot, r, first)
    target = bot.store.workflow(r.workflow_id)['context']['pending_questions'][0]['target_id']
    r = send(bot, r, followup)
    entries = bot.store.entries(bot.store.workflow(r.workflow_id))
    assert entries[0]['medication_fields']['dosage_form_raw'] == 'viên nén'
    assert entries[1]['medication_fields']['dosage_form_raw'] is None
    assert str(entries[0]['supersedes_version_id']) == target


def test_interaction_missing_second_target_survives_followup_without_confirming():
    first, second = 'Kiểm tra tương tác Panadol 500mg', 'Augmentin 625mg'
    repo, bot, r = conversation(MockProvider([raw(first, name_raw='Panadol', strength_raw='500mg'),
                                             raw(second, name_raw='Augmentin', strength_raw='625mg')]))
    r = send(bot, r, first)
    assert bot.store.workflow(r.workflow_id)['context']['pending_questions'][0]['field_key'] == 'interaction_target'
    r = send(bot, r, second)
    assert 'UNASSESSED' in r.text and 'safe_to_take' not in r.text
    assert 'medication_entry_versions' not in repo.tables


def test_reference_question_does_not_trigger_intake_slot_questions():
    text = 'Panadol chứa hoạt chất gì?'
    repo, bot, r = conversation(MockProvider([raw(text, name_raw='Panadol')]))
    r = send(bot, r, text)
    assert not bot.store.workflow(r.workflow_id)['context']['pending_questions']
    assert 'medication_entry_versions' not in repo.tables
    assert 'chưa khả dụng' in r.text


def test_two_unspecified_medications_need_targets_without_intake_or_assessment():
    repo, bot, r = conversation(MockProvider([Understanding().model_dump_json()]))
    r = send(bot, r, 'Kiểm tra hai thuốc này')
    ctx = bot.store.workflow(r.workflow_id)['context']
    assert ctx['active_intents'] == ['CHECK_INTERACTION']
    assert ctx['pending_questions'][0]['field_key'] == 'interaction_target'
    assert 'medication_entry_versions' not in repo.tables and 'safety_assessments' not in repo.tables


def source_result():
    return RetrievalResult(status='WORKING', coverage='SYNTHETIC_TEST_ONLY', facts=[VerifiedFact(
        fact_id='fact1', text='Synthetic verified source statement.', source=EvidenceRef(
            source_id='fixture', locator='test://source/1', scope='Synthetic unit fixture'))], limitations=['Fixture scope only.'])


@pytest.mark.parametrize('model_output', ['{"fact_ids":["invented"]}', '{"answer":"UNSAFE_INVENTED_FACT"}', 'not JSON'])
def test_grounded_composer_rejects_invented_answers_and_falls_back(model_output):
    provider = OllamaProvider('test', transport=httpx.MockTransport(lambda r: httpx.Response(200,
        json={'done': True, 'message': {'content': model_output}})))
    answer = GroundedComposer(provider).compose('question', source_result())
    assert answer.composition == 'TEMPLATE_FALLBACK'
    assert 'Synthetic verified source statement.' in answer.text
    assert 'UNSAFE_INVENTED_FACT' not in answer.text and 'invented' not in answer.text
    assert 'Fixture scope only.' in answer.text and len(answer.evidence_refs) == 1


def test_qwen_only_selects_authoritative_fact_ids():
    def handler(request):
        payload = json.loads(request.content)
        assert payload['think'] is False
        assert payload['format']['properties']['fact_ids']['items']['enum'] == ['fact1']
        return httpx.Response(200, json={'done': True, 'message': {'content': '{"fact_ids":["fact1"]}'}})
    answer = GroundedComposer(OllamaProvider('test', transport=httpx.MockTransport(handler))).compose('question', source_result())
    assert answer.composition == 'QWEN_GROUNDED_SELECTION' and answer.evidence_refs[0].locator == 'test://source/1'


def test_model_selection_cannot_hide_required_coverage_or_limitations():
    result = source_result()
    result.facts.append(VerifiedFact(fact_id='coverage', text='Coverage is PARTIAL.', source=result.facts[0].source, required=True))
    provider = OllamaProvider('test', transport=httpx.MockTransport(lambda r: httpx.Response(200,
        json={'done': True, 'message': {'content': '{"fact_ids":["fact1"]}'}})))
    answer = GroundedComposer(provider).compose('question', result)
    assert 'Coverage is PARTIAL.' in answer.text and 'Fixture scope only.' in answer.text


def verified_module2_result():
    return {'identification_status': 'VERIFIED', 'candidates': [{'candidate_key': 'fixture-key',
        'product': {'ingredients': ['Synthetic ingredient'], 'strength': '123mg'},
        'independent_review': {'status': 'VERIFIED'}, 'registration_description_conflict': False,
        'ingestion_statuses': ['VALID'], 'source_evidence': [{'raw_sha256': 'a' * 64, 'locator_json': '{"record":1}'}]}]}


def test_module2_fact_adapter_requires_verified_identity_and_retained_evidence():
    result = verified_module2_result()
    class Reference:
        def lookup(self, fields): return result
    adapter = Module2FactRetriever(Reference())
    query = RetrievalQuery('ingredients?', 'ingredients', {'name_raw': 'Synthetic'})
    facts = adapter.retrieve(query)
    assert facts.status == 'WORKING' and len(facts.facts) == 1
    assert 'Synthetic ingredient' in facts.facts[0].text and facts.facts[0].source.sha256 == 'a' * 64
    result['identification_status'] = 'REVIEW_REQUIRED'
    assert not adapter.retrieve(query).facts
    result['identification_status'] = 'VERIFIED'
    result['candidates'][0]['source_evidence'] = []
    assert not adapter.retrieve(query).facts


def test_core_candidates_and_ddinter_ids_are_not_clinical_facts():
    class Reference:
        def lookup(self, fields):
            return {'complete_identity': True, 'candidates': [{'id': uuid4(), 'source_locator': 'test://candidate',
                                                               'ddinter_id': 'DDInter14'}]}
    result = CoreReferenceRetriever(Reference()).retrieve(RetrievalQuery('question', 'ingredients', {'name_raw':'A'}))
    assert result.status == 'PARTIAL' and not result.facts
    answer = HybridQA().answer(Intent.CHECK_INTERACTION, RetrievalQuery('safe?', 'safety'))
    assert answer.status == 'UNAVAILABLE' and answer.coverage == 'UNASSESSED'


def test_retrieval_errors_and_phase_b_do_not_expose_details():
    class Broken:
        def retrieve(self, query): raise RuntimeError('PRIVATE_PATIENT_CONNECTION_DETAIL')
    answer = HybridQA(medication=Broken()).answer(Intent.MEDICATION_QA, RetrievalQuery('question', 'ingredients'))
    assert answer.status == 'UNAVAILABLE' and 'PRIVATE_PATIENT' not in answer.text
    assert DisabledDocumentRetriever().retrieve(RetrievalQuery('question', 'general')).status == 'UNAVAILABLE'


def test_frontend_requests_cannot_supply_owner_or_authorize_by_intent():
    with pytest.raises(ValidationError):
        TurnRequest(workflow_id=uuid4(), revision=1, text='test', owner=uuid4())
    repo = FakeCore()
    service = ApplicationService(repo, MockProvider())
    r = service.start()
    with pytest.raises(ValueError, match='Explicit'):
        service.confirm(ConfirmationRequest(workflow_id=r.workflow_id, revision=r.revision,
            request_key=uuid4(), explicit_confirmation=False))


def test_unknown_details_never_waive_another_or_new_medication():
    repo, bot, r = conversation(MockProvider([
        Understanding(medications=[Medication(name_raw='A', evidence_text='A'),
                                   Medication(name_raw='B', evidence_text='B')]).model_dump_json(),
        raw('thêm thuốc C', name_raw='C')]))
    r = send(bot, r, 'A; B')
    r = send(bot, r, 'không rõ')
    pending = bot.store.workflow(r.workflow_id)['context']['pending_questions'][0]
    entries = bot.store.entries(bot.store.workflow(r.workflow_id))
    assert pending['target_id'] == str(entries[1]['id'])
    assert r.state == 'CLARIFYING'
    r = send(bot, r, 'không rõ')
    assert r.state == 'AWAITING_CONFIRMATION'
    r = send(bot, r, 'thêm thuốc C')
    pending = bot.store.workflow(r.workflow_id)['context']['pending_questions'][0]
    assert pending['target_id'] == str(bot.store.entries(bot.store.workflow(r.workflow_id))[2]['id'])
    assert r.state == 'CLARIFYING'


def test_unknown_cannot_resolve_ambiguous_correction_target():
    repo, bot, r = conversation()
    r = send(bot, r, 'Tôi đang uống A 500mg; đang dùng B 250mg')
    r = send(bot, r, 'sửa hàm lượng 100mg')
    assert bot.store.workflow(r.workflow_id)['context']['pending_questions'][0]['field_key'] == 'target_entry'
    r = send(bot, r, 'không rõ')
    assert r.state == 'CLARIFYING'
    assert all(row['confirmed_at'] is None for row in bot.store.entries(bot.store.workflow(r.workflow_id)))


def test_side_question_restores_exact_intake_slot_after_restart():
    first, question, target, followup = 'Tôi đang uống A', 'Kiểm tra tương tác', 'B', '500mg, dạng viên nén'
    provider = MockProvider([raw(first, name_raw='A'), Understanding().model_dump_json(),
                            raw(target, name_raw='B'), raw(followup, strength_raw='500mg', dosage_form_raw='viên nén')])
    repo = FakeCore()
    service = ApplicationService(repo, provider)
    r = service.start(task=Intent.ADD_MEDICATION)
    r = service.send(TurnRequest(workflow_id=r.workflow_id, revision=r.revision, text=first))
    pending = r.missing_blockers
    r = service.send(TurnRequest(workflow_id=r.workflow_id, revision=r.revision, text=question))
    assert r.missing_blockers[0]['field_key'] == 'interaction_target'
    service = ApplicationService(repo, provider)
    r = service.resume(r.workflow_id)
    r = service.send(TurnRequest(workflow_id=r.workflow_id, revision=r.revision, text=target))
    assert r.missing_blockers == pending
    r = service.send(TurnRequest(workflow_id=r.workflow_id, revision=r.revision, text=followup))
    assert r.state == 'AWAITING_CONFIRMATION' and len(r.entries) == 1
    assert r.entries[0].medication.name_raw == 'A'


def test_resume_shows_current_start_confirmation_and_cancellation_messages():
    repo = FakeCore()
    service = ApplicationService(repo, MockProvider())
    r = service.start(task=Intent.ADD_MEDICATION)
    assert service.resume(r.workflow_id).assistant_message == r.assistant_message
    r = service.send(TurnRequest(workflow_id=r.workflow_id, revision=r.revision,
        text='Tôi đang uống Panadol 500mg, dạng viên nén'))
    r = service.send(TurnRequest(workflow_id=r.workflow_id, revision=r.revision, text='cách xác nhận'))
    r = service.confirm(ConfirmationRequest(workflow_id=r.workflow_id, revision=r.revision,
        request_key=uuid4(), explicit_confirmation=True))
    restored = ApplicationService(repo, MockProvider()).resume(r.workflow_id)
    assert restored.assistant_message == r.assistant_message
    assert restored.dialogue_act == DialogueAct.CONFIRM and not restored.qa_results
    r = service.revise(r.workflow_id)
    r = service.send(TurnRequest(workflow_id=r.workflow_id, revision=r.revision, text='hủy'))
    restored = service.resume(r.workflow_id)
    assert restored.dialogue_act == DialogueAct.CANCEL and not restored.qa_results
    assert restored.assistant_message == r.assistant_message and not restored.action_authorized


def test_every_required_finding_survives_model_selection_window():
    result = source_result()
    result.facts.extend(VerifiedFact(fact_id=f'finding:{n}', text=f'Critical retained finding {n}.',
        source=result.facts[0].source, required=True) for n in range(20))
    provider = OllamaProvider('test', transport=httpx.MockTransport(lambda r: httpx.Response(200,
        json={'done': True, 'message': {'content': '{"fact_ids":["fact1"]}'}})))
    answer = GroundedComposer(provider).compose('question', result)
    assert len(answer.evidence_refs) == 21
    assert all(f'Critical retained finding {n}.' in answer.text for n in range(20))
    assert answer.composition == 'QWEN_GROUNDED_SELECTION'
