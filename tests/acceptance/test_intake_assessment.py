"""MAN-xx (manual intake, catalog, edits) and VER-xx (confirmation, identification, assessment)."""
import uuid

import pytest

from tests.acceptance.conftest import (
    SET_DUPLICATE, SET_MAJOR, SET_MODERATE, SET_NONE, add_manual, assess, confirm, details, findings,
    intake, product, start_workflow,
)


def coverage(c, wf):
    a = details(c, wf)['assessment']
    return {k: v.get('coverage') for k, v in a['check_results'].items() if isinstance(v, dict)}


def statuses(wf):
    return [r.get('core_match_status') for r in wf.get('identification_results', [])]


# ---------- catalog ----------

def test_man01_persistent_intake_available(patient):
    assert patient.get('/api/v1/intake/capabilities').json() == {'persistent_intake': True}


def test_man02_catalog_search_returns_full_product_identity(patient):
    rows = patient.get('/api/reference/medications', params={'q': 'Hatacil 500'}).json()['medications']
    row = next(r for r in rows if r['brand_name'] == 'Hatacil 500')
    assert row['dosage_form'] and row['manufacturer'] and row['source_medication_id'] and row['dataset_build']
    assert 'Clarithromycin' in row['components'][0]['ingredient_text_raw']


def test_man03_ambiguous_brand_returns_several_products(patient):
    names = [r['brand_name'] for r in patient.get('/api/reference/medications', params={'q': 'Panadol'}).json()['medications']]
    assert len(names) >= 2


@pytest.mark.parametrize('query', ['xyzabc123', "'; DROP TABLE x;--"])
def test_man04_no_match_returns_empty(patient, query):
    r = patient.get('/api/reference/medications', params={'q': query})
    assert r.status_code == 200
    assert r.json()['medications'] == []


@pytest.mark.parametrize('char', ['%', '_'])
def test_man04_wildcards_are_matched_literally(patient, char):
    rows = patient.get('/api/reference/medications', params={'q': char}).json()['medications']
    assert all(char in r['brand_name'] for r in rows)


def test_man09_spelling_suggestion_for_misspelled_name(patient):
    r = patient.get('/api/reference/medication-spelling', params={'q': 'Paracetamoll', 'strength': '500mg'})
    assert r.status_code == 200
    assert [s['name'] for s in r.json()['suggestions']] == ['Paracetamol']


def test_man09_exact_name_is_not_corrected(patient):
    r = patient.get('/api/reference/medication-spelling', params={'q': 'Paracetamol', 'strength': '500mg'})
    assert r.json()['suggestions'] == []


# ---------- manual draft ----------

def test_man05_06_manual_entries_keep_catalog_selection(patient):
    wf = start_workflow(patient)
    assert wf['state'] == 'COLLECTING'
    wf = add_manual(patient, wf, 'Hatacil 500')
    wf = add_manual(patient, wf, 'DOMESIM 20 mg')
    assert wf['state'] == 'AWAITING_CONFIRMATION'
    assert [e['medication']['name_raw'] for e in wf['entries']] == ['Hatacil 500', 'DOMESIM 20 mg']
    assert not any(e['confirmed'] for e in wf['entries'])
    sources = details(patient, wf)['entry_sources'].values()
    assert {s['input_source'] for s in sources} == {'MANUAL'}
    assert {s['selected_product']['brand_name'] for s in sources} == {'Hatacil 500', 'DOMESIM 20 mg'}


def test_man_missing_strength_triggers_clarification_not_guessing(patient):
    wf = start_workflow(patient)
    p = product(patient, 'Hatacil 500')
    r = patient.post('/api/v1/intake/manual', json={
        'workflow_id': wf['workflow_id'], 'revision': wf['revision'],
        'source_medication_id': p['source_medication_id'], 'dataset_build': p['dataset_build'],
        'medication': {'name_raw': 'Hatacil 500', 'dose_raw': '1 viên', 'evidence_text': 'Hatacil 500, 1 viên'}})
    assert r.status_code == 200
    body = r.json()
    assert body['state'] == 'CLARIFYING'
    assert 'hàm lượng' in body['assistant_message'].lower()
    assert body['entries'][0]['medication'].get('strength_raw') in (None, '')


def test_man07_edit_entry_creates_new_revision_and_persists(patient):
    wf = intake(patient, ['Vascam'], do_confirm=False, do_assess=False)
    entry = wf['entries'][0]
    medication = {**entry['medication'], 'dose_raw': '2 viên'}
    medication = {k: v for k, v in medication.items() if k != 'schema'}
    r = patient.post('/api/v1/intake/entries/edit', json={
        'workflow_id': wf['workflow_id'], 'revision': wf['revision'],
        'entry_version_id': entry['entry_version_id'], 'medication': medication})
    assert r.status_code == 200, r.text
    edited = r.json()
    assert edited['revision'] > wf['revision']
    assert edited['entries'][0]['medication']['dose_raw'] == '2 viên'
    assert edited['entries'][0]['entry_version_id'] != entry['entry_version_id']
    reloaded = patient.get(f"/api/v1/intake/workflows/{wf['workflow_id']}").json()
    assert reloaded['entries'][0]['medication']['dose_raw'] == '2 viên'


def test_man_unknown_catalog_product_is_rejected(patient):
    wf = start_workflow(patient)
    p = product(patient, 'Vascam')
    r = patient.post('/api/v1/intake/manual', json={
        'workflow_id': wf['workflow_id'], 'revision': wf['revision'],
        'source_medication_id': 'PC_does_not_exist', 'dataset_build': p['dataset_build'],
        'medication': {'name_raw': 'Vascam', 'strength_raw': '5mg', 'evidence_text': 'Vascam 5mg'}})
    assert r.status_code in (404, 409, 422), r.text


def test_man_other_roles_cannot_open_patient_workflow(patient, hcp):
    wf = start_workflow(patient)
    assert hcp.get(f"/api/v1/intake/workflows/{wf['workflow_id']}").status_code == 403


# ---------- confirmation ----------

def test_ver02_confirmation_requires_explicit_consent(patient):
    wf = intake(patient, ['Vascam'], do_confirm=False, do_assess=False)
    r = patient.post('/api/v1/intake/confirm', json={'workflow_id': wf['workflow_id'], 'revision': wf['revision'],
                                                     'request_key': str(uuid.uuid4()), 'explicit_confirmation': False})
    assert r.status_code in (409, 422)
    assert patient.get(f"/api/v1/intake/workflows/{wf['workflow_id']}").json()['state'] == 'AWAITING_CONFIRMATION'


def test_ver04_confirm_marks_every_entry_confirmed(patient):
    wf = intake(patient, SET_MODERATE, do_assess=False)
    assert wf['state'] == 'COMPLETED'
    assert all(e['confirmed'] for e in wf['entries'])
    assert wf['authorization_scope'] == 'TRANSCRIPTION_ONLY'


def test_ver05_stale_revision_cannot_be_confirmed(patient):
    wf = intake(patient, ['Vascam'], do_confirm=False, do_assess=False)
    stale = dict(wf)
    add_manual(patient, wf, 'Ibu Hera 400')  # another tab changed the draft
    r = patient.post('/api/v1/intake/confirm', json={'workflow_id': stale['workflow_id'], 'revision': stale['revision'],
                                                     'request_key': str(uuid.uuid4()), 'explicit_confirmation': True})
    assert r.status_code == 409


def test_ver06_assessment_requires_confirmation(patient):
    wf = intake(patient, SET_NONE, do_confirm=False, do_assess=False)
    r = patient.post('/api/v1/intake/actions', json={'workflow_id': wf['workflow_id'], 'revision': wf['revision'],
                                                     'request_key': str(uuid.uuid4()), 'action': 'ASSESS',
                                                     'explicit_request': True})
    assert r.status_code == 409 or r.json().get('assessment_id') is None


# ---------- assessment outcomes ----------

def test_ver07_no_interaction_set_is_not_reported_as_complete_safety(patient):
    wf = intake(patient, SET_NONE)
    assert statuses(wf) == ['SELECTED', 'SELECTED']
    assert findings(patient, wf) == []
    cov = coverage(patient, wf)
    assert cov['ddi'] == 'PARTIAL', 'interaction coverage must never be claimed complete'
    limitations = details(patient, wf)['assessment']['check_results']['ddi']['limitations']
    assert 'Loaded interaction coverage is not exhaustive' in limitations


def test_ver08_major_interaction_is_flagged_with_source_evidence(patient):
    wf = intake(patient, SET_MAJOR)
    assert statuses(wf) == ['SELECTED', 'SELECTED']
    assert ('DDI', 'MAJOR') in findings(patient, wf)
    finding = next(f for f in details(patient, wf)['assessment']['findings'] if f['finding_type'] == 'DDI')
    source = finding['evidence']['sources'][0]
    assert source['source_severity'] == 'Major'
    assert len(source['artifact_sha256']) == 64
    assert finding['evidence']['reminder_hold']['required'] is True


def test_ver09_moderate_interaction(patient):
    wf = intake(patient, SET_MODERATE)
    assert ('DDI', 'MODERATE') in findings(patient, wf)


def test_ver10_duplicate_ingredient(patient):
    wf = intake(patient, SET_DUPLICATE)
    assert ('DUPLICATE_INGREDIENT', 'UNKNOWN') in findings(patient, wf)


def test_ver11_ambiguous_strength_is_not_auto_resolved(patient):
    """Somecid's label strength (pellet 7.5% … 20 mg) needs human review: no silent selection."""
    wf = intake(patient, ['Hatacil 500', 'Somecid'])
    assert statuses(wf)[1] == 'AMBIGUOUS'
    assert ('UNRESOLVED', 'UNKNOWN') in findings(patient, wf)
    assert coverage(patient, wf)['ddi'] != 'ASSESSED'


def test_ver12_single_medication_only_identifies(patient):
    """Observed behaviour: ASSESS on one medication runs identification only (no assessment record)."""
    wf = intake(patient, ['Agigout 100'])
    assert wf['executed_action'] == 'IDENTIFY'
    assert wf['assessment_id'] is None
    assert statuses(wf) == ['SELECTED']


def test_ver13_same_request_key_reuses_the_assessment(patient):
    wf = intake(patient, SET_MODERATE, do_assess=False)
    key = str(uuid.uuid4())
    first, second = assess(patient, wf, key), assess(patient, wf, key)
    assert first['assessment_id'] == second['assessment_id']


def test_ver14_revise_after_confirmation_requires_new_confirmation(patient):
    wf = intake(patient, SET_MAJOR)
    old_assessment = wf['assessment_id']
    r = patient.post(f"/api/v1/intake/workflows/{wf['workflow_id']}/revise", json={'revision': wf['revision']})
    assert r.status_code == 200, r.text
    revised = r.json()
    # A correction opens a new workflow that carries the medications forward.
    assert revised['workflow_id'] != wf['workflow_id']
    assert revised['state'] != 'COMPLETED'
    assert [e['medication']['name_raw'] for e in revised['entries']] == SET_MAJOR
    original = patient.get(f"/api/v1/intake/workflows/{wf['workflow_id']}").json()
    assert original['state'] == 'COMPLETED', 'the confirmed original stays immutable'
    corrected = edit_dose(patient, revised, 0, '2 viên')
    assert corrected['state'] == 'AWAITING_CONFIRMATION'
    again = assess(patient, confirm(patient, corrected))
    assert again['assessment_id'] and again['assessment_id'] != old_assessment
    assert ('DDI', 'MAJOR') in findings(patient, again)


def edit_dose(c, wf, index, dose):
    entry = wf['entries'][index]
    medication = {k: v for k, v in entry['medication'].items() if k != 'schema'}
    r = c.post('/api/v1/intake/entries/edit', json={
        'workflow_id': wf['workflow_id'], 'revision': wf['revision'],
        'entry_version_id': entry['entry_version_id'], 'medication': {**medication, 'dose_raw': dose}})
    assert r.status_code == 200, r.text
    return r.json()
