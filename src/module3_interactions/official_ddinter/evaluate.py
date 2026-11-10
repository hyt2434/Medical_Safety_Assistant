"""Re-evaluate DAV mappings and selected interaction coverage without new crawling."""
import argparse
from collections import Counter, defaultdict
import json
from shared.paths import ProjectPath as Path, PROJECT_ROOT
import re
from shared.dav_import.common import file_hash, digest
from module2_medications.registration_parser import load_json
from module2_medications.audit import audit_dataset, CATEGORIES
from module2_medications.ingredients import parse_ingredients
from module2_medications.reference import MedicationReference
from module2_medications.service import assess_prescriptions
from module2_medications.terminology import DirectDDInter, load_ddinter
from module3_interactions.engine import assess

NEW_CATEGORY_PAIRS = {'B': ('Dolutegravir', 'Ferrous fumarate'), 'D': ('Ketoconazole', 'Abemaciclib'),
    'H': ('Abiraterone', 'Pasireotide'), 'L': ('Abacavir', 'Leflunomide'),
    'P': ('Halofantrine', 'Abiraterone'), 'R': ('Hydrocodone', 'Abiraterone'),
    'V': ('Dolutegravir', 'Tetraferric tricitrate decahydrate')}
HIGH_RISK_PAIRS = [('Warfarin', 'Aspirin'), ('Clopidogrel', 'Omeprazole'), ('Amiodarone', 'Warfarin'),
    ('Clarithromycin', 'Simvastatin'), ('Methotrexate', 'Trimethoprim'), ('Digoxin', 'Clarithromycin'),
    ('Metformin', 'Sitagliptin'), ('Vildagliptin', 'Metformin')]
FORM_CUE = re.compile(r'(?<!\w)(?:hydrochloride?|hydrocloride?|(?:mono|di|tri)?hydrate?|phosphate?|'
    r'besylate?|sulfate?|natri|sodium|potassium|calci(?:um)?|maleate?|acetate?|HCl)(?!\w)', re.I)


def evaluate(project, output, index):
    project, output = Path(project).resolve(), Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    mapper = DirectDDInter(load_ddinter(project, 'official-all', index_path=index))
    baseline_path = project / 'data/reference/test_fixtures/module2_api_quicktest/medication_reference/private_runs/20261013_003/audit.json'
    baseline = json.loads(baseline_path.read_text(encoding='utf-8'))
    raw = project / 'data/raw/dav/records.jsonl'
    if file_hash(raw) != baseline['source']['sha256']:
        raise ValueError('DAV bytes changed; stored baseline is not comparable')
    def save(name, value):
        (output / name).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    audit = audit_dataset(raw, mapper, as_of='2026-10-13', review_queue=output / 'review_queue.jsonl')
    save('audit.json', audit)
    save('crosswalk.json', mapper.crosswalk())
    category_stats = defaultdict(Counter)
    gap_counts, unresolved = Counter(), defaultdict(Counter)
    with raw.open(encoding='utf-8') as stream:
        for text in stream:
            row = load_json(text)
            parsed = parse_ingredients(row['ingredients'], row.get('strength'))
            complete = bool(parsed['ingredients']) and parsed['status'] == 'PARSED'
            mapped_components = 0
            for item in parsed['ingredients']:
                match = mapper.match(item['normalized_ingredient'])
                if item['extraction_status'] != 'PARSED':
                    reason = 'SOURCE_PARSING_REVIEW'
                elif match['mapping_status'] == 'VERIFIED':
                    mapped_components += 1
                    continue
                elif match['mapping_status'] == 'REVIEW_REQUIRED':
                    reason = 'AMBIGUOUS_OR_CONFLICTING_DICTIONARY_IDENTITY'
                elif FORM_CUE.search(item['normalized_ingredient']):
                    reason = 'SALT_FORM_OR_QUALIFIER_REQUIRES_REVIEW'
                else:
                    reason = 'NO_DICTIONARY_NAME_OR_VERIFIED_SYNONYM'
                complete = False
                gap_counts[reason] += 1
                unresolved[item['normalized_ingredient']][reason] += 1
            if not parsed['ingredients']:
                gap_counts['SOURCE_DESCRIPTION_NO_COMPONENTS_PARSED'] += 1
            for category, pattern in CATEGORIES.items():
                if re.search(pattern, row['ingredients'], re.I):
                    category_stats[category]['source_observations'] += 1
                    category_stats[category]['supported_parsing_observations'] += parsed['status'] == 'PARSED'
                    category_stats[category]['complete_mapping_observations'] += complete
                    category_stats[category]['mapped_component_occurrences'] += mapped_components
                    category_stats[category]['component_occurrences'] += len(parsed['ingredients'])
    if file_hash(raw) != baseline['source']['sha256']:
        raise ValueError('DAV bytes changed during evaluation')
    save('mapping_gaps.json', {'cause_counts': dict(gap_counts),
        'cause_limitations': 'Salt patterns are review cues only. A missing name may mean an absent entry or unverified synonym; chemical equivalence is not inferred.',
        'source_product_ambiguity': {'brand_ambiguous_observations': audit['counts']['brand_ambiguous_observations'],
            'registration_conflicting_observations': audit['counts']['registration_conflicting_observations']},
        'unresolved_normalized_ingredient_strings': [
            {'ingredient': name, 'occurrences': sum(c.values()), 'reason_counts': dict(c)}
            for name, c in sorted(unresolved.items(), key=lambda item: (-sum(item[1].values()), item[0]))],
        'local_analysis_only': True, 'raw_products_published': False})
    save('category_coverage.json', {'categories': {name: dict(counts) for name, counts in category_stats.items()},
        'method': 'same non-exhaustive source ingredient-text category probes as prior audit; not clinical classification'})
    def engine_case(names):
        meds = []
        for number, name in enumerate(names, 1):
            mapped = mapper.match(name)
            meds.append({'medication_id': 'synthetic-med-' + str(number), 'prescription_ids': ['synthetic-rx-' + str(number)],
                'brand_name': 'Synthetic generic-pair probe', 'identity_status': 'VERIFIED',
                'identity_evidence': [{'kind': 'synthetic_engineering_fixture_not_DAV_product'}],
                'source_kind': 'synthetic_fixture', 'ingredients': [{'name': mapped['ddinter_generic_name'] or name,
                    'ddinter_id': mapped['ddinter_id'], 'mapping_status': mapped['mapping_status'], 'mapping_evidence': mapped['evidence']}]})
        return assess(meds, mapper.dataset)
    pairs = []
    for label, names in [(f'new_category_{cat}', names) for cat, names in NEW_CATEGORY_PAIRS.items()] + [
            ('high_risk_' + str(n), names) for n, names in enumerate(HIGH_RISK_PAIRS, 1)]:
        result = engine_case(names)
        save(label + '.json', result)
        pairs.append({'case': label, 'generic_names': names, 'assessment_status': result['assessment_status'],
            'checked_unique_pairs': len(result['checked_ingredient_pairs']),
            'matched_interactions': len(result['matched_interactions']),
            'original_levels': [r['original_level'] for r in result['matched_interactions']],
            'source_filenames': sorted({s['evidence']['filename'] for r in result['checked_ingredient_pairs'] for s in r['source_records']}),
            'safe_to_take': result['safe_to_take'], 'requires_hcp_review': result['requires_hcp_review']})
    reference = MedicationReference(project / 'data/reference/test_fixtures/module2_api_quicktest/medication_reference/private_runs/20261013_003/reference.sqlite',
                                    allow_synthetic=True)
    try:
        fixture = json.loads((project / 'data/reference/provenance/module2_api_quicktest/medication_reference/examples/pipeline.synthetic.json').read_text())
        handoff = assess_prescriptions(fixture, reference, mapper)
        save('module1_module2_module3.json', handoff)
    finally:
        reference.close()
    old, new = baseline['counts'], audit['counts']
    total = new['valid_source_observations']
    before, after = old['complete_terminology_mapped_observations'], new['complete_terminology_mapped_observations']
    summary = {'schema_version': 'ddinter.expansion_evaluation.v1', 'dataset_verdict': mapper.dataset.coverage['dataset_verdict'],
        'coverage': mapper.dataset.coverage, 'baseline_audit_sha256': file_hash(baseline_path),
        'DAV_raw_sha256': file_hash(raw), 'valid_DAV_observations': total,
        'old_complete_observation_mappings': before, 'new_complete_observation_mappings': after,
        'old_complete_observation_mapping_percentage': before / total * 100,
        'new_complete_observation_mapping_percentage': after / total * 100,
        'improvement_observations': after - before, 'improvement_percentage_points': (after - before) / total * 100,
        'old_exact_component_mappings': old['mapping_method_EXACT_NORMALIZED_GENERIC'],
        'new_exact_component_mappings': new['mapping_method_EXACT_NORMALIZED_GENERIC'],
        'old_verified_synonym_component_mappings': old['mapping_method_VERIFIED_SOURCE_SYNONYM'],
        'new_verified_synonym_component_mappings': new['mapping_method_VERIFIED_SOURCE_SYNONYM'],
        'remaining_unresolved_component_occurrences': new['unresolved_ingredient_mappings'],
        'unique_unresolved_normalized_strings': len(unresolved), 'gap_cause_counts': dict(gap_counts),
        'category_coverage': {name: dict(c) for name, c in category_stats.items()},
        'selected_pair_probes': pairs, 'pair_probe_count': len(pairs),
        'pair_probes_with_complete_ids': sum(p['checked_unique_pairs'] > 0 for p in pairs),
        'pair_probes_with_positive_source_records': sum(p['matched_interactions'] > 0 for p in pairs),
        'end_to_end_fixture': {'assessment_status': handoff['module3']['assessment_status'],
            'major_warning_preserved': any(r['original_level'] == 'Major' for r in handoff['module3']['matched_interactions']),
            'safe_to_take': handoff['module3']['safe_to_take'], 'requires_hcp_review': handoff['module3']['requires_hcp_review']},
        'real_product_identity_review_still_required': True, 'independent_clinical_accuracy': None,
        'network_requests_during_evaluation': 0, 'new_DAV_reference_database_created': False}
    save('summary.json', summary)
    print(json.dumps({k: summary[k] for k in ('dataset_verdict', 'new_complete_observation_mappings',
        'new_complete_observation_mapping_percentage', 'improvement_percentage_points', 'remaining_unresolved_component_occurrences')}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--project', type=Path, default=PROJECT_ROOT)
    parser.add_argument('--index', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    evaluate(args.project, args.output, args.index)

