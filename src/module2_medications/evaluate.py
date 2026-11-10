"""Reproducible demo and engineering cases. No real product reviews are invented."""
import argparse
from collections import Counter
from datetime import datetime, timezone, timedelta
import json
from shared.paths import ProjectPath as Path, PROJECT_ROOT
import sqlite3
import time
from .audit import audit_dataset
from .fixtures import fixture_db
from .ingredients import parse_ingredients
from .reference import MedicationReference, review_product
from .service import assess_prescriptions
from .terminology import DirectDDInter, load_ddinter
from shared.dav_import.common import file_hash


def evaluate(project, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    as_of = datetime.now(timezone(timedelta(hours=7))).date().isoformat()
    started = time.perf_counter()
    terminology = DirectDDInter(load_ddinter(project, 'category-a'))
    load_seconds = time.perf_counter() - started
    def write(name, value):
        (output / name).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    audit = audit_dataset(Path(project) / 'data/raw/dav/records.jsonl', terminology,
                          as_of=as_of, review_queue=output / 'review_queue.jsonl')
    write('audit.json', audit)
    write('crosswalk.json', terminology.crosswalk())
    db_path, source, _ = fixture_db(output)
    # Engineering adjudication is confined to invented products with synthetic provenance.
    with sqlite3.connect(db_path) as db:
        ids = [r[0] for r in db.execute('SELECT DISTINCT candidate_key FROM m2_candidates')]
    db.close()
    for cid in ids:
        review_product(db_path, cid, status='VERIFIED', reviewer='Synthetic expected-case author; not a clinical reviewer',
                       evidence=[{'locator': 'synthetic://module2-fixture-declarations', 'sha256': file_hash(source)}])
    def med(brand, **options):
        return {'name_raw': brand, 'synthetic_fixture': True,
                'transcription_status': 'USER_CONFIRMED_TRANSCRIPTION', **options}
    scenarios = {
        'major_warning': [med('Fixture Dolutegravir'), med('Fixture Antacid')],
        'combination': [med('Fixture Combination')],
        'different_strengths_duplicate_ingredient': [med('Fixture Para', strength_raw='500mg'), med('Fixture Para', strength_raw='1g')],
        'ambiguous_brand': [med('Fixture Para')],
        'missing_strength': [med('Fixture Missing')],
        'fuzzy_mistake': [med('Fixture Parra')],
        'unmapped_ingredient': [med('Fixture Unknown')],
        'registration_conflict': [med('Fixture Conflict', strength_raw='500mg')],
        'inline_strength_diabetes': [med('Fixture Inline', strength_raw='10mg')],
        'unconfirmed_transcription': [med('Fixture Dolutegravir', transcription_status='REVIEW_REQUIRED')],
    }
    outcomes = {}
    reference = MedicationReference(db_path, allow_synthetic=True)
    try:
        lookup_start = time.perf_counter()
        for _ in range(200):
            reference.lookup(med('Fixture Para', strength_raw='500mg'))
        lookup_seconds = time.perf_counter() - lookup_start
        for name, meds in scenarios.items():
            result = assess_prescriptions({'medications': meds}, reference, terminology,
                                          prescription_id='synthetic-rx-' + name)
            write(name + '.json', result)
            assessed = result['module3']
            outcomes[name] = {'synthetic_fixture': True, 'identification_statuses': [r['identification_status'] for r in result['module2']],
                'mapping_statuses': [r['mapping_status'] for r in result['module2']],
                'assessment_status': assessed['assessment_status'],
                'checked_unique_ingredient_pairs': len(assessed['checked_ingredient_pairs']),
                'matched_interactions': len(assessed['matched_interactions']),
                'original_levels': [p['original_level'] for p in assessed['matched_interactions']],
                'safe_to_take': assessed['safe_to_take'], 'requires_hcp_review': assessed['requires_hcp_review']}
        # Actual saved Module 1 data remains unconfirmed and has no real reference here.
        legacy = json.loads((Path(project) / 'data/samples/historical_extraction.json').read_text(encoding='utf-8'))
        actual = assess_prescriptions(legacy, reference, terminology, prescription_id='saved-module1-sample')
        write('saved_module1_pipeline.json', actual)
    finally:
        reference.close()
    parse_cases = [
        ('Paracetamol 500mg; Dolutegravir 50mg', ['Paracetamol', 'Dolutegravir']),
        ('Metformin Hydrochloride 850mg, Sitagliptin (dưới dạng sitagliptin phosphate monohydrate 64,25mg) 50mg',
         ['Metformin Hydrochloride', 'Sitagliptin']),
        ('Metformin Hydrochloride 500mg, Vildagliptin 50mg', ['Metformin Hydrochloride', 'Vildagliptin']),
        ('Paracetamol 0,5g + Dolutegravir 50mg', ['Paracetamol', 'Dolutegravir']),
    ]
    correct = sum(parse_ingredients(raw)['status'] == 'PARSED' and
                  [i['normalized_ingredient'] for i in parse_ingredients(raw)['ingredients']] == expected
                  for raw, expected in parse_cases)
    pair_tests = []
    for a, b in [('Warfarin', 'Aspirin'), ('Clopidogrel', 'Omeprazole'),
                 ('Metformin', 'Sitagliptin'), ('Dolutegravir', 'Aluminum hydroxide')]:
        left, right = terminology.match(a), terminology.match(b)
        result = terminology.dataset.lookup(left['ddinter_id'], right['ddinter_id']) if left['ddinter_id'] and right['ddinter_id'] else None
        pair_tests.append({'generic_names': [a, b], 'verified_identifiers': [left['ddinter_id'], right['ddinter_id']],
            'status': result['status'] if result else 'UNRESOLVED_IDENTITY',
            'original_level': result.get('original_level') if result else None,
            'safe': None, 'kind': 'terminology_pair_probe_only; no verified real product association'})
    summary = {'schema_version': 'module2.evaluation.v1', 'as_of': as_of, 'dataset_audit': 'audit.json',
        'reference_database': 'reference.sqlite', 'reference_kind': '13 synthetic observations only; not DAV products',
        'source_reuse_limitation': 'DAV grant not supplied; no persistent real medication reference created',
        'ddinter_coverage': terminology.dataset.coverage, 'scenarios': outcomes,
        'synthetic_combination_parser_cases': {'correct': correct, 'total': len(parse_cases),
            'accuracy': correct/len(parse_cases), 'independently_reviewed_real_product_accuracy': None},
        'terminology_pair_probes': pair_tests,
        'saved_module1_pipeline': {'medications': len(actual['module2']),
            'identification_statuses': [r['identification_status'] for r in actual['module2']],
            'assessment_status': actual['module3']['assessment_status'], 'safe_to_take': None,
            'reason': 'Sample brands absent from this DAV capture; synthetic rows never satisfy real inputs'},
        'timing': {'dictionary_load_seconds': load_seconds, '200_warm_fixture_lookups_seconds': lookup_seconds,
            'total_seconds': time.perf_counter() - started},
        'review_queue_rows': audit['counts']['valid_source_observations'],
        'network_requests_by_pipeline': 0, 'clinical_validation_performed': False}
    write('summary.json', summary)
    print(json.dumps({'output': str(output), 'synthetic_scenarios': len(scenarios), 'real_clinical_accuracy': None}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--project', type=Path, default=PROJECT_ROOT)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    evaluate(args.project, args.output)
