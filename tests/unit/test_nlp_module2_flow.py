"""Application orchestration regressions using the existing Core/reference doubles."""
from copy import deepcopy
import json
from uuid import uuid4

import pytest
from pydantic import ValidationError

from module1_intake.nlp.interfaces.application import ApplicationService, TurnRequest, WorkflowActionRequest
from module1_intake.nlp.interfaces.application_cli import run_application
from module1_intake.nlp.models import Intent, Understanding, IntentCandidate
from module1_intake.nlp.qa_pipeline.composition import GroundedComposer
from module1_intake.nlp.understanding.providers import MockProvider
from module1_intake.nlp.understanding.routing import explicit_backend_action
from tests.unit.test_nlp import FakeCore
from tests.unit.module2.test_core import BUILD, ReferenceRows, product, component, mapping


class IdentifyingCore(FakeCore):
    def __init__(self, *, ambiguous=False, multiple_targets=False):
        super().__init__()
        med = product(name='Alpha')
        comp = component(med)
        self.references = ReferenceRows([med, *([product(name='Alpha', strength='250mg')] if ambiguous else [])],
            [comp], [mapping(comp), *([mapping(comp, 'DDInter900002', 'Synthetic Beta')] if multiple_targets else [])])

    def _one(self, query, params=()):
        if 'SELECT dataset_build FROM msa_ref.medications WHERE id=' in query:
            return next(({'dataset_build': p['dataset_build']} for p in self.references.products if p['id'] == params[0]), None)
        if 'msa.published' in query or 'obj_description' in query:
            return self.references._one(query, params)
        return super()._one(query, params)

    def _all(self, query, params=()):
        if 'msa_ref.' in query:
            return self.references._all(query, params)
        if 'SELECT p.session_id' in query:
            item = self._owned('intake_items', params[0])
            extraction = self._owned('intake_extractions', item['extraction_id'])
            inp = self._owned('intake_inputs', extraction['input_id'])
            return [{'session_id': inp['session_id']}]
        return super()._all(query, params)

    def record_match(self, entry, outcome, **options):
        self._owned('medication_entry_versions', entry)
        return self.put('entry_matches', entry_version_id=entry, match_status=outcome, **options)


def turn(service, response, text):
    return service.send(TurnRequest(workflow_id=response.workflow_id, revision=response.revision, text=text))


def action(service, response, kind='IDENTIFY', **options):
    return service.execute(WorkflowActionRequest(workflow_id=response.workflow_id, revision=response.revision,
        request_key=uuid4(), action=kind, explicit_request=True, **options))


def confirmed_service(*, ambiguous=False, multiple_targets=False, provider=None, composer=None):
    repo = IdentifyingCore(ambiguous=ambiguous, multiple_targets=multiple_targets)
    service = ApplicationService(repo, provider or MockProvider(), dataset_build=BUILD, composer=composer)
    r = service.start(task=Intent.ADD_MEDICATION)
    r = turn(service, r, 'Tôi đang uống Alpha' if ambiguous else 'Tôi đang uống Alpha 0,5g, dạng viên nén')
    if ambiguous:
        r = turn(service, r, 'không rõ')
    assert r.state == 'AWAITING_CONFIRMATION'
    r = turn(service, r, 'xác nhận')
    return repo, service, r


def test_confirmation_does_not_run_identification_or_safety():
    repo, service, r = confirmed_service()
    assert r.authorization_scope == 'TRANSCRIPTION_ONLY'
    assert not repo.tables.get('entry_matches') and not repo.tables.get('safety_assessments')
    r = action(service, r)
    assert r.identification_results[0]['identification_status'] == 'VERIFIED'
    assert r.identification_results[0]['schema_version'] == 'module2.medication_identity.v1'
    assert r.identification_results[0]['core_match_status'] == 'SELECTED'
    assert r.executed_action == 'IDENTIFY' and r.assessment_id is None
    assert 'mapping=VERIFIED' in r.assistant_message and 'msa_ref.medication_ingredients/' in r.assistant_message
    assert r.evidence_refs and not repo.tables.get('safety_assessments')


def test_completed_turn_rejects_whitespace_without_new_messages():
    repo, service, r = confirmed_service()
    before = len(repo.tables['conversation_messages'])
    with pytest.raises(ValueError, match='Message'):
        turn(service, r, '  ')
    assert len(repo.tables['conversation_messages']) == before


def test_natural_explicit_identification_after_confirmation():
    repo, service, r = confirmed_service()
    r = turn(service, r, 'Nhận diện các thuốc đã xác nhận')
    assert r.executed_action == 'IDENTIFY' and r.identification_results
    restored = ApplicationService(repo, MockProvider(), dataset_build=BUILD).resume(r.workflow_id)
    assert restored == r


def test_ambiguous_result_reuses_targeted_slot_filling_and_reconfirmation():
    repo, service, r = confirmed_service(ambiguous=True)
    original = r.entries[0].entry_version_id
    r = action(service, r)
    assert r.identification_results[0]['identification_status'] == 'REVIEW_REQUIRED'
    assert len(r.identification_results[0]['candidates']) == 2
    assert r.missing_blockers[0]['field_key'] == 'strength_raw'
    old_workflow = r.workflow_id
    r = turn(service, r, '500mg, dạng viên nén')
    assert r.workflow_id != old_workflow and r.state == 'AWAITING_CONFIRMATION'
    assert not r.action_authorized and not r.entries[0].confirmed
    assert r.entries[0].medication.name_raw == 'Alpha'
    with pytest.raises(ValueError, match='confirmation'):
        action(service, r)
    r = turn(service, r, 'xác nhận')
    r = action(service, r)
    assert r.identification_results[0]['identification_status'] == 'VERIFIED'
    assert repo._owned('medication_entry_versions', original)['confirmed_at'] is not None
    with pytest.raises(ValueError, match='newer version'):
        service.resume(old_workflow)


def test_unknown_identity_and_multiple_targets_stay_explicit():
    repo, service, r = confirmed_service()
    repo.references.products.clear()
    r = action(service, r)
    assert r.identification_results[0]['identification_status'] == 'UNRESOLVED'
    assert r.next_action == 'REVISE_AND_RECONFIRM' and 'UNRESOLVED' in r.assistant_message
    repo, service, r = confirmed_service(multiple_targets=True)
    r = action(service, r)
    identity = r.identification_results[0]
    assert identity['mapping_status'] == 'REVIEW_REQUIRED'
    assert identity['ingredients'][0]['ddinter_id'] is None
    assert len(identity['ingredients'][0]['ddinter_mappings']) == 2
    assert not r.missing_blockers
    assert 'MULTIPLE_OR_INCOMPLETE_CORE_TARGETS' in r.assistant_message


def test_action_retries_are_idempotent_and_dependency_changes_are_rejected():
    repo, service, r = confirmed_service()
    request = WorkflowActionRequest(workflow_id=r.workflow_id, revision=r.revision,
                                   request_key=uuid4(), action='IDENTIFY', explicit_request=True)
    first = service.execute(request)
    count = len(repo.tables['entry_matches'])
    assert service.execute(request) == first and len(repo.tables['entry_matches']) == count
    service.dataset_build = 'b' * 64
    with pytest.raises(ValueError, match='different dependencies'):
        service.execute(request)


def test_unconfirmed_stale_foreign_or_nonexplicit_actions_are_rejected():
    repo, service, r = confirmed_service()
    request = WorkflowActionRequest(workflow_id=r.workflow_id, revision=r.revision,
                                   request_key=uuid4(), action='IDENTIFY', explicit_request=True)
    with pytest.raises(ValueError, match='Explicit'):
        service.execute(request.model_copy(update={'explicit_request': False}))
    with pytest.raises(ValueError, match='revision'):
        service.execute(request.model_copy(update={'revision': r.revision - 1}))
    repo.owner = uuid4()
    with pytest.raises(PermissionError): service.execute(request)
    with pytest.raises(ValidationError):
        WorkflowActionRequest.model_validate({**request.model_dump(), 'owner': uuid4()})


def test_absent_build_or_safety_dataset_is_unavailable_without_backend_execution():
    repo, service, r = confirmed_service()
    r = action(service, r, 'ASSESS')
    assert r.next_action == 'UNAVAILABLE' and r.assessment_id is None
    assert not repo.tables.get('entry_matches') and not repo.tables.get('safety_assessments')
    service.dataset_build = None
    r = action(service, r)
    assert r.executed_action is None and 'UNAVAILABLE' in r.assistant_message


@pytest.mark.parametrize('text', ['Không kiểm tra tương tác', 'Cách kiểm tra tương tác?',
    'Nếu kiểm tra tương tác thì sao?', 'Hãy nói "kiểm tra tương tác"', 'Kiểm tra tương tác Alpha và Beta'])
def test_questions_negations_and_different_targets_do_not_authorize_assessment(text):
    assert explicit_backend_action(text) is None
    repo, service, r = confirmed_service()
    r = turn(service, r, text)
    assert r.executed_action is None and not repo.tables.get('safety_assessments')


def test_model_intent_cannot_authorize_an_unrequested_action():
    repo, service, r = confirmed_service()
    service.bot.provider = MockProvider([Understanding(intents=[IntentCandidate(
        intent=Intent.CHECK_INTERACTION, evidence_text='hello')]).model_dump_json()])
    r = turn(service, r, 'hello')
    assert r.executed_action is None and not repo.tables.get('entry_matches')


def test_followup_question_uses_retained_backend_identities_without_rerunning():
    repo, service, r = confirmed_service()
    r = action(service, r)
    count = len(repo.tables['entry_matches'])
    r = turn(service, r, 'Các thuốc đã xác nhận có thành phần gì?')
    assert r.executed_action is None and 'Source Alpha' in r.assistant_message
    assert len(repo.tables['entry_matches']) == count and r.evidence_refs


def test_grounded_selection_cannot_hide_identity_mapping_or_candidates():
    class SelectingProvider:
        def generate_structured(self, system, payload, schema):
            return json.dumps({'fact_ids': [payload['facts'][0]['fact_id']]})
    repo, service, r = confirmed_service(multiple_targets=True, composer=GroundedComposer(SelectingProvider()))
    r = action(service, r)
    assert r.qa_results[0].composition == 'QWEN_GROUNDED_SELECTION'
    assert 'mapping=REVIEW_REQUIRED' in r.assistant_message and 'DDInter900002' in r.assistant_message
    assert 'Ứng viên tham chiếu' in r.assistant_message and r.evidence_refs


def test_application_cli_conversation_displays_source_backed_v1_results():
    repo = IdentifyingCore()
    service = ApplicationService(repo, MockProvider(), dataset_build=BUILD)
    inputs = iter(['Tôi đang uống Alpha 0,5g, dạng viên nén', 'xác nhận', '/identify', '/json', '/exit'])
    output = []
    run_application(service, service.start(task=Intent.ADD_MEDICATION), read=lambda _: next(inputs), write=output.append)
    transcript = '\n'.join(output)
    assert 'identity=VERIFIED' in transcript and 'mapping=VERIFIED' in transcript
    assert 'msa.entry_matches/' in transcript and 'module2.medication_identity.v1' in transcript
    assert 'Request rejected' not in transcript and not repo.tables.get('safety_assessments')
