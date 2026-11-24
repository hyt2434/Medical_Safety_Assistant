"""Synthetic source adapters over real Core V4; no OCR/manual implementation is assumed.

The small review driver below models an explicit owner action against a persisted
display/revision. It never updates confirmation columns or generates identities.
"""
import base64
from copy import deepcopy
import hashlib
import json
from uuid import uuid4

import psycopg
import pytest

from shared.db import CoreRepository
from shared.db.importer import read_ledger
from shared.db.intake_adapter import (
    medication_fields, persist_module1, build_confirmed_handoff, assert_latest_entry)
from shared.intake_contracts import Medication, Module2Handoff, ConfirmedEntry
from module2_medications import identify_confirmed
from tests.integration.test_module2_core import postgres_repo

SOURCES = ('CHATBOT', 'OCR', 'MANUAL')


@pytest.fixture
def setup(postgres_repo):
    ledger = read_ledger(postgres_repo.db)
    builds = postgres_repo._all('SELECT dataset_build,count(*) AS n FROM msa_ref.medications GROUP BY dataset_build')
    build = next((b['dataset_build'] for b in builds if b['n'] == 4 and
                  ledger['builds'].get(b['dataset_build'], {}).get('synthetic') and
                  ledger['builds'][b['dataset_build']].get('published')), None)
    if build is None:
        pytest.skip('Existing published four-product Core fixture required; no new reference build is imported')
    return postgres_repo, build


def persist_source(repo, kind, medications, folder, *, workflow=None, correction=None):
    """Explicit invented extraction, retaining actual fixture bytes and supplied metadata."""
    if workflow is None:
        conversation = repo.create_conversation()
        intake = repo.create_intake(conversation['id'])
        workflow = repo.create_workflow(conversation['id'], 'MEDICATION_INTAKE', intake=intake['id'])
    fields = [m.model_dump() for m in medications]
    payload = {'schema': 'input.v4', 'digest_basis': 'ORIGINAL_BYTES', 'source_kind': kind,
               'synthetic_fixture': True}
    text = '\n'.join(m.evidence_text for m in medications)
    if kind == 'OCR':
        # Authored one-pixel PNG: this test exercises a synthetic extraction, not OCR accuracy.
        original = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a7x8AAAAASUVORK5CYII=')
        image = folder / (str(uuid4()) + '.png')
        image.write_bytes(original)
        payload['object_locator'] = {'uri': image.as_uri(), 'sha256': hashlib.sha256(original).hexdigest(),
                                     'object_version': 'synthetic-source-v1'}
        modality, content_type = 'IMAGE', 'image/png'
        locators = [{'page': 1, 'bbox': [0, 0, 1, 1], 'coordinate_space': 'pixel',
                     'confidence': 0.43, 'synthetic_extraction': True} for _ in medications]
    elif kind == 'MANUAL':
        form = {'medications': fields, 'form_version': 'synthetic-form-v1'}
        original = json.dumps(form, ensure_ascii=False).encode('utf-8')
        payload['manual_fields'] = form
        modality, content_type = 'MANUAL', 'application/json'
        locators = [{'form_version': 'synthetic-form-v1', 'row_index': n,
                     'field_paths': ['name_raw', 'strength_raw', 'dosage_form_raw']} for n, _ in enumerate(medications)]
    else:
        original = text.encode('utf-8')
        payload['text'] = text
        modality, content_type = 'TEXT', 'text/plain; charset=utf-8'
        locators = [{'line': n, 'synthetic_extraction': True} for n, _ in enumerate(medications, 1)]
    extraction = {'schema': 'extraction.v4', 'medications': fields,
                  'warnings': ['Explicit synthetic extraction; requires owner review'], 'document_instructions_raw': []}
    options = {'extractor_name': 'synthetic-' + kind.lower(), 'extractor_version': 'source-contract-v1'}
    if correction is None:
        saved = persist_module1(repo, workflow['intake_session_id'], original, extraction,
            modality=modality, content_type=content_type, input_payload=payload, item_locators=locators, **options)
        rows = saved['entries']
    else:
        inp = repo.record_input(workflow['intake_session_id'], modality, original, payload=payload, content_type=content_type)
        attempt = repo.record_extraction(inp['id'], options['extractor_name'], options['extractor_version'],
            {**extraction, 'medications': [medication_fields(m) for m in fields]})
        rows = [repo.correct_entry(correction['id'], medication_fields(fields[0]), source_extraction=attempt['id'])]
        saved = {'input': inp, 'extraction': attempt, 'entries': rows, 'requires_user_review': True}
    return display_review(repo, workflow, rows), saved, original, payload, locators


def display_review(repo, workflow, rows):
    ctx = deepcopy(workflow['context'])
    displayed = [{'id': str(r['id']), 'content_digest': r['content_digest']} for r in rows]
    message = repo.append_message(workflow['conversation_id'], 'ASSISTANT',
        json.dumps([r['medication_fields'] for r in rows], ensure_ascii=False))
    revision = workflow['revision'] + 1
    ctx.update(entry_version_ids=[r['id'] for r in displayed], requested_workflows=['MEDICATION_INTAKE'],
        draft={'draft_revision': revision, 'display_message_id': str(message['id']), 'entries': displayed},
        pending_confirmation={'draft_revision': revision, 'display_message_id': str(message['id']),
            'payload_digest': repo.digest(displayed), 'entry_version_ids': [r['id'] for r in displayed]})
    workflow = repo.transition_workflow(workflow['id'], 'AWAITING_CONFIRMATION',
                                       expected_revision=workflow['revision'], context=ctx)
    return workflow


def confirm_review(repo, workflow, *, revision, explicit_confirmation):
    """Test-only review controller; every confirmation goes through Core's real guards."""
    current = repo._owned('workflow_instances', workflow['id'])
    if current['revision'] != revision:
        raise ValueError('Stale review revision')
    if current['state'] != 'AWAITING_CONFIRMATION' or explicit_confirmation is not True:
        raise ValueError('Explicit owner confirmation of a displayed review required')
    ctx = current['context']
    rows = [repo._owned('medication_entry_versions', i) for i in ctx['entry_version_ids']]
    actual = [{'id': str(r['id']), 'content_digest': r['content_digest']} for r in rows]
    if (ctx['draft']['entries'] != actual or ctx['pending_confirmation']['payload_digest'] != repo.digest(actual)
            or ctx['pending_confirmation']['draft_revision'] != revision):
        raise ValueError('Displayed digest differs from current entries')
    repo.append_message(current['conversation_id'], 'USER', 'Confirm exactly the displayed synthetic transcription')
    for row in rows:
        assert_latest_entry(repo, row)
        repo.confirm_entry(row['id'], row['content_digest'], uuid4(), explicit_confirmation=explicit_confirmation)
    return repo.transition_workflow(current['id'], 'COMPLETED', expected_revision=revision, context=ctx)


def handoff_for_unconfirmed_rows(workflow, rows):
    return Module2Handoff(conversation_id=workflow['conversation_id'], intake_id=workflow['intake_session_id'],
        requested_workflows=['MEDICATION_INTAKE'], entries=[ConfirmedEntry(entry_version_id=r['id'],
            content_digest=r['content_digest'], medication=Medication.model_validate(
                {k: v for k, v in r['medication_fields'].items() if k != 'schema'})) for r in rows])


@pytest.mark.parametrize('kind', SOURCES)
def test_all_sources_use_same_confirmation_normalization_mappings_and_real_metadata(setup, tmp_path, kind):
    repo, build = setup
    meds = [Medication(name_raw=f'Core Fixture {n}', strength_raw='0,5g', evidence_text=f'Core Fixture {n} 0,5g')
            for n in (0, 2)]
    workflow, saved, original, payload, locators = persist_source(repo, kind, meds, tmp_path)
    assert saved['requires_user_review'] and all(r['confirmed_at'] is None for r in saved['entries'])
    with pytest.raises(ValueError, match='confirmation'):
        build_confirmed_handoff(repo, workflow['id'])
    with pytest.raises(ValueError, match='unconfirmed'):
        identify_confirmed(repo, handoff_for_unconfirmed_rows(workflow, saved['entries']), dataset_build=build)
    workflow = confirm_review(repo, workflow, revision=workflow['revision'], explicit_confirmation=True)
    handoff = build_confirmed_handoff(repo, workflow['id'])
    matches = identify_confirmed(repo, Module2Handoff.model_validate_json(handoff.model_dump_json()), dataset_build=build)
    assert [m['match_status'] for m, result in matches] == ['SELECTED', 'SELECTED']
    assert [r['mapping_status'] for m, r in matches] == ['VERIFIED', 'REVIEW_REQUIRED']
    assert len(matches[1][1]['ingredients'][0]['ddinter_mappings']) == 2
    assert matches[1][1]['ingredients'][0]['ddinter_id'] is None
    for index, (match, result) in enumerate(matches):
        assert result['schema_version'] == 'module2.medication_identity.v1'
        assert result['original_medication']['strength_raw'] == '0,5g'
        assert result['identified_candidate']['product']['strength'] == '500mg'
        assert result['dataset_build'] == build and result['interaction_assessment'] == 'NOT_PERFORMED'
        evidence = result['input_evidence']
        assert evidence['origin_evidence']['locator'] == locators[index]
        assert evidence['inputs'][0]['payload_or_locator'] == payload
        assert evidence['inputs'][0]['input_digest'] == hashlib.sha256(original).hexdigest()
        assert evidence['inputs'][0]['content_type'] == saved['input']['content_type']
        assert evidence['extractions'][0]['extractor_name'] == 'synthetic-' + kind.lower()
        assert evidence['extractions'][0]['result'] == saved['extraction']['result']
        assert result['identified_candidate']['source_evidence']  # Distinct reference provenance survives.


@pytest.mark.parametrize('kind', SOURCES)
def test_missing_fields_uncertainty_and_unmatched_inputs_are_not_filled(setup, tmp_path, kind):
    repo, build = setup
    meds = [Medication(name_raw=None, strength_raw='500mg', evidence_text='500mg, name unreadable', uncertain_fields=['name_raw']),
            Medication(name_raw='Unknown Synthetic Drug', evidence_text='Unknown Synthetic Drug'),
            Medication(name_raw='Core Fixture 0', dosage_form_raw='viên nén', evidence_text='Core Fixture 0 viên nén'),
            Medication(name_raw='Core Fixture 0', evidence_text='Core Fixture 0 uncertain', uncertain_fields=['name_raw'])]
    workflow, saved, *_ = persist_source(repo, kind, meds, tmp_path)
    workflow = confirm_review(repo, workflow, revision=workflow['revision'], explicit_confirmation=True)
    results = identify_confirmed(repo, build_confirmed_handoff(repo, workflow['id']), dataset_build=build)
    assert [r['identification_status'] for m, r in results] == ['UNRESOLVED', 'UNRESOLVED', 'REVIEW_REQUIRED', 'REVIEW_REQUIRED']
    assert all(not r['ready_for_identifier_handoff'] for m, r in results)
    assert results[0][1]['original_medication']['name_raw'] is None
    assert results[1][1]['original_medication']['strength_raw'] is None
    assert 'SUPPLIED_QUALIFIER_MISSING_IN_REFERENCE' in results[2][1]['issues']
    assert results[3][1]['original_medication']['uncertain_fields'] == ['name_raw']


@pytest.mark.parametrize('kind', SOURCES)
def test_owner_revision_digest_and_explicit_confirmation_guards_for_every_source(setup, tmp_path, kind):
    repo, build = setup
    workflow, saved, *_ = persist_source(repo, kind, [Medication(name_raw='Core Fixture 0', evidence_text='Core Fixture 0')], tmp_path)
    entry = saved['entries'][0]
    with pytest.raises(ValueError, match='revision'):
        confirm_review(repo, workflow, revision=workflow['revision'] - 1, explicit_confirmation=True)
    with pytest.raises(ValueError, match='revision'):
        repo.transition_workflow(workflow['id'], 'AWAITING_CONFIRMATION',
                                 expected_revision=workflow['revision'] - 1, context=workflow['context'])
    with pytest.raises(ValueError, match='Explicit'):
        confirm_review(repo, workflow, revision=workflow['revision'], explicit_confirmation=False)
    with pytest.raises(ValueError, match='Explicit'):
        repo.confirm_entry(entry['id'], entry['content_digest'], uuid4(), explicit_confirmation=False)
    with pytest.raises(psycopg.Error):
        repo.confirm_entry(entry['id'], 'f' * 64, uuid4(), explicit_confirmation=True)
    assert repo._owned('medication_entry_versions', entry['id'])['confirmed_at'] is None
    foreign = CoreRepository(repo.db, authenticated_owner=uuid4())
    with pytest.raises(PermissionError):
        identify_confirmed(foreign, handoff_for_unconfirmed_rows(workflow, [entry]), dataset_build=build)
    workflow = confirm_review(repo, workflow, revision=workflow['revision'], explicit_confirmation=True)
    handoff = build_confirmed_handoff(repo, workflow['id'])
    other_intake = repo.create_intake(workflow['conversation_id'])
    with pytest.raises(ValueError, match='different intake'):
        identify_confirmed(repo, handoff.model_copy(update={'intake_id': other_intake['id']}), dataset_build=build)
    for corruption in ('digest', 'fields'):
        forged = handoff.model_copy(deep=True)
        if corruption == 'digest': forged.entries[0].content_digest = 'e' * 64
        else: forged.entries[0].medication.strength_raw = '250mg'
        with pytest.raises(ValueError): identify_confirmed(repo, forged, dataset_build=build)
    assert not repo._all('SELECT id FROM msa.entry_matches WHERE user_id=%s', (repo.owner,))


@pytest.mark.parametrize('kind', SOURCES)
def test_corrections_require_reverification_and_keep_original_and_current_sources(setup, tmp_path, kind):
    repo, build = setup
    workflow, saved, original, payload, *_ = persist_source(repo, kind,
        [Medication(name_raw='Unknown Synthetic Drug', evidence_text='Unknown Synthetic Drug')], tmp_path)
    workflow = confirm_review(repo, workflow, revision=workflow['revision'], explicit_confirmation=True)
    old = build_confirmed_handoff(repo, workflow['id'])
    assert identify_confirmed(repo, old, dataset_build=build)[0][1]['identification_status'] == 'UNRESOLVED'
    revised = repo.create_workflow(workflow['conversation_id'], 'MEDICATION_INTAKE', intake=workflow['intake_session_id'])
    revised, corrected, _, new_payload, *_ = persist_source(repo, 'MANUAL',
        [Medication(name_raw='Core Fixture 0', strength_raw='500mg', evidence_text='Core Fixture 0 500mg')],
        tmp_path, workflow=revised, correction=saved['entries'][0])
    with pytest.raises(ValueError, match='newer version'): identify_confirmed(repo, old, dataset_build=build)
    with pytest.raises(ValueError, match='confirmation'): build_confirmed_handoff(repo, revised['id'])
    revised = confirm_review(repo, revised, revision=revised['revision'], explicit_confirmation=True)
    result = identify_confirmed(repo, build_confirmed_handoff(repo, revised['id']), dataset_build=build)[0][1]
    assert result['identification_status'] == 'VERIFIED'
    inputs = {i['id']: i for i in result['input_evidence']['inputs']}
    assert len(inputs) == 2 and inputs[str(saved['input']['id'])]['payload_or_locator'] == payload
    assert inputs[str(corrected['input']['id'])]['payload_or_locator'] == new_payload
    assert len(result['input_evidence']['extractions']) == 2
    assert repo._owned('medication_entry_versions', saved['entries'][0]['id'])['confirmed_at'] is not None


def test_missing_correction_provenance_is_reported_instead_of_attributed_to_original(setup, tmp_path):
    repo, build = setup
    workflow, saved, *_ = persist_source(repo, 'OCR',
        [Medication(name_raw='Core Fixture 0', strength_raw='250mg', evidence_text='Core Fixture 0 250mg')], tmp_path)
    workflow = confirm_review(repo, workflow, revision=workflow['revision'], explicit_confirmation=True)
    # Core allows a correction with no extraction link. Do not pretend its changed
    # fields came from the original image or fabricate a manual-input record.
    fields = medication_fields(Medication(name_raw='Core Fixture 0', strength_raw='500mg',
                                         evidence_text='Core Fixture 0 500mg').model_dump())
    changed = repo.correct_entry(saved['entries'][0]['id'], fields)
    review = repo.create_workflow(workflow['conversation_id'], 'MEDICATION_INTAKE', intake=workflow['intake_session_id'])
    review = display_review(repo, review, [changed])
    review = confirm_review(repo, review, revision=review['revision'], explicit_confirmation=True)
    handoff = build_confirmed_handoff(repo, review['id'])
    result = identify_confirmed(repo, handoff, dataset_build=build)[0][1]
    assert result['input_evidence']['source_extraction_id'] is None
    assert result['input_evidence']['issues'] == ['CURRENT_SOURCE_EXTRACTION_NOT_RECORDED']
    assert len(result['input_evidence']['inputs']) == len(result['input_evidence']['extractions']) == 1


@pytest.mark.parametrize('kind', SOURCES)
def test_typo_candidate_requires_corrected_fresh_confirmation_before_selection(setup, tmp_path, kind):
    repo, build = setup
    workflow, saved, *_ = persist_source(repo, kind,
        [Medication(name_raw='Core Fixturre 0', strength_raw='500mg', evidence_text='Core Fixturre 0 500mg')], tmp_path)
    with pytest.raises(ValueError, match='unconfirmed'):
        identify_confirmed(repo, handoff_for_unconfirmed_rows(workflow, saved['entries']), dataset_build=build)
    workflow = confirm_review(repo, workflow, revision=workflow['revision'], explicit_confirmation=True)
    old = build_confirmed_handoff(repo, workflow['id'])
    match, result = identify_confirmed(repo, old, dataset_build=build)[0]
    assert match['match_status'] == 'AMBIGUOUS' and match['product_id'] is None
    assert result['identification_status'] == 'REVIEW_REQUIRED' and not result['ready_for_identifier_handoff']
    assert all(not c['establishes_identity'] for c in result['candidates'])
    assert result['interaction_assessment'] == 'NOT_PERFORMED'
    revised = repo.create_workflow(workflow['conversation_id'], 'MEDICATION_INTAKE', intake=workflow['intake_session_id'])
    revised, corrected, *_ = persist_source(repo, 'MANUAL',
        [Medication(name_raw='Core Fixture 0', strength_raw='500mg', evidence_text='Core Fixture 0 500mg')],
        tmp_path, workflow=revised, correction=saved['entries'][0])
    with pytest.raises(ValueError, match='newer version'):
        identify_confirmed(repo, old, dataset_build=build)
    with pytest.raises(ValueError, match='confirmation'):
        build_confirmed_handoff(repo, revised['id'])
    revised = confirm_review(repo, revised, revision=revised['revision'], explicit_confirmation=True)
    match, result = identify_confirmed(repo, build_confirmed_handoff(repo, revised['id']), dataset_build=build)[0]
    assert match['match_status'] == 'SELECTED' and result['identification_status'] == 'VERIFIED'
    assert len(result['input_evidence']['inputs']) == 2
