"""Module 1 → Module 2 → Module 3, with isolated fixtures and read-only approved CSVs."""
from collections import Counter, defaultdict
from contextlib import nullcontext
from copy import deepcopy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
from unittest.mock import patch
from uuid import uuid4

import pytest

from module1_intake.nlp.models import Medication, Understanding, Intent
from module1_intake.nlp.interfaces.application import ApplicationService, ConfirmationRequest, TurnRequest
from module1_intake.nlp.understanding.providers import MockProvider
from module1_intake.nlp.integration.handoff import assess_confirmed_snapshot
from module2_medications.core import CoreMedicationReference, identify_confirmed
from module2_medications.service import from_module1
from module3_interactions.engine import BoundedDataset, assess
from shared.db import CoreRepository
from shared.db import importer
from tests.unit.module2.test_core import ReferenceRows

ROOT = Path(__file__).resolve().parents[2]


class CapturedProjection(ReferenceRows):
    """Capture the REAL importer's COPY rows, without making a database or importing data.

    This fixture replaces only transaction/COPY/reconciliation I/O. CSV validation,
    build hashing, UUIDs, JSONB projection and source locators are production code.
    """
    def __init__(self):
        super().__init__([])
        self.tables = {}
        self.ledger = {'schema': 'ref-build-ledger.v4', 'builds': {}}

    def transaction(self):
        return nullcontext()

    def execute(self, query, params=()):
        assert 'pg_advisory_xact_lock' in query or 'msa.assert_ref_build' in query

    def cursor(self):
        return self

    def copy(self, query):
        statement = query.as_string()
        table = re.search(r'COPY msa_ref\."(\w+)"', statement)[1]
        columns = re.findall(r'"([^"]+)"', statement.split('(', 1)[1])
        rows = self.tables.setdefault(table, [])

        class Writer:
            def write_row(self, values):
                row = {c: deepcopy(v.obj) if isinstance(v, importer.Jsonb) else v for c, v in zip(columns, values)}
                for column in ('id', 'ingredient_id', 'medication_id', 'component_id'):
                    if row.get(column) is not None:
                        row[column] = str(row[column])
                rows.append(row)
        return nullcontext(Writer())

    def _one(self, query, params=()):
        if 'msa.published' in query:
            return {'ok': self.ledger['builds'].get(params[0], {}).get('published', False)}
        assert 'obj_description' in query
        return {'ledger': json.dumps(self.ledger)}


@pytest.fixture(scope='module')
def approved_projection():
    directory = ROOT / 'data/datasets'
    if not all((directory / (n + '.csv')).is_file() for n in importer.COUNTS):
        pytest.skip('Six approved local CSVs are required; no substitute dataset is used')
    before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in directory.glob('*.csv')}
    captured = CapturedProjection()
    with patch.object(importer, 'read_ledger', return_value=captured.ledger), \
         patch.object(importer, 'write_ledger'), patch.object(importer, 'reconcile', return_value={}):
        result = importer.import_datasets(captured, directory,
                                         manifest_directory=ROOT / 'artifacts/core_db_v4/manifests')
    captured.products = captured.tables['medications']
    ingredients = {i['id']: i for i in captured.tables['ingredients']}
    captured.components = [{**c, 'ingredient_record': ingredients.get(c['ingredient_id'])}
                           for c in captured.tables['medication_ingredients']]
    captured.mappings = captured.tables['ddinter_mappings']
    assert before == {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in directory.glob('*.csv')}
    return captured, result['dataset_build']


def test_approved_projection_preserves_every_mapping_and_build(approved_projection):
    repo, build = approved_projection
    assert len(repo.products) == 10670 and len(repo.components) == 12899 and len(repo.mappings) == 5675
    ref = CoreMedicationReference(repo, build)
    by_product = defaultdict(list)
    for comp in repo.components:
        by_product[comp['medication_id']].append(comp)
    names = Counter(p['brand_name'] for p in repo.products)
    # Include every product with mapping rows, including historical review flags and multi-target sets.
    mapped_components = {m['component_id'] for m in repo.mappings}
    for med in repo.products:
        comps = by_product[med['id']]
        if not any(c['id'] in mapped_components for c in comps):
            continue
        candidate = {'id': med['id'], 'component_count': med['component_count']}
        ingredients, extraction = ref.mapped_ingredients(candidate)
        wanted = [m for m in repo.mappings if m['component_id'] in {c['id'] for c in comps}]
        actual = [m for i in ingredients for m in i['ddinter_mappings']]
        assert sorted(actual, key=lambda m: m['id']) == sorted(wanted, key=lambda m: m['id'])
        assert all(i['dataset_build'] == build for i in ingredients)
    unique = next(p for p in repo.products if names[p['brand_name']] == 1)
    r = ref.lookup({'name_raw': unique['brand_name']})
    assert r['complete_identity'] and r['candidates'][0]['id'] == unique['id']


def test_approved_module1_fields_to_module3_contract(approved_projection):
    repo, build = approved_projection
    ref = CoreMedicationReference(repo, build)
    counts = Counter(p['brand_name'] for p in repo.products)
    components = {c['id']: c for c in repo.components}
    products = {p['id']: p for p in repo.products}
    # Pick source-supported single targets from distinct products. Module 3 still checks its own scope.
    targets = {}
    grouped = defaultdict(list)
    for mapping in repo.mappings:
        grouped[mapping['component_id']].append(mapping)
    for comp_id, mappings in grouped.items():
        comp = components[comp_id]
        med = products[comp['medication_id']]
        ids = {m['target_id'] for m in mappings}
        if len(ids) == 1 and None not in ids and med['component_count'] == 1 and counts[med['brand_name']] == 1:
            source_name = mappings[0]['source_locator']['source_attributes']['source_name']
            targets.setdefault(mappings[0]['target_id'], (med, source_name))
        if len(targets) == 2:
            break
    assert len(targets) == 2
    selected = list(targets.items())
    meds = [Medication(name_raw=med['brand_name'], evidence_text=med['brand_name'])
            for target, (med, name) in selected]
    extraction = Understanding(medications=meds).model_dump()
    identities = from_module1(extraction, ref, confirmed=True)
    assert all(r['ready_for_identifier_handoff'] for r in identities)
    # The bounded loader requires a row. An unrelated, explicitly synthetic pair
    # leaves these approved products outside loaded interaction coverage.
    dataset = BoundedDataset([{'DDInterID_A': 'DDInter990001', 'Drug_A': 'Synthetic Unrelated One',
        'DDInterID_B': 'DDInter990002', 'Drug_B': 'Synthetic Unrelated Two', 'Level': 'Minor'}],
        {'scope': 'Unrelated synthetic interaction fixture; approved identity evidence only', 'loaded_rows': 1,
         'synthetic_fixture': True}, additional_identities={target: {'name': name,
            'evidence': med['source_locator']} for target, (med, name) in selected})
    result = assess([r['module3_input'] for r in identities], dataset)
    assert not result['unresolved_mappings']
    assert result['checked_ingredient_pairs'][0]['status'] == 'NO_RECORD_IN_LOADED_SUBSET'
    assert result['safe_to_take'] is None


@pytest.fixture
def postgres_repo():
    dsn = os.environ.get('MODULE2_TEST_DSN')
    if not dsn:
        pytest.skip('MODULE2_TEST_DSN must name an EXISTING marked local test database')
    import psycopg
    from psycopg.conninfo import conninfo_to_dict
    options = conninfo_to_dict(dsn)
    if options.get('host') not in {'localhost', '127.0.0.1', '::1'} or not re.fullmatch(
            r'msa_core_test_v4[a-z0-9]*checks', options.get('dbname', '')):
        pytest.fail('Refusing a database outside the marked loopback Core V4 test boundary')
    with psycopg.connect(dsn, autocommit=True) as db:
        marker = db.execute("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()").fetchone()[0]
        assert marker == 'Medication Safety Assistant Core V4 isolated test'
        owner = uuid4()
        db.execute('INSERT INTO identity.users(id) VALUES (%s)', (owner,))
        yield CoreRepository(db, authenticated_owner=owner)


def test_confirmed_nlp_core_snapshot_and_module3(postgres_repo):
    repo = postgres_repo
    # Reuse ONLY the existing published synthetic build. No fixture import or new database.
    builds = repo._all('SELECT dataset_build,count(*) AS n FROM msa_ref.medications GROUP BY dataset_build')
    ledger = importer.read_ledger(repo.db)
    build = next((b['dataset_build'] for b in builds if b['n'] == 4 and
                  ledger['builds'].get(b['dataset_build'], {}).get('synthetic')), None)
    if build is None:
        pytest.skip('The existing four-product published Core synthetic fixture is required')
    spec = importlib.util.spec_from_file_location('module2_existing_fixtures', ROOT / 'db/tests/fixtures.py')
    fixtures = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixtures)
    meds = [Medication(name_raw=f'Core Fixture {n}', strength_raw='0,5g',
                       evidence_text=f'Core Fixture {n} 0,5g') for n in (0, 2)]
    service = ApplicationService(repo, MockProvider([Understanding(medications=meds).model_dump_json()]))
    r = service.start(task=Intent.ADD_MEDICATION)
    r = service.send(TurnRequest(workflow_id=r.workflow_id, revision=r.revision,
                                text='Core Fixture 0 0,5g; Core Fixture 2 0,5g'))
    for _ in range(2):
        r = service.send(TurnRequest(workflow_id=r.workflow_id, revision=r.revision, text='không rõ'))
    service.confirm(ConfirmationRequest(workflow_id=r.workflow_id, revision=r.revision,
                                       request_key=uuid4(), explicit_confirmation=True))
    handoff = service.handoff(r.workflow_id)
    matches = identify_confirmed(repo, handoff, dataset_build=build)
    assert len(matches) == 2 and all(m['match_status'] == 'SELECTED' for m, identity in matches)
    assert any(i['mapping_status'] == 'REVIEW_REQUIRED' for m, i in matches)
    snapshot = repo.create_snapshot([(m['entry_version_id'], m['id']) for m, i in matches],
                                    data_context='SYNTHETIC_TEST')
    context = repo.snapshot_context(snapshot['id'])
    assert sum(len(r['component_context']['mapping_refs']) for r in context) == 3
    saved, result = assess_confirmed_snapshot(repo, handoff, snapshot['id'], fixtures.dataset(), request_key=uuid4())
    assert saved['execution_status'] == 'COMPLETED'
    findings = repo._all('SELECT * FROM msa.safety_findings WHERE assessment_id=%s', (saved['id'],))
    assert sum(f['finding_type'] == 'DDI' for f in findings) == 2
    assert result['safe_to_take'] is None
    assert any('MULTIPLE_APPROVED_TARGETS' in reason for reason in result['checks']['ddi']['limitations'])
    altered = handoff.model_copy(deep=True)
    altered.entries[0].content_digest = 'f' * 64
    before = repo._one('SELECT count(*) AS n FROM msa.entry_matches WHERE user_id=%s', (repo.owner,))['n']
    with pytest.raises(ValueError, match='stale or unconfirmed'):
        identify_confirmed(repo, altered, dataset_build=build)
    assert repo._one('SELECT count(*) AS n FROM msa.entry_matches WHERE user_id=%s', (repo.owner,))['n'] == before
    with pytest.raises(PermissionError):
        identify_confirmed(CoreRepository(repo.db, authenticated_owner=uuid4()), handoff, dataset_build=build)
