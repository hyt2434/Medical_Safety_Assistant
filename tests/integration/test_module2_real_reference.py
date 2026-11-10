"""Read-only evaluation of a published REAL Core build, not clinical gold-label validation.

Opt in with MODULE2_REAL_DSN. Real references are never imported or changed.
The optional handoff test uses the existing isolated application DB for actual
confirmation, and captures match persistence in memory because that DB does not
contain the real reference build. This distinction is retained in the report.
"""
from collections import Counter, defaultdict
from copy import deepcopy
from decimal import Decimal
import csv
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import time
from uuid import uuid4

import psycopg
from psycopg.conninfo import conninfo_to_dict
import pytest

from shared.db import CoreRepository
from shared.db.intake_adapter import build_confirmed_handoff
from shared.intake_contracts import Medication
from module2_medications.core import CoreMedicationReference, identify_confirmed
from module2_medications.service import identify, module3_input
from module2_medications.text import brand_key, normalized_form, registration
from shared.dav_import.normalize import parse_strength
from module3_interactions.engine import BoundedDataset, assess, valid_id, text_key
from tests.integration.test_module2_core import postgres_repo
from tests.integration.test_module2_input_sources import persist_source, confirm_review, handoff_for_unconfirmed_rows

ROOT = Path(__file__).resolve().parents[2]
BUILD_TABLES = {'medications': 'source_medication_id', 'ingredients': 'source_ingredient_id',
                'medication_ingredients': 'source_component_id', 'ddinter_mappings': 'source_mapping_id'}


def percent(numerator, denominator):
    return round(100 * numerator / denominator, 4) if denominator else None


def fingerprints(tables):
    return {table: hashlib.sha256(json.dumps(rows, sort_keys=True, default=str,
        separators=(',', ':')).encode()).hexdigest() for table, rows in tables.items()}


class Category:
    def __init__(self):
        self.total = self.retained = self.correct_verified = self.wrong_verified = 0
        self.statuses, self.issues, self.examples = Counter(), Counter(), []

    def add(self, result, row, fields, *, positive=True):
        self.total += 1
        self.statuses[result['identification_status']] += 1
        ids = {str(c['id']) for c in result['candidates']}
        retained = str(row['id']) in ids
        self.retained += int(positive and retained)
        verified = result['identification_status'] == 'VERIFIED'
        self.correct_verified += int(positive and verified and retained)
        self.wrong_verified += int(verified and (not positive or not retained))
        new_issue = any(issue not in self.issues for issue in result['issues'])
        self.issues.update(result['issues'])
        if (len(self.examples) < 5 or new_issue) and (not retained or not verified):
            self.examples.append({'source_medication_id': row['source_medication_id'],
                'brand_name': row['brand_name'], 'query': fields, 'status': result['identification_status'],
                'candidate_count': len(ids), 'expected_source_retained': retained if positive else None,
                'issues': result['issues']})

    def report(self, *, positive=True):
        return {'queries': self.total, 'statuses': dict(self.statuses),
            'status_rates_percent': {s: percent(self.statuses[s], self.total)
                                     for s in ('VERIFIED', 'REVIEW_REQUIRED', 'UNRESOLVED')},
            'multiple_candidate_queries': self.issues['MULTIPLE_PRODUCT_CANDIDATES'],
            'multiple_candidate_rate_percent': percent(self.issues['MULTIPLE_PRODUCT_CANDIDATES'], self.total),
            'unsupported_strength_review_queries': self.issues['STRENGTH_SEMANTICS_REVIEW_REQUIRED'],
            'expected_source_retained': self.retained if positive else None,
            'expected_source_retention_percent': percent(self.retained, self.total) if positive else None,
            'correct_unique_source_selections': self.correct_verified if positive else None,
            'correct_unique_source_selection_percent': percent(self.correct_verified, self.total) if positive else None,
            'incorrect_verified_selections': self.wrong_verified,
            'issues': dict(self.issues), 'examples': self.examples}


def fields_for(row, *, extended=False):
    definition = row['product_details'].get('source_identity_definition') or {}
    fields = {'name_raw': row['brand_name']}
    for field, value in [('strength_raw', definition.get('strength')), ('dosage_form_raw', row['dosage_form']),
                         ('route_raw', row['route'])]:
        if value: fields[field] = value
    if extended:
        for field, value in [('registration_token', row['product_details'].get('registration_token')),
                             ('manufacturer', row['manufacturer'])]:
            if value: fields[field] = value
    return fields


def equivalent_strength(raw):
    parsed = parse_strength(raw)
    if parsed['status'] != 'PARSED': return None
    if parsed['unit'] == 'mg':
        amount = format((Decimal(parsed['amount']) / 1000).normalize(), 'f')
        value = amount.replace('.', ',') + ' g'
    elif parsed['unit'] == 'IU':
        value = parsed['amount'] + ' UI'
    else: return None
    if parsed['denominator_unit']:
        value += '/' + parsed['denominator_amount'] + ' ' + parsed['denominator_unit']
    return value


def read_tables(repo, build):
    return {name: repo._all(f'SELECT * FROM msa_ref.{name} WHERE dataset_build=%s ORDER BY id', (build,))
            for name in BUILD_TABLES}


def evaluate(repo, build, tables):
    started = time.perf_counter()
    ref = CoreMedicationReference(repo, build)
    categories = defaultdict(Category)
    products = tables['medications']
    names = defaultdict(list)
    for row in products: names[brand_key(row['brand_name'])].append(row)
    variants = {'tablet': 'tablet', 'film_coated_tablet': 'tablet, film coated',
                'hard_capsule': 'hard capsule', 'injection_solution': 'solution for injection',
                'extended_release_tablet': 'tablet, extended release'}
    lookup_start = time.perf_counter()
    query_digest = hashlib.sha256()

    def observe(category, fields, row, *, positive=True):
        query_digest.update(json.dumps({'category': category, 'source_id': row['source_medication_id'], 'fields': fields},
                                       sort_keys=True, ensure_ascii=False).encode('utf-8') + b'\n')
        result = ref.lookup(fields)
        if any(c.get('match_kind') in {'SIMILAR_NAME_REVIEW_ONLY', 'ATTRIBUTES_REVIEW_ONLY'}
               for c in result['candidates']):
            assert result['identification_status'] == 'REVIEW_REQUIRED'
            assert not result['complete_identity']
            assert all(not c['establishes_identity'] for c in result['candidates'])
        categories[category].add(result, row, fields, positive=positive)
        return result

    for row in products:
        base = fields_for(row)
        cases = {'exact_name': {'name_raw': row['brand_name']}, 'name_strength_form': base,
                 'all_available_qualifiers': fields_for(row, extended=True),
                 'missing_strength': {k: v for k, v in base.items() if k != 'strength_raw'},
                 'missing_form': {k: v for k, v in base.items() if k != 'dosage_form_raw'}}
        dose = equivalent_strength(base.get('strength_raw'))
        if dose:
            category = 'equivalent_strength' if parse_strength(dose)['status'] == 'PARSED' else 'ambiguous_locale_strength'
            if category == 'equivalent_strength': cases[category] = {**base, 'strength_raw': dose}
            else:
                fields = {**base, 'strength_raw': dose}
                observe(category, fields, row, positive=False)
        form = variants.get(normalized_form(row['dosage_form']))
        if form: cases['equivalent_dosage_form'] = {**base, 'dosage_form_raw': form}
        for category, fields in cases.items():
            result = observe(category, fields, row)
            if category == 'exact_name' and len(names[brand_key(row['brand_name'])]) > 1:
                categories['duplicate_normalized_names'].add(result, row, fields)
            if category == 'name_strength_form' and (row['component_count'] or 0) > 1:
                categories['multi_ingredient_products'].add(result, row, fields)
            if category == 'name_strength_form' and (not base.get('strength_raw') or not row['dosage_form']):
                categories['reference_missing_strength_or_form'].add(result, row, fields)
        negative = dict(base)
        negative.pop('name_raw')
        observe('missing_name', negative, row, positive=False)
        typo = row['brand_name'] + row['brand_name'][-1]
        while brand_key(typo) in names: typo += row['brand_name'][-1]
        negative = {'name_raw': typo}
        observe('similar_but_absent_names', negative, row, positive=False)
    lookup_seconds = time.perf_counter() - lookup_start
    consistency, issues = Counter(), []
    by_medication, by_component = defaultdict(list), defaultdict(list)
    ingredients = {str(r['id']): r for r in tables['ingredients']}
    medications = {str(r['id']): r for r in products}
    components = {str(r['id']): r for r in tables['medication_ingredients']}
    for row in tables['medication_ingredients']:
        by_medication[str(row['medication_id'])].append(row)
        consistency['components_in_build'] += int(row['dataset_build'] == build)
        consistency['component_product_links_valid'] += int(str(row['medication_id']) in medications)
        consistency['components_with_canonical_ingredient'] += int(row['ingredient_id'] is not None)
        consistency['ingredient_links_valid_or_null'] += int(row['ingredient_id'] is None or str(row['ingredient_id']) in ingredients)
    for row in tables['ddinter_mappings']:
        by_component[str(row['component_id'])].append(row)
        consistency['mapping_component_links_valid'] += int(str(row['component_id']) in components)
    for name, rows in tables.items():
        for row in rows:
            loc = row['source_locator']
            valid = (row['dataset_build'] == build and loc.get('source_id') == row[BUILD_TABLES[name]] and
                     loc.get('artifact_sha256') == ref.build_metadata['files'][name] and
                     loc.get('manifest_locator', {}).get('artifact_sha256') == build and bool(loc.get('source_ref')))
            consistency['valid_source_locator_rows'] += int(valid)
            if not valid: issues.append({'table': name, 'source_id': row[BUILD_TABLES[name]], 'issue': 'SOURCE_OR_BUILD_MISMATCH'})
    component_status, product_status, mapping_targets, samples = Counter(), Counter(), Counter(), []
    projection_start = time.perf_counter()
    for row in products:
        expected = by_medication[str(row['id'])]
        projected, extraction = ref.mapped_ingredients({'id': str(row['id']), 'component_count': row['component_count']})
        consistency['complete_component_products'] += int(extraction['status'] == 'PARSED')
        consistency['products_with_exact_component_ids'] += int(
            {p['component_id'] for p in projected} == {str(c['id']) for c in expected})
        complete = bool(projected) and extraction['status'] == 'PARSED' and all(p['mapping_status'] == 'VERIFIED' for p in projected)
        product_status['all_components_unambiguous_targets' if complete else 'incomplete_or_ambiguous_mapping'] += 1
        for item in projected:
            component_status[item['mapping_status']] += 1
            wanted = json.loads(json.dumps(by_component[item['component_id']], default=str))
            same = sorted(item['ddinter_mappings'], key=lambda m: m['id']) == sorted(wanted, key=lambda m: m['id'])
            consistency['components_preserving_all_mapping_rows'] += int(same)
            canonical = components[item['component_id']]['ingredient_id']
            consistency['projected_ingredient_links_valid_or_null'] += int(
                item['ingredient_record'] is None if canonical is None else item['ingredient_record']['id'] == str(canonical))
            mapping_targets['components_with_any_valid_target'] += int(bool(item['candidate_ddinter_ids']))
            mapping_targets['components_with_multiple_targets'] += int(len(item['candidate_ddinter_ids']) > 1)
            if len(samples) < 8 and item['mapping_status'] != 'VERIFIED':
                samples.append({'source_medication_id': row['source_medication_id'], 'brand_name': row['brand_name'],
                    'source_component_id': item['source_component_id'], 'name': item['normalized_ingredient'],
                    'status': item['mapping_status'], 'targets': item['candidate_ddinter_ids'], 'reason': item['unresolved_reason']})
    projection_seconds = time.perf_counter() - projection_start
    rows = tables['ddinter_mappings']
    mapping_targets.update(rows=len(rows), valid_target_rows=sum(valid_id(r['target_id']) for r in rows),
        null_target_rows=sum(r['target_id'] is None for r in rows), unique_target_ids=len({r['target_id'] for r in rows if valid_id(r['target_id'])}),
        rows_with_retrieval_evidence=sum(bool(r['retrieval_evidence']) for r in rows),
        rows_with_catalog_hash=sum(bool(r['target_catalog_sha256']) for r in rows))
    subset_categories = {'duplicate_normalized_names', 'multi_ingredient_products', 'reference_missing_strength_or_form'}
    result = {'schema': 'module2.real_reference_evaluation.v1', 'dataset_build': build,
        'executed_lookup_queries': sum(value.total for name, value in categories.items() if name not in subset_categories),
        'query_manifest_sha256': query_digest.hexdigest(),
        'reference_build_metadata': ref.build_metadata, 'records': {n: len(r) for n, r in tables.items()},
        'methodology': {'identification': 'Source-derived round-trip and controlled equivalent/negative inputs; not an independent clinical gold set.',
            'consistency': 'All relational links, source/build locators, projected components and every mapping row checked separately.',
            'clinical_identification_accuracy': None, 'clinical_accuracy_limitation': 'No independently adjudicated patient/product identity gold labels are available.'},
        'categories': {name: value.report(positive=name not in {'missing_name', 'similar_but_absent_names', 'ambiguous_locale_strength'})
                       for name, value in categories.items()},
        'name_groups': {'unique_normalized_names': len(names), 'duplicate_groups': sum(len(v) > 1 for v in names.values()),
                        'products_in_duplicate_groups': sum(len(v) for v in names.values() if len(v) > 1)},
        'consistency': {'counts': dict(consistency), 'issues': issues},
        'mapping_coverage': {'component_statuses': dict(component_status), 'product_statuses': dict(product_status),
            **dict(mapping_targets), 'component_any_valid_target_percent': percent(mapping_targets['components_with_any_valid_target'], len(components)),
            'component_unambiguous_mapping_percent': percent(component_status['VERIFIED'], len(components)),
            'products_all_components_unambiguous_percent': percent(product_status['all_components_unambiguous_targets'], len(products)),
            'examples': samples},
        'elapsed_seconds': {'lookups': round(lookup_seconds, 3), 'relational_projection': round(projection_seconds, 3),
                            'total': round(time.perf_counter() - started, 3)}}
    return result


def report_path():
    target = Path(os.environ.get('MODULE2_REAL_REPORT', ROOT / 'artifacts/module2_real_reference.json')).resolve()
    if not target.is_relative_to((ROOT / 'artifacts').resolve()):
        raise ValueError('Evaluation reports must stay under ignored artifacts/')
    return target


def compare_baseline(report):
    """Compare only identical query manifests and unchanged real references."""
    source = os.environ.get('MODULE2_REAL_BASELINE')
    if not source:
        return
    path = Path(source).resolve()
    assert path.is_relative_to((ROOT / 'artifacts').resolve())
    assert path != report_path(), 'Never overwrite the frozen baseline'
    before = json.loads(path.read_text(encoding='utf-8'))
    for field in ('dataset_build', 'executed_lookup_queries', 'query_manifest_sha256',
                  'reference_fingerprints', 'mapping_coverage', 'consistency'):
        assert before[field] == report[field], f'Baseline mismatch: {field}'
    subsets = {'duplicate_normalized_names', 'multi_ingredient_products', 'reference_missing_strength_or_form'}
    totals = {'before': Counter(), 'after': Counter()}
    categories = {}
    for name, after in report['categories'].items():
        old = before['categories'][name]
        assert old['queries'] == after['queries']
        categories[name] = {'queries': after['queries'], 'subset': name in subsets,
            'before': old['status_rates_percent'], 'after': after['status_rates_percent'],
            'status_count_delta': {s: after['statuses'].get(s, 0) - old['statuses'].get(s, 0)
                                   for s in ('VERIFIED', 'REVIEW_REQUIRED', 'UNRESOLVED')},
            'incorrect_verified_before': old['incorrect_verified_selections'],
            'incorrect_verified_after': after['incorrect_verified_selections']}
        if name not in subsets:
            totals['before'].update(old['statuses'])
            totals['after'].update(after['statuses'])
    assert sum(totals['before'].values()) == sum(totals['after'].values()) == report['executed_lookup_queries']
    report['benchmark_comparison'] = {'baseline': str(path.relative_to(ROOT)),
        'identical_query_manifest': True, 'unchanged_reference_and_mapping_evidence': True,
        'totals': {stage: {'counts': dict(counts), 'rates_percent': {
            s: percent(counts[s], report['executed_lookup_queries'])
            for s in ('VERIFIED', 'REVIEW_REQUIRED', 'UNRESOLVED')}} for stage, counts in totals.items()},
        'categories': categories,
        'limitation': 'Aggregate mixes source-derived positive and missing-name/absent-name controls; not clinical accuracy.'}


@pytest.fixture(scope='module')
def real_catalog():
    dsn = os.environ.get('MODULE2_REAL_DSN')
    if not dsn: pytest.skip('MODULE2_REAL_DSN must point to an existing real Core V4 build; no fallback/import')
    with psycopg.connect(dsn, autocommit=True, options='-c default_transaction_read_only=on') as db:
        assert db.execute('SHOW transaction_read_only').fetchone()[0] == 'on'
        repo = CoreRepository(db, authenticated_owner=uuid4())
        ledger = json.loads(repo._one("SELECT obj_description('msa_ref'::regnamespace,'pg_namespace') AS ledger")['ledger'])
        choices = [b for b, m in ledger['builds'].items() if m.get('published') and m.get('synthetic') is False]
        build = os.environ.get('MODULE2_REAL_BUILD')
        if build is None:
            assert len(choices) == 1, 'Pin MODULE2_REAL_BUILD when multiple real builds exist'
            build = choices[0]
        assert build in choices, 'A published non-synthetic build is required'
        tables = read_tables(repo, build)
        before = fingerprints(tables)
        yield repo, build, tables
        assert fingerprints(read_tables(repo, build)) == before, 'Reference rows changed during read-only evaluation'


def test_real_catalog_identification_mapping_and_provenance(real_catalog):
    repo, build, tables = real_catalog
    report = evaluate(repo, build, tables)
    options = conninfo_to_dict(os.environ['MODULE2_REAL_DSN'])
    report['database'] = {k: options.get(k) for k in ('host', 'port', 'dbname')}
    report['read_only'] = True
    report['reference_fingerprints'] = fingerprints(tables)
    compare_baseline(report)
    target = report_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    assert not report['consistency']['issues']
    assert all(c['incorrect_verified_selections'] == 0 for c in report['categories'].values())
    assert report['categories']['exact_name']['expected_source_retained'] == len(tables['medications'])
    counts = report['consistency']['counts']
    assert counts['products_with_exact_component_ids'] == len(tables['medications'])
    assert counts['components_preserving_all_mapping_rows'] == len(tables['medication_ingredients'])


class ReadOnlyMatchCapture:
    """Real reference reads + genuine Core intake guards; no real-build match writes.

    The existing isolated intake database has no copy of the real reference build.
    Capture the final persistence boundary rather than importing data or claiming
    a cross-database Core snapshot can be persisted.
    """
    def __init__(self, intake_repo, reference_repo):
        self.intake, self.reference, self.owner = intake_repo, reference_repo, intake_repo.owner
        self.captured = []

    def _owned(self, *args, **kwargs):
        return self.intake._owned(*args, **kwargs)

    def _one(self, query, params=()):
        target = self.reference if 'msa_ref' in str(query) or 'msa.published' in str(query) else self.intake
        return target._one(query, params)

    def _all(self, query, params=()):
        return (self.reference if 'msa_ref' in str(query) else self.intake)._all(query, params)

    def record_match(self, entry, outcome, **options):
        row = self.intake._owned('medication_entry_versions', entry)
        assert row['confirmed_at'] is not None
        match = {'id': uuid4(), 'entry_version_id': row['id'], 'match_status': outcome,
                 'product_id': options.get('product'), 'captured_only_not_persisted': True}
        self.captured.append((match, deepcopy(options)))
        return match


def existing_module3_sample():
    csv_path = os.environ.get('MODULE2_DDINTER_CSV')
    index_path = os.environ.get('MODULE2_DDINTER_INDEX')
    if not csv_path or not index_path:
        pytest.skip('Existing approved DDInter CSV and index paths required for real Module 3 compatibility')
    source = Path(csv_path)
    manifest = json.loads((source.parent / 'approved_download_manifest.json').read_text(encoding='utf-8-sig'))
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    assert digest == manifest['sha256'].lower()
    with source.open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        rows = [next(reader) for _ in range(10)]
    index = Path(index_path).resolve()
    seal = json.loads(index.with_suffix('.manifest.json').read_text(encoding='utf-8'))
    assert hashlib.sha256(index.read_bytes()).hexdigest() == seal['index_sha256']
    # Read identities from the existing sealed index; reuse the actual bounded
    # engine for pair lookup. No new index, name matcher, or safety engine.
    with sqlite3.connect(index.as_uri() + '?mode=ro', uri=True) as db:
        identities = {i: json.loads(value) for i, value in db.execute('SELECT identifier,identity_json FROM identities')}
    return BoundedDataset(rows, {'loaded_rows': len(rows), 'scope': 'First ten retained real category-A rows; existing sealed index identity evidence',
        'synthetic_fixture': False, 'source_url': manifest['source_url'], 'csv_sha256': digest,
        'complete_database_loaded': False, 'index_sha256': seal['index_sha256']}, identities)


def test_realistic_confirmed_handoff_and_existing_module3_interface(real_catalog, postgres_repo, tmp_path):
    reference_repo, build, tables = real_catalog
    dataset = existing_module3_sample()
    ref = CoreMedicationReference(reference_repo, build)
    by_med, mapped = defaultdict(list), defaultdict(list)
    products = {str(p['id']): p for p in tables['medications']}
    components = {str(c['id']): c for c in tables['medication_ingredients']}
    for c in components.values(): by_med[str(c['medication_id'])].append(c)
    for m in tables['ddinter_mappings']: mapped[str(m['component_id'])].append(m)
    selected, tags = {}, {}

    def add(row, tag):
        if str(row['id']) not in selected:
            selected[str(row['id'])] = row
            tags[str(row['id'])] = tag

    # Try actual loaded interaction endpoints first, without inventing mappings.
    endpoints = {i for pair in dataset.records for i in pair}
    for mapping in tables['ddinter_mappings']:
        if mapping['target_id'] in endpoints:
            row = products[str(components[str(mapping['component_id'])]['medication_id'])]
            if ref.lookup(fields_for(row))['complete_identity']: add(row, 'loaded_endpoint')
        if len(selected) >= 4: break
    for tag, predicate, quota in [
        ('multi_ingredient', lambda r: (r['component_count'] or 0) > 1, 4),
        ('missing_strength', lambda r: not fields_for(r).get('strength_raw'), 3),
        ('unsupported_strength', lambda r: bool(fields_for(r).get('strength_raw')) and
            parse_strength(fields_for(r)['strength_raw'])['status'] != 'PARSED', 3),
        ('duplicate_name', lambda r: len(ref.lookup({'name_raw': r['brand_name']})['candidates']) > 1, 3),
        ('mapped_component', lambda r: any(mapped[str(c['id'])] for c in by_med[str(r['id'])]), 3)]:
        added = 0
        for row in products.values():
            if predicate(row) and str(row['id']) not in selected:
                add(row, tag); added += 1
            if added >= quota: break
    meds = []
    for row in selected.values():
        fields = fields_for(row)
        evidence = '; '.join(str(v) for v in fields.values())
        meds.append(Medication(**fields, evidence_text=evidence))
    workflow, saved, *_ = persist_source(postgres_repo, 'MANUAL', meds, tmp_path)
    capture = ReadOnlyMatchCapture(postgres_repo, reference_repo)
    with pytest.raises(ValueError, match='unconfirmed'):
        identify_confirmed(capture, handoff_for_unconfirmed_rows(workflow, saved['entries']), dataset_build=build)
    assert not capture.captured
    workflow = confirm_review(postgres_repo, workflow, revision=workflow['revision'], explicit_confirmation=True)
    handoff = build_confirmed_handoff(postgres_repo, workflow['id'])
    matches = identify_confirmed(capture, handoff, dataset_build=build)
    assert len(matches) == len(selected) and all(m['captured_only_not_persisted'] for m, r in matches)
    for row, (match, result) in zip(selected.values(), matches):
        assert str(row['id']) in {c['id'] for c in result['candidates']}
        assert result['input_evidence']['inputs'][0]['modality'] == 'MANUAL'
    inputs = [module3_input(result, str(match['entry_version_id']), [str(workflow['intake_session_id'])])
              for match, result in matches]
    output = assess(inputs, dataset)
    assert output['safe_to_take'] is None and output['no_interactions'] is None
    assert len(output['checked_medication_pairs']) == len(inputs) * (len(inputs) - 1) // 2
    assert not output['coverage']['complete_database_loaded']
    retained = len(capture.captured)
    forged = handoff.model_copy(deep=True)
    forged.entries[-1].content_digest = 'f' * 64
    with pytest.raises(ValueError): identify_confirmed(capture, forged, dataset_build=build)
    assert len(capture.captured) == retained
    target = report_path()
    report = json.loads(target.read_text(encoding='utf-8')) if target.exists() else {}
    report['confirmed_handoff_and_module3'] = {
        'inputs': len(matches), 'input_selection_categories': dict(Counter(tags.values())),
        'confirmation': 'Actual Core V4 display/revision/digest/owner confirmation in existing isolated intake DB',
        'reference_access': 'Read-only actual real build; final match persistence captured in memory, NOT persisted',
        'identity_statuses': dict(Counter(r['identification_status'] for m, r in matches)),
        'mapping_statuses': dict(Counter(r['mapping_status'] for m, r in matches)),
        'module3_scope': dataset.coverage, 'checked_medication_pairs': len(output['checked_medication_pairs']),
        'checked_ingredient_pairs': len(output['checked_ingredient_pairs']),
        'unresolved_components': len(output['unresolved_mappings']), 'source_interactions': len(output['matched_interactions']),
        'unresolved_issue_counts': dict(Counter(issue for item in output['unresolved_mappings'] for issue in item['issues'])),
        'source_interaction_examples': [{'target_ids': pair['drug_id_pair'], 'source_levels': pair['original_levels']}
                                        for pair in output['matched_interactions'][:3]],
        'assessment_status': output['assessment_status'], 'safe_to_take': output['safe_to_take'],
        'limitation': 'Direct Module 3 interface checked; real-build Core snapshot/assessment persistence is not exercised across databases.'}
    targets = {m['target_id'] for m in tables['ddinter_mappings'] if valid_id(m['target_id'])}
    missing = sorted(targets - dataset.identities.keys())
    names_outside = []
    for mapping in tables['ddinter_mappings']:
        identity = dataset.identities.get(mapping['target_id'])
        source_name = mapping['source_locator'].get('source_attributes', {}).get('source_name')
        if identity and source_name and text_key(source_name) not in {
                text_key(n) for n in [identity['name'], *identity.get('synonyms', [])]}:
            names_outside.append(mapping['source_mapping_id'])
    report['mapping_targets_in_existing_module3_identity_evidence'] = {
        'unique_core_targets': len(targets), 'targets_in_loaded_identity_evidence': len(targets) - len(missing),
        'targets_outside_loaded_identity_evidence': len(missing), 'outside_target_examples': missing[:20],
        'rows_with_source_names_outside_loaded_target_name_or_synonyms': len(names_outside),
        'source_name_mismatch_examples': names_outside[:20],
        'limitation': 'Catalog membership/name comparison is not independent adjudication of chemical mapping correctness or interaction coverage.'}
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
