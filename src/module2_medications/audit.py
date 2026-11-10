"""Local streaming audit: aggregate findings and hash/line review locators only."""
from collections import Counter, defaultdict
from datetime import date, datetime
import json
from shared.paths import ProjectPath as Path, PROJECT_ROOT
import re
from shared.dav_import.common import digest, file_hash
from .registration_parser import load_json
from .ingredients import parse_ingredients
from .reference import candidate_key
from .text import clean, key, brand_key, registration, strength_key

FIELDS = ('brand_name', 'registration_number', 'ingredients', 'strength', 'dosage_form', 'manufacturer')
BRANDS = ('Jardiance', 'Janumet', 'Galvus Met', 'Siofor', 'Ozempic', 'Trulicity', 'MYPARA', 'NOVOXIM', 'KAVASDIN')
DIABETES = ('metformin', 'sitagliptin', 'empagliflozin', 'dapagliflozin', 'vildagliptin',
            'linagliptin', 'glimepiride', 'insulin', 'semaglutide', 'dulaglutide')
CATEGORIES = {
    'analgesic_antipyretic': r'paracetamol|acetaminophen|ibuprofen|diclofenac|tramadol',
    'antibiotic': r'amoxicil|cefuroxim|ceftriaxon|azithromycin|ciprofloxacin|meropenem',
    'cardiovascular': r'amlodipin|telmisartan|valsartan|bisoprolol|atorvastatin',
    'diabetes': '|'.join(DIABETES),
    'gastrointestinal': r'omeprazol|pantoprazol|esomeprazol|domperidon',
    'respiratory_allergy': r'salbutamol|budesonid|cetirizin|loratadin|montelukast',
    'anticoagulant_antiplatelet': r'warfarin|rivaroxaban|apixaban|heparin|clopidogrel|dabigatran',
    'other_high_risk': r'digoxin|methotrexat|lithium|tacrolimus|venetoclax',
}


def audit_dataset(path, terminology, *, as_of, review_queue=None):
    path = Path(path)
    before = file_hash(path)
    stats = Counter()
    missing, types, statuses, field_shapes, issues = Counter(), Counter(), Counter(), Counter(), Counter()
    brands, normalized_brands, registrations, primary_registrations = set(), set(), set(), set()
    pages = defaultdict(set)
    locators, exact_observations = set(), set()
    by_registration, by_brand, by_brand_strength = defaultdict(set), defaultdict(set), defaultdict(set)
    brand_occurrences, registration_occurrences = Counter(), Counter()
    queue_rows = []
    sought, diabetes, categories, diabetes_mapped = Counter(), Counter(), Counter(), Counter()
    expiry_dates = []
    queue = Path(review_queue).open('x', encoding='utf-8') if review_queue else None
    try:
        with path.open(encoding='utf-8-sig') as stream:
            for line, text in enumerate(stream, 1):
                reasons = []
                stats['physical_lines'] += 1
                try:
                    raw = load_json(text)
                    if not isinstance(raw, dict):
                        raise ValueError('Expected an object')
                    if any(raw.get(f) is not None and not isinstance(raw.get(f), str) for f in FIELDS):
                        raise ValueError('Reference fields must be text or null')
                except (ValueError, TypeError) as error:
                    stats['invalid_source_observations'] += 1
                    reasons.append('INVALID_JSON_OR_FIELD_TYPE:' + str(error))
                    if queue:
                        queue_rows.append(({'line': line, 'reasons': reasons}, None, None))
                    continue
                stats['valid_source_observations'] += 1
                row_sha = digest(raw)
                if row_sha in exact_observations:
                    stats['exact_duplicate_observations'] += 1
                exact_observations.add(row_sha)
                field_shapes[','.join(sorted(raw))] += 1
                for f in FIELDS:
                    if not clean(raw.get(f)):
                        missing[f] += 1
                    types[f + ':' + type(raw.get(f)).__name__] += 1
                statuses[str(raw.get('verification_status'))] += 1
                brand, reg = raw.get('brand_name'), raw.get('registration_number')
                brands.add(brand)
                normalized_brands.add(key(brand))
                registrations.add(reg)
                primary = registration(reg)
                if primary:
                    primary_registrations.add(primary)
                else:
                    stats['unreadable_registration_cells'] += 1
                    reasons.append('REGISTRATION_CELL_REVIEW')
                cid = candidate_key(raw)
                by_registration[primary or clean(reg)].add(cid)
                by_brand[brand_key(brand)].add(cid)
                by_brand_strength[(brand_key(brand), strength_key(raw.get('strength')))].add(cid)
                brand_occurrences[brand_key(brand)] += 1
                registration_occurrences[primary or clean(reg)] += 1
                source = raw.get('_source', {})
                try:
                    if source.get('source_url') not in {
                            'https://06dichvucong.dav.gov.vn/congbothuoc/index',
                            'https://dichvucong.dav.gov.vn/congbothuoc/index'}:
                        raise ValueError('Source URL')
                    timestamp = datetime.fromisoformat(source['captured_at'].replace('Z', '+00:00'))
                    if timestamp.tzinfo is None:
                        raise ValueError('Naive timestamp')
                    page, ordinal = source['page'], source['ordinal']
                    if type(page) is not int or type(ordinal) is not int or min(page, ordinal) < 1:
                        raise ValueError('Page/ordinal')
                    if source.get('raw_page_filename') != f'page_{page:05d}.json':
                        raise ValueError('Page filename')
                    locator = (page, ordinal)
                    if locator in locators:
                        stats['duplicate_source_locators'] += 1
                    locators.add(locator)
                    pages[page].add(ordinal)
                    reconstructed = {'fields': {k: v for k, v in raw.items() if k not in
                        {'verification_status', '_source', '_source_cells'}},
                        'cells': raw['_source_cells'], 'verification_status': raw['verification_status']}
                    if digest(reconstructed) != source['row_sha256']:
                        stats['source_row_hash_mismatches'] += 1
                        reasons.append('SOURCE_ROW_HASH_MISMATCH')
                    stats['valid_source_metadata'] += 1
                except (ValueError, KeyError, TypeError, AttributeError):
                    stats['invalid_source_metadata'] += 1
                    reasons.append('SOURCE_METADATA_REVIEW')
                try:
                    expiry = datetime.strptime(raw.get('valid_until', ''), '%d/%m/%Y').date()
                    expiry_dates.append(expiry.isoformat())
                    if expiry < date.fromisoformat(as_of):
                        stats['observations_with_past_displayed_expiry'] += 1
                except (ValueError, TypeError):
                    stats['missing_or_unparseable_displayed_expiry'] += 1
                ingredient_text = raw.get('ingredients') or ''
                for wanted in BRANDS:
                    if re.search(r'(?<!\w)' + re.escape(key(wanted)) + r'(?!\w)', key(brand)):
                        sought[wanted] += 1
                for wanted in DIABETES:
                    if re.search(r'(?<!\w)' + re.escape(wanted), key(ingredient_text)):
                        diabetes[wanted] += 1
                for category, pattern in CATEGORIES.items():
                    if re.search(pattern, ingredient_text, re.I):
                        categories[category] += 1
                parsed = parse_ingredients(ingredient_text, raw.get('strength'))
                stats['ingredient_extraction_' + parsed['status']] += 1
                combination = len(parsed['ingredients']) > 1
                if combination:
                    stats['combination_candidates'] += 1
                    stats['combination_extraction_' + parsed['status']] += 1
                complete = bool(parsed['ingredients']) and parsed['status'] == 'PARSED'
                for component in parsed['ingredients']:
                    stats['ingredient_components'] += 1
                    mapped = terminology.match(component['normalized_ingredient'])
                    verified = component['extraction_status'] == 'PARSED' and mapped['mapping_status'] == 'VERIFIED'
                    stats['verified_ingredient_mappings' if verified else 'unresolved_ingredient_mappings'] += 1
                    stats['generic_format_normalized_components'] += component['extraction_status'] == 'PARSED'
                    if verified:
                        stats['mapping_method_' + mapped['match_method']] += 1
                        for wanted in DIABETES:
                            if key(mapped['ddinter_generic_name']) == wanted:
                                diabetes_mapped[wanted] += 1
                    else:
                        complete = False
                        reasons.append(mapped['unresolved_reason'] or 'EXTRACTION_REVIEW')
                    reasons.extend(component['issues'])
                stats['complete_terminology_mapped_observations' if complete else
                      'incomplete_terminology_mapped_observations'] += 1
                reasons.extend(parsed['issues'])
                reasons.append('INDEPENDENT_DAV_PRODUCT_REVIEW_PENDING')
                issues.update(set(reasons))
                if queue:
                    queue_rows.append(({'line': line, 'observation_sha256': row_sha,
                        'source_page': source.get('page'), 'source_ordinal': source.get('ordinal'),
                        'identification_status': 'REVIEW_REQUIRED', 'reasons': sorted(set(reasons))},
                        brand_key(brand), primary or clean(reg)))
        for item, brand_id, reg_id in queue_rows:
            if brand_id is not None and len(by_brand[brand_id]) > 1:
                item['reasons'].append('BRAND_HAS_MULTIPLE_PRODUCT_CANDIDATES')
            if reg_id is not None and len(by_registration[reg_id]) > 1:
                item['reasons'].append('CONFLICTING_REGISTRATION_OBSERVATIONS')
            queue.write(json.dumps(item, ensure_ascii=False) + '\n')
    finally:
        if queue:
            queue.close()
    if file_hash(path) != before:
        raise ValueError('Raw input changed during the audit')
    total = stats['valid_source_observations']
    stats['brand_ambiguous_observations'] = sum(n for b, n in brand_occurrences.items() if len(by_brand[b]) > 1)
    stats['registration_conflicting_observations'] = sum(n for r, n in registration_occurrences.items() if len(by_registration[r]) > 1)
    issues['BRAND_HAS_MULTIPLE_PRODUCT_CANDIDATES'] = stats['brand_ambiguous_observations']
    issues['CONFLICTING_REGISTRATION_OBSERVATIONS'] = stats['registration_conflicting_observations']
    return {'schema_version': 'module2.dataset_audit.v1', 'as_of': as_of,
        'source': {'path': str(path), 'sha256': before, 'bytes': path.stat().st_size, 'raw_unchanged': True,
            'encoding': 'UTF-8 (strict decoding; optional BOM)', 'reuse_permissions': 'NO_GRANT_FOUND_ALONGSIDE_RAW_FILE',
            'persistent_DAV_reference_built': False, 'raw_page_artifacts_available_alongside_input': False},
        'counts': dict(stats), 'distinct_raw_brand_names': len(brands),
        'distinct_case_unicode_whitespace_normalized_brand_names': len(normalized_brands),
        'distinct_raw_registration_cells': len(registrations), 'distinct_parsed_primary_registrations': len(primary_registrations),
        'source_pages': len(pages), 'page_bounds': [min(pages), max(pages)] if pages else None,
        'noncontiguous_page_ordinals': sum(sorted(values) != list(range(1, len(values)+1)) for values in pages.values()),
        'missing_fields': dict(missing), 'field_types': dict(types), 'field_shapes': dict(field_shapes),
        'source_verification_statuses': dict(statuses),
        'repeated_registration_keys': total - len(by_registration),
        'registrations_with_conflicting_descriptions': sum(len(v) > 1 for v in by_registration.values()),
        'brand_lookup_keys_with_multiple_candidates': sum(len(v) > 1 for v in by_brand.values()),
        'brand_only_unique_candidate_keys': sum(len(v) == 1 for v in by_brand.values()),
        'brand_strength_unique_candidate_keys': sum(len(v) == 1 for v in by_brand_strength.values()),
        'lookup_key_coverage': {'brand_indexable_observations': total - missing['brand_name'],
            'registration_indexable_observations': total - stats['unreadable_registration_cells'],
            'meaning': 'indexable candidates; not independently verified product identification'},
        'requested_brand_source_observations': {b: sought[b] for b in BRANDS},
        'diabetes_source_text_mentions': {x: diabetes[x] for x in DIABETES},
        'diabetes_verified_terminology_component_mappings': {x: diabetes_mapped[x] for x in DIABETES},
        'category_source_text_mentions': {x: categories[x] for x in CATEGORIES},
        'category_method': 'non-exhaustive ingredient text probes; no verified therapeutic classification inferred',
        'mapping_dictionary_coverage': terminology.dataset.coverage,
        'review_reason_counts': dict(issues), 'independently_reviewed_real_examples': 0,
        'real_product_identification_accuracy': None, 'real_combination_parsing_accuracy': None,
        'real_mapping_accuracy': None, 'current_product_authorization': 'UNKNOWN',
        'limitations': ['Source observations are not unique products or current authorizations.',
            'Parser/mapping coverage counts measure deterministic processing, not clinical accuracy.',
            'Salt forms and unsupported Vietnamese spelling variants remain unresolved without reviewed equivalences.',
            'Review queue contains source locators and hashes only, not raw medication descriptions.',
            'No independently reviewed real-product evaluation corpus has been supplied.']}

