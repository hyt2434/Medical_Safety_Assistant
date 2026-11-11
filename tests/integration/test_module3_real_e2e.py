"""Real, local DDInter and existing published Core fixtures; no reference imports.

Intake is authored test input, not a patient prescription. NLP extraction uses a
deterministic provider; grounded answers use the existing template composer.
"""
from collections import defaultdict
from copy import deepcopy
import hashlib
import json
import re
from uuid import uuid4

import pytest

from tests.integration.test_module2_core import postgres_repo
from module1_intake.nlp.interfaces.application import (
    ApplicationService, TurnRequest, ConfirmationRequest, WorkflowActionRequest)
from module1_intake.nlp.models import Medication, Understanding, Intent
from module1_intake.nlp.understanding.providers import MockProvider
from module1_intake.nlp.qa_pipeline.structured import CoreAssessmentRetriever
from module1_intake.nlp.qa_pipeline.composition import GroundedComposer
from module1_intake.nlp.qa_pipeline.contracts import RetrievalQuery
from module2_medications.core import identify_confirmed
from module3_interactions.engine import BoundedDataset, HEADERS
from module3_interactions.official_ddinter.dataset import OfficialDataset
from shared.db.safety_adapter import run_safety
from shared.db.importer import read_ledger


@pytest.fixture(scope='module')
def ddinter():
    return OfficialDataset()


@pytest.fixture
def real(postgres_repo, ddinter):
    repo = postgres_repo
    ledger = read_ledger(repo.db)
    builds = repo._all('SELECT dataset_build,count(*) AS n FROM msa_ref.medications GROUP BY dataset_build')
    build = next((b['dataset_build'] for b in builds if b['n'] == 10670
                  and ledger['builds'].get(b['dataset_build'], {}).get('published')
                  and ledger['builds'][b['dataset_build']].get('synthetic') is False), None)
    if build is None:
        observed = [{**b, 'ledger': ledger['builds'].get(b['dataset_build'])} for b in builds]
        pytest.fail(
            f"MODULE2_TEST_DSN selects {repo.db.info.dbname!r}, which has no published "
            "non-synthetic 10,670-product reference build. A schema-only NLP database "
            "or the four-product synthetic fixture cannot run this suite. "
            f"Observed builds: {observed!r}. "
            "See src/module3_interactions/README.md#reproduce-the-real-data-e2e-run. "
            "No import is performed by this test."
        )
    # Retained reference rows and ledger must remain byte-equivalent across tests.
    def fingerprint():
        return [repo._one(f"SELECT count(*) AS n,md5(string_agg(to_jsonb(t)::text,'' ORDER BY id)) AS hash FROM msa_ref.{table} t")
                for table in ('medications', 'ingredients', 'medication_ingredients', 'ddinter_mappings')]
    before = fingerprint()
    products = repo._all('SELECT * FROM msa_ref.medications WHERE dataset_build=%s ORDER BY brand_name,id', (build,))
    components = repo._all('SELECT * FROM msa_ref.medication_ingredients WHERE dataset_build=%s', (build,))
    mappings = repo._all('SELECT * FROM msa_ref.ddinter_mappings WHERE dataset_build=%s', (build,))
    by_name, by_product, by_component = defaultdict(list), defaultdict(list), defaultdict(list)
    for p in products:
        by_name[p['brand_name'].casefold()].append(p)
    for c in components:
        by_product[c['medication_id']].append(c)
    for m in mappings:
        by_component[m['component_id']].append(m)
    single, unmapped, partial = {}, [], []
    for p in products:
        if len(by_name[p['brand_name'].casefold()]) != 1:
            continue
        cs = by_product[p['id']]
        if not cs or len(cs) != p['component_count']:
            continue
        targets = [{m['target_id'] for m in by_component[c['id']] if m['target_id'] in ddinter.identities} for c in cs]
        if len(cs) == 1 and len(targets[0]) == 1:
            single.setdefault(next(iter(targets[0])), p)
        strength = p['product_details']['source_identity_definition'].get('strength') or ''
        if (len(cs) == 1 and not by_component[cs[0]['id']] and cs[0]['ingredient_id']
                and re.fullmatch(r'\d+(?:[.,]\d+)?\s*(?:mg|g|mcg)', strength, re.I)):
            unmapped.append(p)
        if len(cs) > 1 and any(targets) and any(not t for t in targets):
            partial.append(p)
    major, absent = None, None
    for a in sorted(single):
        for b in sorted(single):
            if a >= b:
                continue
            found = ddinter.lookup(a, b)
            if major is None and found.get('original_level') == 'Major':
                major = (single[a], single[b])
            if absent is None and found['status'] == 'NO_RECORD_IN_LOADED_SUBSET':
                absent = (single[a], single[b])
            if major and absent:
                break
        if major and absent:
            break
    assert major and absent and unmapped and partial
    yield repo, build, major, absent, unmapped[0], partial[0]
    assert fingerprint() == before
    assert read_ledger(repo.db) == ledger


def intake(repo, build, products, dataset):
    meds = []
    for index, p in enumerate(products, 1):
        strength = p['product_details']['source_identity_definition'].get('strength') or None
        text = f"Mục {index}: {p['brand_name']} {strength or ''}, dạng {p['dosage_form'] or ''}".strip()
        meds.append(Medication(name_raw=p['brand_name'], strength_raw=strength,
                               dosage_form_raw=p['dosage_form'], evidence_text=text))
    service = ApplicationService(repo, MockProvider([Understanding(medications=meds).model_dump_json()]),
                                 dataset_build=build, dataset=dataset, data_context='SYNTHETIC_TEST')
    r = service.start(task=Intent.ADD_MEDICATION)
    r = service.send(TurnRequest(workflow_id=r.workflow_id, revision=r.revision,
                                text='; '.join(m.evidence_text for m in meds)))
    for _ in range(len(meds) * 3):
        if r.state == 'AWAITING_CONFIRMATION':
            break
        r = service.send(TurnRequest(workflow_id=r.workflow_id, revision=r.revision, text='không rõ'))
    assert r.state == 'AWAITING_CONFIRMATION', r
    r = service.confirm(ConfirmationRequest(workflow_id=r.workflow_id, revision=r.revision,
                                            request_key=uuid4(), explicit_confirmation=True))
    handoff = service.handoff(r.workflow_id)
    assert all(repo._owned('medication_entry_versions', e.entry_version_id)['confirmed_at'] for e in handoff.entries)
    return service, r, handoff


def snapshot(repo, build, products, dataset):
    service, r, handoff = intake(repo, build, products, dataset)
    matches = identify_confirmed(repo, handoff, dataset_build=build)
    assert all(m['match_status'] == 'SELECTED' for m, _ in matches), [i['issues'] for _, i in matches]
    snap = repo.create_snapshot([(m['entry_version_id'], m['id']) for m, _ in matches], data_context='SYNTHETIC_TEST')
    assert snap['status'] == 'SEALED' and snap['snapshot_digest']
    return snap, matches


def findings(repo, assessment):
    return repo._all('SELECT * FROM msa.safety_findings WHERE assessment_id=%s ORDER BY finding_key', (assessment['id'],))


def answer(repo, assessment, composer=None):
    query = RetrievalQuery(question='Kiểm tra tương tác thuốc đã xác nhận', kind='safety',
        entry_ids=tuple(row['entry_version_id'] for row in repo.snapshot_context(assessment['snapshot_id'])),
        assessment_id=assessment['id'])
    return (composer or GroundedComposer()).compose(query.question, CoreAssessmentRetriever(repo).retrieve(query))


def test_full_application_real_ddi_grounding_and_idempotency(real, ddinter, record_property):
    repo, build, major, *_ = real
    service, r, handoff = intake(repo, build, major, ddinter)
    def execute(kind, key):
        return service.execute(WorkflowActionRequest(workflow_id=r.workflow_id, revision=r.revision,
            action=kind, request_key=key, explicit_request=True))
    r = execute('IDENTIFY', uuid4())
    assert all(i['identification_status'] == 'VERIFIED' for i in r.identification_results)
    key = uuid4()
    r = execute('ASSESS', key)
    saved = repo._owned('safety_assessments', r.assessment_id)
    assert saved['execution_status'] == 'COMPLETED' and saved['result_digest']
    assert saved['knowledge_builds']['ddinter']['index_sha256'] == ddinter.coverage['index_sha256']
    assert saved['knowledge_builds']['ddinter']['manifest_sha256']
    assert saved['knowledge_builds']['ddinter']['index_manifest_sha256']
    ddi = [f for f in findings(repo, saved) if f['finding_type'] == 'DDI']
    assert ddi and all(f['source_severity'] == 'Major' for f in ddi)
    assert all(f['evidence']['display_timing'] == 'IMMEDIATE' for f in ddi)
    for f in ddi:
        assert f['evidence']['sources'] and f['evidence']['mapping_ids']
        for source in f['evidence']['sources']:
            assert source['record']['original_level'] == source['source_severity']
            assert source['artifact_sha256'] == source['record']['evidence']['csv_sha256']
    assert 'DDI (MAJOR)' in r.assistant_message and 'coverage=PARTIAL' in r.assistant_message
    assert r.evidence_refs and any('safety_findings/' in e.locator for e in r.evidence_refs)
    assert execute('ASSESS', key) == r
    previous = findings(repo, saved)
    reused, out = run_safety(repo, saved['snapshot_id'], ddinter, request_key=key)
    assert reused['id'] == saved['id'] and out['reused_attempt']
    assert findings(repo, saved) == previous
    hold = saved['check_results']['ddi']['scope']['reminder_hold']
    assert hold['required'] and set(hold['entry_version_ids']) == {str(e.entry_version_id) for e in handoff.entries}
    assert not hold['activation_policy_implemented'] and not hold['existing_reminders_modified']
    record_property('real_products', [p['brand_name'] for p in major])
    record_property('source_rows', sum(len(f['evidence']['sources']) for f in ddi))


def test_duplicates_from_verified_local_ids_without_ddinter_mapping(real, ddinter):
    repo, build, _, _, missing, _ = real
    snap, _ = snapshot(repo, build, [missing, missing], ddinter)
    saved, result = run_safety(repo, snap['id'], ddinter)
    duplicates = [f for f in findings(repo, saved) if f['finding_type'] == 'DUPLICATE_INGREDIENT']
    assert duplicates and all(f['evidence']['rule_id'] == 'same-local-ingredient-id' for f in duplicates)
    assert all(f['evidence']['local_ingredient_id'] and f['evidence']['sources'] for f in duplicates)
    assert saved['check_results']['duplicate_ingredient']['coverage'] == 'ASSESSED'
    assert saved['check_results']['ddi']['coverage'] == 'UNASSESSED'
    assert result['safe_to_take'] is None
    assert 'DUPLICATE_INGREDIENT' in answer(repo, saved).text


def test_absent_source_record_never_establishes_safety(real, ddinter):
    repo, build, _, absent, *_ = real
    snap, _ = snapshot(repo, build, absent, ddinter)
    saved, result = run_safety(repo, snap['id'], ddinter)
    assert saved['check_results']['ddi']['pair_results'][0]['status'] == 'NO_RECORD_IN_LOADED_SUBSET'
    assert saved['check_results']['ddi']['coverage'] == 'PARTIAL'
    assert not any(f['finding_type'] == 'DDI' for f in findings(repo, saved))
    assert result['safe_to_take'] is result['no_interactions'] is None
    assert answer(repo, saved).status == 'PARTIAL'


def test_partial_combination_retains_every_component_pair(real, ddinter):
    repo, build, major, _, _, partial = real
    snap, _ = snapshot(repo, build, [partial, major[0]], ddinter)
    saved, result = run_safety(repo, snap['id'], ddinter)
    rows = repo.snapshot_context(snap['id'])
    expected = len(rows[0]['component_context']['components']) * len(rows[1]['component_context']['components'])
    scope = saved['check_results']['ddi']['scope']
    assert len(scope['component_pair_results']) == expected
    assert any(c['status'] == 'UNASSESSED' for c in scope['component_pair_results'])
    assert any(f['finding_type'] == 'UNRESOLVED' for f in findings(repo, saved))
    assert saved['check_results']['ddi']['coverage'] in {'PARTIAL', 'UNASSESSED'}
    assert result['safe_to_take'] is None


def test_single_medication_core_contract_not_applicable(real, ddinter):
    repo, build, major, *_ = real
    snap, _ = snapshot(repo, build, [major[0]], ddinter)
    saved, result = run_safety(repo, snap['id'], ddinter)
    for key in ('ddi', 'duplicate_ingredient'):
        assert saved['check_results'][key]['coverage'] == 'NOT_APPLICABLE'
        assert saved['check_results'][key]['pair_results'] == []
    assert result['safe_to_take'] is None


def test_warning_survives_lookup_failure_and_retry(real, ddinter):
    repo, build, major, *_ = real
    snap, _ = snapshot(repo, build, [major[0], major[1], major[0]], ddinter)
    class Failure:
        coverage, identities = deepcopy(ddinter.coverage), ddinter.identities
        calls = 0
        def lookup(self, a, b):
            self.calls += 1
            if self.calls == 2:
                raise RuntimeError('Injected lookup failure after committed real warning')
            return ddinter.lookup(a, b)
    key = uuid4()
    saved, result = run_safety(repo, snap['id'], Failure(), request_key=key)
    assert saved['execution_status'] == 'FAILED'
    retained = findings(repo, saved)
    major_ids = {f['id'] for f in retained if f['severity'] == 'MAJOR'}
    assert major_ids and major_ids <= {f['id'] for f in repo.severe_warnings()}
    assert result['reminder_hold']['required']
    assert 'DDI (MAJOR)' in answer(repo, saved).text
    class BrokenComposerProvider:
        def generate_structured(self, *args):
            raise RuntimeError('Injected composition outage')
    fallback = answer(repo, saved, GroundedComposer(BrokenComposerProvider()))
    assert fallback.composition == 'TEMPLATE_FALLBACK' and 'DDI (MAJOR)' in fallback.text
    reused, _ = run_safety(repo, snap['id'], ddinter, request_key=key)
    assert reused['id'] == saved['id'] and findings(repo, reused) == retained
    retried, _ = run_safety(repo, snap['id'], ddinter, request_key=uuid4(), retry_of=saved['id'])
    assert retried['execution_status'] == 'COMPLETED'
    assert major_ids <= {f['id'] for f in repo.severe_warnings()}


def test_explicit_synthetic_conflict_preserves_severities_and_hold(real, ddinter):
    repo, build, major, *_ = real
    snap, _ = snapshot(repo, build, major, ddinter)
    targets = [r['component_context']['mapping_refs'][0]['mapping_id'] for r in repo.snapshot_context(snap['id'])]
    mappings = repo._all('SELECT target_id FROM msa_ref.ddinter_mappings WHERE id=ANY(%s::uuid[]) ORDER BY id', (targets,))
    a, b = [m['target_id'] for m in mappings]
    rows = [dict(zip(HEADERS, (a, ddinter.identities[a]['name'], b, ddinter.identities[b]['name'], level)))
            for level in ('Major', 'Minor')]
    digest = hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()
    synthetic = BoundedDataset(rows, {'loaded_rows': 2, 'synthetic_fixture': True,
        'csv_sha256': digest, 'source_url': 'synthetic://module3-conflict-engineering-test'})
    saved, result = run_safety(repo, snap['id'], synthetic)
    conflict = next(f for f in findings(repo, saved) if f['finding_type'] == 'SOURCE_CONFLICT')
    assert conflict['source_severity'] is None and conflict['severity'] == 'UNKNOWN'
    assert {s['source_severity'] for s in conflict['evidence']['sources']} == {'Major', 'Minor'}
    assert conflict['id'] in {f['id'] for f in repo.severe_warnings()}
    assert result['reminder_hold']['required'] and 'SOURCE_CONFLICT' in answer(repo, saved).text


def synthetic_build(repo):
    builds = read_ledger(repo.db)['builds']
    build = next(b for b, meta in builds.items() if meta.get('synthetic') and meta.get('published'))
    products = repo._all('SELECT * FROM msa_ref.medications WHERE dataset_build=%s ORDER BY source_medication_id', (build,))
    assert len(products) == 4
    return build, products


def test_persisted_duplicate_ddinter_alternatives_keep_partial_coverage(real):
    repo, *_ = real
    build, products = synthetic_build(repo)
    rows = [dict(zip(HEADERS, ('DDInter900002', 'Synthetic Beta', 'DDInter900003', 'Synthetic Gamma', 'Major')))]
    dataset = BoundedDataset(rows, {'loaded_rows': 1, 'synthetic_fixture': True,
        'csv_sha256': hashlib.sha256(json.dumps(rows).encode()).hexdigest(),
        'source_url': 'synthetic://module3-approved-target-duplicate-test'})
    snap, _ = snapshot(repo, build, [products[1], products[2]], dataset)
    saved, _ = run_safety(repo, snap['id'], dataset)
    duplicate = next(f for f in findings(repo, saved) if f['finding_type'] == 'DUPLICATE_INGREDIENT')
    assert duplicate['evidence']['rule_id'] == 'same-approved-ddinter-target'
    assert duplicate['evidence']['target_id'] == 'DDInter900002'
    assert len(duplicate['evidence']['mapping_ids']) == 2
    assert saved['check_results']['duplicate_ingredient']['coverage'] == 'PARTIAL'


def test_mixed_build_snapshot_rejected_without_starting_assessment(real, ddinter):
    repo, build, major, *_ = real
    real_snap, _ = snapshot(repo, build, [major[0]], ddinter)
    other_build, products = synthetic_build(repo)
    other_snap, _ = snapshot(repo, other_build, [products[0]], ddinter)
    rows = repo.snapshot_context(real_snap['id']) + repo.snapshot_context(other_snap['id'])
    mixed = repo.create_snapshot([(r['entry_version_id'], r['entry_match_id']) for r in rows], data_context='SYNTHETIC_TEST')
    before = repo._one('SELECT count(*) AS n FROM msa.safety_assessments WHERE user_id=%s', (repo.owner,))
    with pytest.raises(ValueError, match='consistent reference'):
        run_safety(repo, mixed['id'], ddinter)
    assert repo._one('SELECT count(*) AS n FROM msa.safety_assessments WHERE user_id=%s', (repo.owner,)) == before


def test_real_sample_is_rejected_at_persistence_boundary(real, ddinter):
    repo, build, major, *_ = real
    snap, _ = snapshot(repo, build, major, ddinter)
    source = next(c for c in ddinter.lookup('DDInter582', 'DDInter725')['source_records'])
    sample = BoundedDataset([source['raw_source_row']], {'loaded_rows': 1, 'synthetic_fixture': False,
        'csv_sha256': source['evidence']['csv_sha256'], 'source_url': source['evidence']['source_url']})
    with pytest.raises(ValueError, match='no sample fallback'):
        run_safety(repo, snap['id'], sample)
