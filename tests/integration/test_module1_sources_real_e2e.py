"""Real Qwen/Whisper -> existing Core V4 -> published products -> real DDInter.

Reuse the marked PostgreSQL fixture and existing reference builds, without
bootstrap, migrations or imports. Inputs are authored test cases, not patients.
The existing deterministic fact composer renders backend results. All three
input adapters persist through the actual Core repository and confirmation API.
"""
import csv
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
from uuid import uuid4

import pytest

from module1_intake import api
from module1_intake.voice import WhisperASR
from module1_intake.nlp.interfaces.application import (
    ApplicationService, ConfirmationRequest, TurnRequest, VoiceEditRequest,
    VoiceRequest, VoiceSubmitRequest, WorkflowActionRequest,
    ManualInputRequest, ManualEditRequest,
)
from module1_intake.nlp.models import Intent, Medication, Administration
from module1_intake.nlp.qa_pipeline.composition import GroundedComposer
from module1_intake.nlp.understanding.providers import OllamaProvider
from shared.db.importer import read_ledger
from tests.integration.test_module2_core import postgres_repo
from tests.integration.test_module3_real_e2e import ddinter, findings


ROOT = Path(__file__).resolve().parents[2]
PANADOL_ID = 'PC_43a0331111c5b1d01282b18e'
ALLTREX_ID = 'PC_74a2c1a855efd9c665d41578'
TARGETS = {'DDInter14', 'DDInter1174'}
PANADOL_TEXT = 'Vui lòng lưu thuốc tên "Panadol Viên Sủi", hàm lượng 500mg, dạng viên sủi, mỗi sáng một viên.'
ALLTREX_TEXT = 'Tôi đang uống Alltrex 2,5mg, dạng viên nén.'
PAIR_TEXT = PANADOL_TEXT.rstrip('.') + '; ' + ALLTREX_TEXT
LABELLED_REPORT = ('Tôi đang uống thuốc tên "Panadol Viên Sủi", hàm lượng 500mg, dạng viên sủi, mỗi sáng một viên; '
                   'Tôi đang uống thuốc tên "Alltrex", hàm lượng 2,5mg, dạng viên nén.')
REAL_QWEN = pytest.mark.skipif(os.environ.get('NLP_RUN_REAL_OLLAMA') != '1', reason='Opt-in real local Qwen')


def emit(label, payload):
    print('\n' + label + ': ' + json.dumps(payload, ensure_ascii=False, default=str), flush=True)


def reference_fingerprint(repo):
    return [repo._one(f"SELECT count(*) AS n,md5(string_agg(to_jsonb(t)::text,'' ORDER BY id)) AS hash FROM msa_ref.{table} t")
            for table in ('medications', 'ingredients', 'medication_ingredients', 'ddinter_mappings')]


@pytest.fixture
def case(postgres_repo, ddinter):
    repo = postgres_repo
    ledger = read_ledger(repo.db)
    builds = repo._all('SELECT dataset_build,count(*) AS n FROM msa_ref.medications GROUP BY dataset_build')
    build = next((b['dataset_build'] for b in builds if b['n'] == 10670
                  and ledger['builds'].get(b['dataset_build'], {}).get('published')
                  and ledger['builds'][b['dataset_build']].get('synthetic') is False), None)
    assert build, 'Existing published real Core build required; no import is performed'
    products = repo._all('SELECT * FROM msa_ref.medications WHERE dataset_build=%s AND source_medication_id=ANY(%s)',
                         (build, [PANADOL_ID, ALLTREX_ID]))
    assert {p['source_medication_id'] for p in products} == {PANADOL_ID, ALLTREX_ID}
    before = reference_fingerprint(repo)
    schema = repo._all("SELECT nspname,obj_description(oid,'pg_namespace') AS metadata FROM pg_namespace WHERE nspname IN ('msa','msa_ref','identity') ORDER BY nspname")
    emit('TEST_DATABASE', {'database': repo.db.info.dbname, 'owner': repo.owner, 'real_build': build})
    yield repo, build, {p['source_medication_id']: p for p in products}, ddinter
    assert reference_fingerprint(repo) == before
    assert read_ledger(repo.db) == ledger
    assert repo._all("SELECT nspname,obj_description(oid,'pg_namespace') AS metadata FROM pg_namespace WHERE nspname IN ('msa','msa_ref','identity') ORDER BY nspname") == schema


def app_for(case):
    repo, build, _, dataset = case
    return ApplicationService(repo, OllamaProvider(
        os.environ.get('NLP_OLLAMA_MODEL', 'qwen3.5:9b'),
        timeout=float(os.environ.get('NLP_OLLAMA_TIMEOUT', '120'))),
        dataset_build=build, dataset=dataset, data_context='SYNTHETIC_TEST',
        composer=GroundedComposer())


def send(app, response, text):
    return app.send(TurnRequest(workflow_id=response.workflow_id, revision=response.revision, text=text))


def counts(repo):
    return {table: repo._one(f'SELECT count(*) AS n FROM msa.{table} WHERE user_id=%s', (repo.owner,))['n']
            for table in ('entry_matches', 'medication_list_snapshots', 'safety_assessments', 'safety_findings')}


def review_trace(response):
    return {'workflow_id': response.workflow_id, 'revision': response.revision, 'state': response.state,
            'error_code': response.error_code, 'intents': response.active_intents,
            'assistant': response.assistant_message,
            'entries': [{'entry_id': e.entry_version_id, 'confirmed': e.confirmed,
                         **e.medication.model_dump(mode='json')} for e in response.entries]}


def assert_ddinter_csv(dataset):
    source = dataset.lookup('DDInter14', 'DDInter1174')
    assert source['status'] == 'INTERACTION_DETECTED' and source['original_level'] == 'Moderate'
    expected = {'DDInterID_A': 'DDInter14', 'Drug_A': 'Acetaminophen',
                'DDInterID_B': 'DDInter1174', 'Drug_B': 'Methotrexate', 'Level': 'Moderate'}
    record, = source['source_records']
    evidence = record['evidence']
    path = ROOT / 'data/DDInter' / evidence['filename']
    assert hashlib.sha256(path.read_bytes()).hexdigest() == evidence['csv_sha256']
    with path.open(encoding='utf-8-sig', newline='') as stream:
        raw = next(row for number, row in enumerate(csv.DictReader(stream), 1)
                   if number == evidence['csv_record_1_based'])
    assert raw == record['raw_source_row'] == expected
    return record


def test_pair_matches_original_ddinter_csv(ddinter):
    emit('DDINTER_SOURCE_ORACLE', assert_ddinter_csv(ddinter))


def confirm_identify_assess(app, response, case, route):
    repo, build, products, dataset = case
    emit(route + '_REVIEW_BEFORE_CONFIRM', review_trace(response))
    assert response.state == 'AWAITING_CONFIRMATION' and response.error_code is None
    assert len(response.entries) == 2 and not any(e.confirmed for e in response.entries)
    assert not any(counts(repo).values())
    for action in ('IDENTIFY', 'ASSESS'):
        with pytest.raises(ValueError, match='confirmation'):
            app.execute(WorkflowActionRequest(workflow_id=response.workflow_id, revision=response.revision,
                request_key=uuid4(), action=action, explicit_request=True))
    emit(route + '_BEFORE_CONFIRM_COUNTS', counts(repo))
    response = app.confirm(ConfirmationRequest(workflow_id=response.workflow_id, revision=response.revision,
        request_key=uuid4(), explicit_confirmation=True))
    assert response.state == 'COMPLETED' and all(e.confirmed for e in response.entries)
    assert not any(counts(repo).values()), 'Confirmation must not perform identification or safety'
    handoff = app.handoff(response.workflow_id)
    response = app.execute(WorkflowActionRequest(workflow_id=response.workflow_id, revision=response.revision,
        request_key=uuid4(), action='IDENTIFY', explicit_request=True))
    module2 = response.identification_results
    emit(route + '_MODULE2', [{'input': r['original_medication'], 'status': r['identification_status'],
        'candidate': (r.get('identified_candidate') or {}).get('source_medication_id'),
        'core_medication_id': (r.get('identified_candidate') or {}).get('id'),
        'ingredients': [{key: i.get(key) for key in ('normalized_ingredient', 'ddinter_id', 'mapping_status')}
                        for i in r['ingredients']]} for r in module2])
    assert all(r['identification_status'] == 'VERIFIED' and r['ready_for_identifier_handoff'] for r in module2)
    assert {r['identified_candidate']['source_medication_id'] for r in module2} == set(products)
    assert {r['identified_candidate']['id'] for r in module2} == {str(p['id']) for p in products.values()}
    assert {identifier for r in module2 for identifier in r['verified_ddinter_ids']} == TARGETS
    assert counts(repo)['safety_assessments'] == 0
    response = app.execute(WorkflowActionRequest(workflow_id=response.workflow_id, revision=response.revision,
        request_key=uuid4(), action='ASSESS', explicit_request=True))
    assert response.assessment_id and response.executed_action == 'ASSESS'
    saved = repo._owned('safety_assessments', response.assessment_id)
    assert saved['execution_status'] == 'COMPLETED'
    assert saved['check_results']['ddi']['coverage'] == 'PARTIAL'
    assert {row['entry_version_id'] for row in repo.snapshot_context(response.snapshot_id)} == {
        e.entry_version_id for e in handoff.entries}
    ddi = [row for row in findings(repo, saved) if row['finding_type'] == 'DDI']
    assert ddi and all(row['source_severity'] == 'Moderate' for row in ddi)
    oracle = assert_ddinter_csv(dataset)
    assert any(source['record']['raw_source_row'] == oracle['raw_source_row']
               and source['artifact_sha256'] == oracle['evidence']['csv_sha256']
               and set(source['target_ids']) == TARGETS
               for row in ddi for source in row['evidence']['sources'])
    emit(route + '_MODULE3', {'workflow': response.workflow_id, 'assessment': response.assessment_id,
        'snapshot': response.snapshot_id, 'execution': saved['execution_status'],
        'coverage': saved['check_results']['ddi']['coverage'], 'source_severity': [r['source_severity'] for r in ddi],
        'source_record': oracle['evidence'], 'confirmed_entry_ids': [e.entry_version_id for e in handoff.entries]})
    return response


@REAL_QWEN
def test_typed_qwen_through_real_core_modules_1_2_3(case):
    app = app_for(case)
    current = app.start(task=Intent.ADD_MEDICATION)
    current = send(app, current, LABELLED_REPORT)
    confirm_identify_assess(app, current, case, 'TYPED')


@REAL_QWEN
def test_voice_reviewed_name_reaches_module2_then_real_ddinter(case, monkeypatch):
    repo, _, products, _ = case
    monkeypatch.setattr(api, '_asr', WhisperASR(model_size=os.environ.get('WHISPER_MODEL_SIZE', 'small'),
                                             device='cpu', compute_type='int8'))
    real_transcribe = api.transcribe_voice
    def observe_real_asr(*args, **kwargs):
        result = real_transcribe(*args, **kwargs)
        emit('VOICE_WHISPER_BEFORE_PERSIST', result)
        return result
    monkeypatch.setattr(api, 'transcribe_voice', observe_real_asr)
    app = app_for(case)
    current = app.start(task=Intent.ADD_MEDICATION)
    try:
        view = app.preview_voice(VoiceRequest(workflow_id=current.workflow_id, revision=current.revision,
            audio_payload=(ROOT / 'data/samples/voice/panadol_vi_tts.wav').read_bytes(), language='vi-VN'))
    except Exception as error:
        # Preserve a failing E2E regression instead of bypassing Core's binary guard.
        restored = app.resume_voice(current.workflow_id)
        assert restored.draft is None
        with pytest.raises(ValueError, match='draft'):
            app.edit_voice(VoiceEditRequest(workflow_id=current.workflow_id, revision=restored.revision,
                draft_id=uuid4(), text=PANADOL_TEXT))
        emit('VOICE_STOPPED_BEFORE_REVIEW', {'error_type': type(error).__name__,
            'error': str(error).splitlines()[0], 'draft': None, 'can_edit_existing_draft': False,
            'downstream_counts': counts(repo)})
        raise
    assert view.draft and not view.error_code
    original = view.draft.raw_transcript
    emit('VOICE_WHISPER_BEFORE_EDIT', {'raw_transcript': original, 'confidence': view.draft.confidence_score,
                                      'synthetic_wav': True})
    assert not app.resume(current.workflow_id).entries
    assert not any(counts(repo).values())
    view = app.edit_voice(VoiceEditRequest(workflow_id=view.workflow_id, revision=view.revision,
        draft_id=view.draft.draft_id, text=PANADOL_TEXT))
    assert view.draft.raw_transcript == original and view.draft.text == PANADOL_TEXT
    assert not any(counts(repo).values())
    current = app.submit_voice(VoiceSubmitRequest(workflow_id=view.workflow_id, revision=view.revision,
        draft_id=view.draft.draft_id, explicit_confirmation=True))
    emit('VOICE_EDITED_EXTRACTION', review_trace(current))
    assert len(current.entries) == 1 and not current.entries[0].confirmed
    assert current.entries[0].medication.name_raw == 'Panadol Viên Sủi'
    # The WAV names only one medication. The second medication is explicitly typed
    # by the test user; never label it as something Whisper heard.
    current = send(app, current, ALLTREX_TEXT)
    response = confirm_identify_assess(app, current, case, 'VOICE_PLUS_TYPED_SECOND_DRUG')
    first = next(r for r in response.identification_results
                 if r['identified_candidate']['source_medication_id'] == PANADOL_ID)
    assert first['original_medication']['name_raw'].casefold() == products[PANADOL_ID]['brand_name'].casefold()
    inputs = first['input_evidence']['inputs']
    voiced = next(row for row in inputs if row['payload_or_locator'].get('input_source') == 'VOICE')
    assert voiced['payload_or_locator']['voice']['raw_transcript'] == original
    assert voiced['payload_or_locator']['text'] == PANADOL_TEXT
    original_input = repo._owned('intake_inputs', view.draft.audio_input_id)
    assert original_input['modality'] == 'TEXT'
    assert original_input['input_digest'] == hashlib.sha256(original.encode('utf-8')).hexdigest()
    payload = original_input['payload_or_locator']
    assert payload['audio_retained'] is False and 'object_locator' not in payload
    assert payload['audio_sha256'] == hashlib.sha256((ROOT / 'data/samples/voice/panadol_vi_tts.wav').read_bytes()).hexdigest()
    emit('VOICE_PROVENANCE_AT_MODULE2', {'raw': original, 'reviewed': voiced['payload_or_locator']['text'],
                                       'audio_input_id': view.draft.audio_input_id})


def test_manual_selected_nonfirst_product_through_real_modules_1_2_3(case, monkeypatch):
    repo, _, products, _ = case
    monkeypatch.setattr(api, '_suggester', None)
    api.init_suggester(ROOT / 'data/datasets')
    app = app_for(case)
    current = app.start(task=Intent.ADD_MEDICATION)
    selected = []
    for source_id, query in ((PANADOL_ID, 'panadol'), (ALLTREX_ID, 'alltrex')):
        choices = api.suggest_medication_names(query, limit=100)
        # Explicit test-user choice by source ID, never choices[0].
        choice, = [row for row in choices if row['medication_id'] == source_id]
        if source_id == PANADOL_ID:
            assert choices.index(choice) > 0
        assert choice['brand_name'] == products[source_id]['brand_name']
        assert choice['dosage_form'] == products[source_id]['dosage_form']
        selected.append({'query': query, 'selected_by_source_id': source_id, 'choice': deepcopy(choice),
                         'suggested_ids': [row['medication_id'] for row in choices]})
        form = Medication(name_raw=choice['brand_name'], strength_raw='500 mg' if source_id == PANADOL_ID else '2,5mg',
            dosage_form_raw=choice['dosage_form'], dose_raw='2 viên',
            administrations=[Administration(timing_raw='mỗi sáng', dose_raw='2 viên')],
            evidence_text=f"{choice['brand_name']}, 2 viên mỗi sáng")
        current = app.save_manual(ManualInputRequest(workflow_id=current.workflow_id, revision=current.revision,
            source_medication_id=source_id, medication=form))
        assert source_id in current.assistant_message and str(products[source_id]['id']) in current.assistant_message
        assert not any(counts(repo).values()) and not any(e.confirmed for e in current.entries)
        # Explicit form edit creates a new version and invalidates the old review.
        old = current
        form = form.model_copy(update={'dose_raw': 'một viên',
            'administrations': [Administration(timing_raw='mỗi sáng', dose_raw='một viên')],
            'evidence_text': f"{choice['brand_name']}, một viên mỗi sáng"})
        current = app.save_manual(ManualEditRequest(workflow_id=current.workflow_id, revision=current.revision,
            entry_version_id=current.entries[-1].entry_version_id, source_medication_id=source_id, medication=form))
        assert current.entries[-1].entry_version_id != old.entries[-1].entry_version_id
        assert current.entries[-1].medication.dose_raw == 'một viên'
        with pytest.raises(ValueError, match='Stale'):
            app.confirm(ConfirmationRequest(workflow_id=old.workflow_id, revision=old.revision,
                request_key=uuid4(), explicit_confirmation=True))
    emit('MANUAL_USER_SELECTIONS', selected)
    result = confirm_identify_assess(app, current, case, 'MANUAL')
    for identity in result.identification_results:
        candidate = identity['identified_candidate']
        assert identity['manual_selection']['medication_id'] == candidate['id']
        assert identity['manual_selection']['source_medication_id'] == candidate['source_medication_id']


def test_manual_duplicate_name_nonfirst_id_is_preserved(case, monkeypatch):
    repo, build, _, _ = case
    monkeypatch.setattr(api, '_suggester', None)
    api.init_suggester(ROOT / 'data/datasets')
    choices = api.suggest_medication_names('Lenalimid', limit=100)
    group = [c for c in choices if c['brand_name'].casefold() == 'lenalimid']
    assert len(group) >= 5 and len({c['medication_id'] for c in group}) == len(group)
    choice = group[1]  # Test user's explicit choice, not the highest-ranked suggestion.
    product, = repo._all('SELECT * FROM msa_ref.medications WHERE dataset_build=%s AND source_medication_id=%s',
        (build, choice['medication_id']))
    app = app_for(case)
    current = app.start(task=Intent.ADD_MEDICATION)
    current = app.save_manual(ManualInputRequest(workflow_id=current.workflow_id, revision=current.revision,
        source_medication_id=choice['medication_id'], medication=Medication(name_raw=choice['brand_name'],
            dosage_form_raw=choice['dosage_form'], evidence_text=choice['brand_name'])))
    if current.state == 'CLARIFYING':
        current = send(app, current, 'không rõ')  # User explicitly leaves strength unknown.
    assert current.state == 'AWAITING_CONFIRMATION' and not any(counts(repo).values())
    current = app.confirm(ConfirmationRequest(workflow_id=current.workflow_id, revision=current.revision,
        request_key=uuid4(), explicit_confirmation=True))
    result = app.identify(current.workflow_id, dataset_build=build)
    match, identity = result[0]
    emit('MANUAL_DUPLICATE_NAME_SELECTED', {'choice_index': choices.index(choice), 'source_id': choice['medication_id'],
        'core_id': product['id'], 'match_status': match['match_status'], 'identity_status': identity['identification_status']})
    assert identity['identified_candidate']['id'] == str(product['id'])
    assert identity['identified_candidate']['source_medication_id'] == choice['medication_id']
    assert str(match['product_id']) == str(product['id'])


def test_core_rejects_audio_without_real_retained_object(case):
    import psycopg

    repo, _, _, _ = case
    app = app_for(case)
    current = app.start(task=Intent.ADD_MEDICATION)
    workflow = app.bot.store.workflow(current.workflow_id)
    audio = (ROOT / 'data/samples/voice/panadol_vi_tts.wav').read_bytes()
    with pytest.raises(psycopg.errors.RaiseException, match='Binary input needs retained object'):
        repo.record_input(workflow['intake_session_id'], 'AUDIO', audio,
            payload={'schema': 'input.v4', 'digest_basis': 'ORIGINAL_BYTES',
                'text': 'ASR transcript without a retained audio object', 'input_source': 'VOICE'})
    assert not app.resume(current.workflow_id).entries and not any(counts(repo).values())
    emit('CORE_BINARY_CONTRACT_REPRODUCED', 'Binary input needs retained object')


@REAL_QWEN
def test_unconfirmed_qwen_pair_cannot_enter_identification_or_safety(case):
    repo, _, _, _ = case
    app = app_for(case)
    current = send(app, app.start(task=Intent.ADD_MEDICATION), PAIR_TEXT)
    emit('UNCONFIRMED_REVIEW', review_trace(current))
    assert current.state == 'AWAITING_CONFIRMATION' and not any(e.confirmed for e in current.entries)
    for action in ('IDENTIFY', 'ASSESS'):
        with pytest.raises(ValueError, match='confirmation'):
            app.execute(WorkflowActionRequest(workflow_id=current.workflow_id, revision=current.revision,
                request_key=uuid4(), action=action, explicit_request=True))
    assert not any(counts(repo).values())
    emit('UNCONFIRMED_BLOCKED', counts(repo))


@REAL_QWEN
def test_reported_use_with_strength_label_remains_medication_intake(case):
    app = app_for(case)
    current = send(app, app.start(task=Intent.ADD_MEDICATION), LABELLED_REPORT)
    emit('DECLARATIVE_STRENGTH_LABEL_ROUTING', review_trace(current))
    assert current.state == 'AWAITING_CONFIRMATION'
    assert len(current.entries) == 2 and not any(e.confirmed for e in current.entries)


@REAL_QWEN
def test_strength_question_is_read_only_with_real_qwen(case):
    repo, _, _, _ = case
    app = app_for(case)
    current = send(app, app.start(task=Intent.ADD_MEDICATION), 'Thuốc Panadol Viên Sủi có hàm lượng bao nhiêu?')
    emit('STRENGTH_QUESTION_ROUTING', review_trace(current))
    assert Intent.MEDICATION_QA in current.active_intents and Intent.ADD_MEDICATION not in current.active_intents
    assert current.entries == [] and not any(counts(repo).values())
