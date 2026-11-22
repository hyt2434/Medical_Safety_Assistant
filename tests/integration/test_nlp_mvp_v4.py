"""New MVP integration on the guarded isolated NLP Core V4 database only."""
import os
from pathlib import Path
import importlib.util
from uuid import uuid4

import pytest

from tests.integration.test_nlp_v4 import connection
from module1_intake.nlp.interfaces.application import ApplicationService, ConfirmationRequest, TurnRequest
from module1_intake.nlp.models import DialogueAct, Intent, Medication, Understanding
from module1_intake.nlp.understanding.providers import MockProvider, OllamaProvider
from module1_intake.nlp.qa_pipeline.contracts import RetrievalQuery
from shared.db import CoreRepository
from tests.db_cleanup import isolated_core_owner


@pytest.fixture
def repo(connection):
    with isolated_core_owner(connection) as owner:
        yield CoreRepository(connection, authenticated_owner=owner)


def send(service, response, text):
    return service.send(TurnRequest(workflow_id=response.workflow_id, revision=response.revision, text=text))


def test_real_core_voice_review_provenance_and_retry(repo, monkeypatch):
    """Real Core persistence; ASR and NLP are deterministic test doubles here."""
    import hashlib
    from module1_intake import api
    from module1_intake.voice import ASRResult
    from module1_intake.nlp.interfaces.application import VoiceRequest, VoiceEditRequest, VoiceSubmitRequest

    text = 'Tôi đang uống Panadol 500mg, dạng viên nén, mỗi sáng một viên'
    class Speech:
        def transcribe(self, audio, language):
            return ASRResult(text, 0.9)
    monkeypatch.setattr(api, '_asr', Speech())
    service = ApplicationService(repo, MockProvider())
    current = service.start(task=Intent.ADD_MEDICATION)
    view = service.preview_voice(VoiceRequest(workflow_id=current.workflow_id, revision=current.revision, audio_payload=b'audio fixture'))
    assert service.resume(current.workflow_id).entries == []
    edited_text = text.replace('một viên', 'hai viên')
    current = service.edit_voice(VoiceEditRequest(workflow_id=view.workflow_id, revision=view.revision,
        draft_id=view.draft.draft_id, text=edited_text))
    assert current.draft.raw_transcript == text and current.draft.text == edited_text
    reloaded = ApplicationService(repo, MockProvider())
    assert reloaded.resume_voice(view.workflow_id) == current
    failed = reloaded.preview_voice(VoiceRequest(workflow_id=current.workflow_id, revision=current.revision, audio_payload=b''))
    assert failed.error_code == 'INVALID_AUDIO' and failed.draft == current.draft
    assert failed.revision == current.revision
    result = reloaded.submit_voice(VoiceSubmitRequest(workflow_id=current.workflow_id, revision=current.revision,
        draft_id=current.draft.draft_id, explicit_confirmation=True))
    assert result.entries[0].medication.dose_raw == 'hai viên' and not result.entries[0].confirmed
    # The adapter retains the ASR transcript, not an audio object. Core AUDIO
    # requires a genuinely retained object; audio_input_id is the API's stable
    # field name for the original TEXT input with VOICE provenance.
    original = repo._owned('intake_inputs', view.draft.audio_input_id)
    assert original['modality'] == 'TEXT'
    assert original['input_digest'] == hashlib.sha256(text.encode('utf-8')).hexdigest()
    payload = original['payload_or_locator']
    assert payload['input_source'] == 'VOICE' and payload['text'] == text
    assert payload['audio_retained'] is False and 'object_locator' not in payload
    assert payload['audio_sha256'] == hashlib.sha256(b'audio fixture').hexdigest()
    rows = repo._all('SELECT * FROM msa.intake_inputs WHERE session_id=%s AND user_id=%s AND modality=%s',
        (original['session_id'], repo.owner, 'TEXT'))
    assert len(rows) == 2
    interpreted, = [row for row in rows if row['id'] != original['id']]
    assert interpreted['input_digest'] == hashlib.sha256(edited_text.encode('utf-8')).hexdigest()
    reviewed = interpreted['payload_or_locator']
    assert reviewed['input_source'] == 'VOICE' and reviewed['text'] == edited_text
    assert 'object_locator' not in reviewed
    assert reviewed['voice']['raw_transcript'] == text
    assert reviewed['voice']['text'] == edited_text
    assert reviewed['voice']['audio_input_id'] == str(original['id'])
    assert reviewed['voice']['draft_id'] == str(view.draft.draft_id)
    done = reloaded.confirm(ConfirmationRequest(workflow_id=result.workflow_id, revision=result.revision,
        request_key=uuid4(), explicit_confirmation=True))
    assert done.entries[0].confirmed
    from module1_intake.nlp.interfaces.application import EntryEditRequest
    revised = service.revise(done.workflow_id, expected_revision=done.revision)
    changed = service.edit_entry(EntryEditRequest(workflow_id=revised.workflow_id, revision=revised.revision,
        entry_version_id=done.entries[0].entry_version_id,
        medication=done.entries[0].medication.model_copy(update={'dose_raw': 'ba viên', 'evidence_text': edited_text+'; sửa liều ba viên'})))
    assert not changed.entries[0].confirmed and changed.entries[0].medication.dose_raw == 'ba viên'
    details = service.details(changed.workflow_id)
    assert details['entry_sources'][str(changed.entries[0].entry_version_id)]['input_source'] == 'VOICE'
    row = repo._owned('medication_entry_versions', changed.entries[0].entry_version_id)
    attempt = repo._owned('intake_extractions', row['source_extraction_id'])
    retained_input = repo._owned('intake_inputs', attempt['input_id'])
    assert retained_input['payload_or_locator']['voice']['raw_transcript'] == text
    assert retained_input['payload_or_locator']['voice']['text'] == edited_text
    assert repo._owned('medication_entry_versions', done.entries[0].entry_version_id)['confirmed_at'] is not None


def test_real_core_ui_catalog_choice_revision_details_and_foreign_owner(repo):
    from module1_intake.nlp.interfaces.application import ManualInputRequest, EntryEditRequest
    products = repo._all("SELECT * FROM msa_ref.medications WHERE brand_name ILIKE %s ORDER BY brand_name,source_medication_id LIMIT 2", ('Lenalimid',))
    assert len(products) == 2 and products[0]['id'] != products[1]['id']
    selected = products[1]
    service = ApplicationService(repo, MockProvider(), dataset_build=selected['dataset_build'])
    current = service.start(task=Intent.ADD_MEDICATION)
    med = Medication(name_raw=selected['brand_name'], strength_raw='5 mg', dosage_form_raw=selected['dosage_form'],
                     dose_raw='một viên', evidence_text=selected['brand_name']+' 5 mg, một viên')
    with pytest.raises(ValueError, match='Catalog version changed'):
        service.save_manual(ManualInputRequest(workflow_id=current.workflow_id, revision=current.revision,
            source_medication_id=selected['source_medication_id'], dataset_build='0'*64, medication=med))
    current = service.save_manual(ManualInputRequest(workflow_id=current.workflow_id, revision=current.revision,
        source_medication_id=selected['source_medication_id'], dataset_build=selected['dataset_build'], medication=med))
    original = current
    current = service.edit_entry(EntryEditRequest(workflow_id=current.workflow_id, revision=current.revision,
        entry_version_id=current.entries[0].entry_version_id,
        medication=med.model_copy(update={'dose_raw':'hai viên','evidence_text':med.evidence_text+'; sửa hai viên'})))
    details = service.details(current.workflow_id)
    choice = details['entry_sources'][str(current.entries[0].entry_version_id)]['selected_product']
    assert choice['source_medication_id'] == selected['source_medication_id']
    assert choice['medication_id'] == str(selected['id']) and choice['dataset_build'] == selected['dataset_build']
    assert details['conversation_id'] == repo._owned('workflow_instances', current.workflow_id)['conversation_id']
    with pytest.raises(ValueError, match='revision'):
        service.edit_entry(EntryEditRequest(workflow_id=original.workflow_id, revision=original.revision,
            entry_version_id=original.entries[0].entry_version_id, medication=med))
    for table in ('entry_matches','medication_list_snapshots','safety_assessments'):
        assert repo._one(f'SELECT count(*) AS n FROM msa.{table} WHERE user_id=%s', (repo.owner,))['n'] == 0
    with isolated_core_owner(repo.db) as other:
        foreign = ApplicationService(CoreRepository(repo.db, authenticated_owner=other), MockProvider())
        with pytest.raises(PermissionError):
            foreign.details(current.workflow_id)
    done = service.confirm(ConfirmationRequest(workflow_id=current.workflow_id, revision=current.revision,
        request_key=uuid4(), explicit_confirmation=True))
    with pytest.raises(ValueError, match='revision|revise|completed|active',):
        service.edit_entry(EntryEditRequest(workflow_id=done.workflow_id, revision=done.revision,
            entry_version_id=done.entries[0].entry_version_id, medication=med))
    revision = service.revise(done.workflow_id, expected_revision=done.revision)
    assert revision.workflow_id != done.workflow_id
    corrected = service.edit_entry(EntryEditRequest(workflow_id=revision.workflow_id, revision=revision.revision,
        entry_version_id=done.entries[0].entry_version_id, medication=med))
    assert not corrected.entries[0].confirmed
    assert service.details(corrected.workflow_id)['assessment'] is None


def test_real_core_pending_target_resume_and_owner_scoped_records(repo):
    first, second = 'Tôi đang uống Panadol', '500mg, dạng viên nén'
    provider = MockProvider([Understanding(medications=[Medication(name_raw='Panadol', evidence_text=first)]).model_dump_json(),
        Understanding(medications=[Medication(strength_raw='500mg', dosage_form_raw='viên nén', evidence_text=second)]).model_dump_json()])
    service = ApplicationService(repo, provider)
    r = service.start(task=Intent.ADD_MEDICATION)
    r = send(service, r, first)
    assert len(r.missing_blockers) == 1 and r.missing_blockers[0]['field_key'] == 'strength_raw'
    restored = ApplicationService(repo, provider)
    assert restored.resume(r.workflow_id).missing_blockers == r.missing_blockers
    r = send(restored, r, second)
    assert r.next_action == 'SHOW_REVIEW' and len(r.entries) == 1
    assert len(restored.records.list(history=True)) == 2
    assert len(restored.records.list()) == 1
    history = restored.records.retrieve(RetrievalQuery('Xem lịch sử thuốc', 'general'))
    assert history.coverage == 'OWNER_SCOPED_HISTORY' and len(history.facts) == 2
    foreign = ApplicationService(CoreRepository(repo.db, authenticated_owner=uuid4()), MockProvider())
    assert foreign.records.list() == []
    empty = foreign.records.retrieve(RetrievalQuery('Xem thuốc', 'general'))
    assert len(empty.facts) == 1 and 'Chưa có bản ghi' in empty.facts[0].text
    with pytest.raises(PermissionError): foreign.resume(r.workflow_id)
    with pytest.raises(ValueError): send(restored, r.model_copy(update={'revision': r.revision - 1}), 'xác nhận')
    done = restored.confirm(ConfirmationRequest(workflow_id=r.workflow_id, revision=r.revision,
        request_key=uuid4(), explicit_confirmation=True))
    assert done.action_authorized and done.entries[0].confirmed
    assert restored.resume(done.workflow_id).assistant_message == done.assistant_message
    assert restored.handoff(done.workflow_id).entries[0].medication.strength_raw == '500mg'


def test_real_core_question_retries_are_persisted_and_bounded(repo):
    text = 'Tôi đang uống Panadol'
    raw = Understanding(medications=[Medication(name_raw='Panadol', evidence_text=text)]).model_dump_json()
    service = ApplicationService(repo, MockProvider([raw] * 4))
    r = service.start(task=Intent.ADD_MEDICATION)
    for count in (1, 2, 3):
        r = send(service, r, text)
        assert len(r.missing_blockers) == 1 and r.missing_blockers[0]['attempt'] == count
        assert str(r.entries[0].entry_version_id) == r.missing_blockers[0]['target_id']
    r = send(service, r, text)
    assert r.state == 'AWAITING_CONFIRMATION' and not r.missing_blockers and not r.action_authorized


def test_real_core_hybrid_help_and_unavailable_safety_write_no_findings(repo):
    service = ApplicationService(repo, MockProvider())
    r = service.start()
    r = send(service, r, 'cách thêm thuốc')
    assert r.qa_results[0].status == 'WORKING' and r.evidence_refs
    r = send(service, r, 'kiểm tra tương tác')
    assert r.missing_blockers[0]['field_key'] == 'interaction_target'
    assert repo._one('SELECT count(*) AS n FROM msa.safety_assessments WHERE user_id=%s', (repo.owner,))['n'] == 0
    assert repo._one('SELECT count(*) AS n FROM msa.entry_matches WHERE user_id=%s', (repo.owner,))['n'] == 0


def test_real_core_explicit_module2_and_module3_adapters_with_existing_synthetic_fixture(repo):
    # Reuse the established Core test fixture builder and actual Module 3 bounded
    # dataset/engine. No approved data import or fake runtime safety engine.
    path = Path(__file__).resolve().parents[2] / 'db/tests/fixtures.py'
    spec = importlib.util.spec_from_file_location('nlp_mvp_core_fixtures', path)
    fixtures = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixtures)
    build, products = fixtures.fixture_sources(repo)
    text = 'Core Fixture 0 500mg; Core Fixture 1 500mg'
    meds = [Medication(name_raw=f'Core Fixture {n}', strength_raw='500mg', evidence_text=f'Core Fixture {n} 500mg') for n in range(2)]
    service = ApplicationService(repo, MockProvider([Understanding(medications=meds).model_dump_json()]))
    r = service.start(task=Intent.ADD_MEDICATION)
    r = send(service, r, text)
    r = send(service, r, 'không rõ')
    r = send(service, r, 'không rõ')  # One unknown decision per medication target.
    r = service.confirm(ConfirmationRequest(workflow_id=r.workflow_id, revision=r.revision, request_key=uuid4(), explicit_confirmation=True))
    assert repo._one('SELECT count(*) AS n FROM msa.entry_matches WHERE user_id=%s',(repo.owner,))['n'] == 0
    matches = service.identify(r.workflow_id, dataset_build=build)
    assert all(match['match_status'] == 'SELECTED' for match, result in matches)
    # Synthetic REF is deliberately restricted to SYNTHETIC_TEST context by Core.
    snapshot = repo.create_snapshot([(match['entry_version_id'], match['id']) for match, result in matches], data_context='SYNTHETIC_TEST')
    key = uuid4()
    assessment, result = service.assess_snapshot(r.workflow_id, snapshot['id'], fixtures.dataset(), request_key=key)
    assert assessment['execution_status'] == 'COMPLETED'
    assert result['safe_to_take'] is None and result['no_interactions'] is None
    answer = service.answer_assessment(r.workflow_id, assessment['id'], 'Kết quả có nguồn?')
    assert answer.status == 'PARTIAL' and answer.evidence_refs and 'coverage=PARTIAL' in answer.text
    assert 'DDI (MAJOR)' in answer.text  # Explicit synthetic source finding, not a clinical claim.
    repeated, _ = service.assess_snapshot(r.workflow_id, snapshot['id'], fixtures.dataset(), request_key=key)
    assert repeated['id'] == assessment['id']
    foreign = ApplicationService(CoreRepository(repo.db, authenticated_owner=uuid4()), MockProvider())
    with pytest.raises(PermissionError): foreign.answer_assessment(r.workflow_id, assessment['id'], 'question')


@pytest.fixture
def qwen():
    if os.environ.get('NLP_RUN_REAL_OLLAMA') != '1': pytest.skip('Real Qwen opt-in required')
    return OllamaProvider(os.environ.get('NLP_OLLAMA_MODEL', 'qwen3.5:9b'),
        timeout=float(os.environ.get('NLP_OLLAMA_TIMEOUT', '120')))


def test_real_qwen_multi_turn_core_purpose_correction_confirmation_and_resume(repo, qwen):
    service = ApplicationService(repo, qwen)
    r = service.start()
    r = send(service, r, 'Tôi được kê 2 hộp Panadol 500mg.')
    assert r.dialogue_act == DialogueAct.PROVIDE_INFO
    assert r.entries[0].medication.quantity_raw == '2 hộp' and not r.action_authorized
    assert r.missing_blockers[0]['field_key'] == 'purpose'
    service = ApplicationService(repo, qwen)
    r = service.resume(r.workflow_id)
    r = send(service, r, 'Thêm vào danh sách; dạng viên nén.')
    assert r.state == 'AWAITING_CONFIRMATION' and not r.action_authorized
    before = r.entries[0].entry_version_id
    r = send(service, r, 'Sửa thuốc 1 thành Panadol 250mg.')
    assert r.entries[0].entry_version_id != before and r.entries[0].medication.strength_raw == '250mg'
    assert r.entries[0].medication.quantity_raw == '2 hộp'
    r = service.confirm(ConfirmationRequest(workflow_id=r.workflow_id, revision=r.revision,
                                           request_key=uuid4(), explicit_confirmation=True))
    assert r.state == 'COMPLETED' and r.action_authorized
    med = service.handoff(r.workflow_id).entries[0].medication
    assert med.quantity_raw == '2 hộp' and med.dosage_form_raw == 'viên nén'
    assert repo._one('SELECT count(*) AS n FROM msa.entry_matches WHERE user_id=%s', (repo.owner,))['n'] == 0
    assert repo._one("SELECT count(*) AS n FROM information_schema.tables WHERE table_schema IN ('msa','msa_ref') AND table_type='BASE TABLE'")['n'] == 20


def test_real_qwen_hybrid_composition_and_timing_extension_persistence(repo, qwen):
    service = ApplicationService(repo, qwen)
    r = service.start()
    r = send(service, r, 'cách xác nhận')
    assert r.qa_results[0].composition == 'QWEN_GROUNDED_SELECTION'
    assert r.qa_results[0].evidence_refs and r.qa_results[0].status == 'WORKING'
    r = send(service, r, 'Vui lòng lưu Augmentin 625mg, dạng viên nén, uống 1 viên sáng và tối trong 7 ngày.')
    assert r.state == 'AWAITING_CONFIRMATION'
    med = r.entries[0].medication
    assert med.administrations[0].timing_slots_raw == ['sáng', 'tối']
    assert med.duration_raw in {'trong 7 ngày', '7 ngày'}
    restored = ApplicationService(repo, qwen).resume(r.workflow_id)
    assert restored.entries[0].medication.administrations[0].timing_slots_raw == ['sáng', 'tối']
    r = service.confirm(ConfirmationRequest(workflow_id=r.workflow_id, revision=r.revision,
                                           request_key=uuid4(), explicit_confirmation=True))
    assert r.entries[0].confirmed
