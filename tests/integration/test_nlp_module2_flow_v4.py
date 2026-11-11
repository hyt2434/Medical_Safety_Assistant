"""Confirmed NLP application/CLI actions on an EXISTING marked PostgreSQL fixture."""
from copy import deepcopy
import importlib.util
import os
from pathlib import Path
from uuid import uuid4

import pytest

from tests.integration.test_nlp_v4 import connection
from module1_intake.nlp.interfaces.application import (
    ApplicationService, TurnRequest, WorkflowActionRequest, ConfirmationRequest)
from module1_intake.nlp.interfaces.application_cli import run_application
from module1_intake.nlp.models import Intent, Medication, Understanding
from module1_intake.nlp.understanding.providers import MockProvider, OllamaProvider
from shared.db import CoreRepository
from shared.db.importer import read_ledger

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def setup(connection):
    owner = uuid4()
    connection.execute('INSERT INTO identity.users(id) VALUES (%s)', (owner,))
    repo = CoreRepository(connection, authenticated_owner=owner)
    ledger = read_ledger(connection)
    builds = repo._all('SELECT dataset_build,count(*) AS n FROM msa_ref.medications GROUP BY dataset_build')
    build = next((b['dataset_build'] for b in builds if b['n'] == 4 and
                  ledger['builds'].get(b['dataset_build'], {}).get('synthetic') and
                  ledger['builds'][b['dataset_build']].get('published')), None)
    if build is None:
        pytest.skip('Existing published four-product synthetic Core fixture required; no reference import is performed')
    spec = importlib.util.spec_from_file_location('nlp_module2_existing_fixtures', ROOT / 'db/tests/fixtures.py')
    fixtures = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixtures)
    return repo, build, fixtures.dataset()


def provider():
    meds = [Medication(name_raw=f'Core Fixture {n}', strength_raw='0,5g', evidence_text=f'Core Fixture {n} 0,5g')
            for n in (0, 2)]
    return MockProvider([Understanding(medications=meds).model_dump_json(),
                         Understanding().model_dump_json(), Understanding().model_dump_json()])


def turn(service, r, text):
    return service.send(TurnRequest(workflow_id=r.workflow_id, revision=r.revision, text=text))


def count(repo, table):
    assert table in {'entry_matches', 'safety_assessments', 'medication_list_snapshots'}
    return repo._one(f'SELECT count(*) AS n FROM msa.{table} WHERE user_id=%s', (repo.owner,))['n']


def confirm(service):
    r = service.start(task=Intent.ADD_MEDICATION)
    r = turn(service, r, 'Core Fixture 0 0,5g; Core Fixture 2 0,5g')
    r = turn(service, r, 'không rõ')
    r = turn(service, r, 'không rõ')
    assert r.state == 'AWAITING_CONFIRMATION'
    return turn(service, r, 'xác nhận')


def action(service, r, kind, key=None):
    return service.execute(WorkflowActionRequest(workflow_id=r.workflow_id, revision=r.revision,
        request_key=key or uuid4(), action=kind, explicit_request=True))


def test_application_identification_then_explicit_safety_and_retained_grounding(setup):
    repo, build, dataset = setup
    service = ApplicationService(repo, provider(), dataset_build=build, dataset=dataset, data_context='SYNTHETIC_TEST')
    r = confirm(service)
    assert count(repo, 'entry_matches') == count(repo, 'safety_assessments') == 0
    key = uuid4()
    r = action(service, r, 'IDENTIFY', key)
    assert [i['identification_status'] for i in r.identification_results] == ['VERIFIED', 'VERIFIED']
    assert r.identification_results[1]['mapping_status'] == 'REVIEW_REQUIRED'
    assert len(r.identification_results[1]['ingredients'][0]['ddinter_mappings']) == 2
    assert count(repo, 'safety_assessments') == count(repo, 'medication_list_snapshots') == 0
    initial_matches = count(repo, 'entry_matches')
    assert action(service, r, 'IDENTIFY', key) == r and count(repo, 'entry_matches') == initial_matches
    r = turn(service, r, 'Kiểm tra tương tác các thuốc đã xác nhận')
    assert r.assessment_id and r.snapshot_id and r.executed_action == 'ASSESS'
    assert count(repo, 'safety_assessments') == 1
    rows = repo.snapshot_context(r.snapshot_id)
    assert sum(len(row['component_context']['mapping_refs']) for row in rows) == 3
    assert 'DDI (MAJOR)' in r.assistant_message and 'coverage=PARTIAL' in r.assistant_message
    assert 'MULTIPLE_OR_INCOMPLETE_CORE_TARGETS' in r.assistant_message
    assert r.evidence_refs and all(ref.scope for ref in r.evidence_refs)
    restored = ApplicationService(repo, MockProvider(), dataset_build=build, dataset=dataset,
                                  data_context='SYNTHETIC_TEST').resume(r.workflow_id)
    assert restored == r
    with pytest.raises(PermissionError):
        ApplicationService(CoreRepository(repo.db, authenticated_owner=uuid4()), MockProvider()).resume(r.workflow_id)
    safety_key = repo._owned('safety_assessments', r.assessment_id)['request_key']
    assert action(service, r, 'ASSESS', safety_key) == r and count(repo, 'safety_assessments') == 1


def test_confirmation_revision_latest_and_exact_safety_targets_remain_enforced(setup):
    repo, build, dataset = setup
    service = ApplicationService(repo, provider(), dataset_build=build, dataset=dataset, data_context='SYNTHETIC_TEST')
    r = service.start(task=Intent.ADD_MEDICATION)
    r = turn(service, r, 'Core Fixture 0 0,5g; Core Fixture 2 0,5g')
    with pytest.raises(ValueError, match='confirmation'):
        action(service, r, 'ASSESS')
    r = turn(service, r, 'không rõ')
    r = turn(service, r, 'không rõ')
    r = turn(service, r, 'xác nhận')
    request = WorkflowActionRequest(workflow_id=r.workflow_id, revision=r.revision,
                                   request_key=uuid4(), action='ASSESS', explicit_request=True)
    with pytest.raises(ValueError, match='revision'):
        service.execute(request.model_copy(update={'revision': r.revision - 1}))
    r = action(service, r, 'ASSESS')
    snapshot = r.snapshot_id
    original = service.handoff(r.workflow_id)
    changed = deepcopy(repo._owned('medication_entry_versions', original.entries[0].entry_version_id)['medication_fields'])
    changed['strength_raw'] = '250mg'
    repo.correct_entry(original.entries[0].entry_version_id, changed)
    with pytest.raises(ValueError, match='newer version'):
        service.assess_snapshot(r.workflow_id, snapshot, dataset, request_key=uuid4())
    with pytest.raises(ValueError, match='newer version'):
        service.execute(request)
    assert count(repo, 'safety_assessments') == 1


def test_unresolved_and_missing_reference_attributes_remain_visible_in_safety(setup):
    repo, build, dataset = setup
    meds = [Medication(name_raw='Core Fixture 0', strength_raw='500mg', dosage_form_raw='viên nén',
                       evidence_text='Core Fixture 0 500mg, dạng viên nén'),
            Medication(name_raw='Unlisted Fixture', strength_raw='500mg', evidence_text='Unlisted Fixture 500mg'),
            Medication(name_raw='Core Fixture 3', strength_raw='500mg', evidence_text='Core Fixture 3 500mg')]
    service = ApplicationService(repo, MockProvider([Understanding(medications=meds).model_dump_json()]),
        dataset_build=build, dataset=dataset, data_context='SYNTHETIC_TEST')
    r = service.start(task=Intent.ADD_MEDICATION)
    r = turn(service, r, 'Core Fixture 0 500mg, dạng viên nén; Unlisted Fixture 500mg; Core Fixture 3 500mg')
    r = turn(service, r, 'không rõ')
    r = turn(service, r, 'không rõ')
    r = turn(service, r, 'xác nhận')
    r = action(service, r, 'IDENTIFY')
    assert [i['identification_status'] for i in r.identification_results] == ['REVIEW_REQUIRED', 'UNRESOLVED', 'VERIFIED']
    assert r.identification_results[2]['ingredients'][0]['ddinter_id'] is None
    assert 'SUPPLIED_QUALIFIER_MISSING_IN_REFERENCE' in r.assistant_message
    assert count(repo, 'safety_assessments') == 0
    r = action(service, r, 'ASSESS')
    assert r.assessment_id and 'coverage=UNASSESSED' in r.assistant_message
    findings = repo._all('SELECT * FROM msa.safety_findings WHERE assessment_id=%s', (r.assessment_id,))
    assert findings and all(f['finding_type'] == 'UNRESOLVED' for f in findings)


def cli_conversation(setup, inference, *, save=False):
    repo, build, dataset = setup
    service = ApplicationService(repo, inference, dataset_build=build, dataset=dataset, data_context='SYNTHETIC_TEST')
    inputs = iter(['Tôi đang uống Core Fixture 0 0,5g; đang dùng Core Fixture 2 0,5g',
                   'không rõ', 'không rõ', 'xác nhận', 'Nhận diện các thuốc đã xác nhận',
                   'Kiểm tra tương tác các thuốc đã xác nhận', '/safety-answer', '/json', '/exit'])
    output = []

    def read(prompt):
        text = next(inputs)
        if text == 'Nhận diện các thuốc đã xác nhận':
            assert count(repo, 'entry_matches') == count(repo, 'safety_assessments') == 0
        if text == 'Kiểm tra tương tác các thuốc đã xác nhận':
            assert count(repo, 'entry_matches') > 0 and count(repo, 'safety_assessments') == 0
        output.append(prompt + text)
        return text
    run_application(service, service.start(task=Intent.ADD_MEDICATION), read=read, write=output.append)
    transcript = '\n'.join(output)
    if save:
        folder = ROOT / 'artifacts/nlp_module2'
        folder.mkdir(parents=True, exist_ok=True)
        (folder / 'cli_conversation.txt').write_text(transcript + '\n', encoding='utf-8')
    assert 'Request rejected' not in transcript
    assert 'identity=VERIFIED' in transcript and 'mapping=REVIEW_REQUIRED' in transcript
    assert 'DDI (MAJOR)' in transcript and 'coverage=PARTIAL' in transcript
    assert 'msa_ref.medications/' in transcript and 'msa.safety_findings/' in transcript
    assert 'module2.medication_identity.v1' in transcript
    assert count(repo, 'safety_assessments') == 1
    return transcript


def test_cli_conversation_with_existing_postgres_and_mock_extraction(setup):
    cli_conversation(setup, provider())


def test_real_qwen_cli_confirmation_identification_safety_and_grounding(setup):
    if os.environ.get('NLP_RUN_REAL_OLLAMA') != '1':
        pytest.skip('Real Qwen opt-in NLP_RUN_REAL_OLLAMA=1 required')
    inference = OllamaProvider(os.environ.get('NLP_OLLAMA_MODEL', 'qwen3.5:9b'),
        base_url=os.environ.get('NLP_OLLAMA_URL', 'http://127.0.0.1:11434'),
        timeout=float(os.environ.get('NLP_OLLAMA_TIMEOUT', '120')))
    transcript = cli_conversation(setup, inference, save=os.environ.get('NLP_SAVE_CLI_TRANSCRIPT') == '1')
    assert 'QWEN_GROUNDED_SELECTION' in transcript
