"""Module 1 input adapter and backward-compatible Module 3 identifier handoff."""
from copy import deepcopy
from module3_interactions.engine import assess
from .ingredients import parse_ingredients


def identify(medication, reference, terminology):
    lookup = reference.lookup(medication)
    result = {'schema_version': 'module2.medication_identity.v1', 'original_medication': deepcopy(medication),
        **lookup, 'identified_candidate': None, 'ingredients': [], 'verified_ddinter_ids': [],
        'mapping_status': 'UNRESOLVED', 'ready_for_identifier_handoff': False,
        'requires_hcp_review': True, 'interaction_assessment': 'NOT_PERFORMED'}
    if len(lookup['candidates']) != 1:
        return result
    candidate = lookup['candidates'][0]
    result['identified_candidate'] = candidate
    raw = candidate['product']
    parsed = parse_ingredients(raw.get('ingredients'), raw.get('strength'))
    result['ingredient_extraction'] = parsed
    for item in parsed['ingredients']:
        mapped = terminology.match(item['normalized_ingredient'])
        mapped.update(original_ingredient=item['original_ingredient'],
            normalized_ingredient=item['normalized_ingredient'], strength_raw=item['strength_raw'],
            strength=item['strength'], extraction_status=item['extraction_status'],
            source_form_declaration=item['source_form_declaration'], extraction_issues=item['issues'])
        if item['extraction_status'] != 'PARSED':
            mapped.update(mapping_status='REVIEW_REQUIRED', ddinter_id=None,
                          unresolved_reason='INGREDIENT_EXTRACTION_REVIEW_REQUIRED')
        if terminology.dataset.coverage.get('synthetic_fixture') and not candidate['synthetic_fixture']:
            mapped.update(mapping_status='UNRESOLVED', ddinter_id=None,
                          unresolved_reason='SYNTHETIC_TERMINOLOGY_FOR_REAL_PRODUCT_BLOCKED')
        result['ingredients'].append(mapped)
    complete = bool(result['ingredients']) and parsed['status'] == 'PARSED' and all(
        x['mapping_status'] == 'VERIFIED' for x in result['ingredients'])
    result['mapping_status'] = 'VERIFIED' if complete else 'REVIEW_REQUIRED' if result['ingredients'] else 'UNRESOLVED'
    result['verified_ddinter_ids'] = list(dict.fromkeys(x['ddinter_id'] for x in result['ingredients']
                                                       if x['mapping_status'] == 'VERIFIED'))
    confirmed = medication.get('transcription_status') in {'USER_CONFIRMED_TRANSCRIPTION', 'VERIFIED'}
    if not confirmed:
        result['identification_status'] = 'REVIEW_REQUIRED'
        result['issues'].append('MODULE1_TRANSCRIPTION_REVIEW_REQUIRED')
    result['ready_for_identifier_handoff'] = complete and result['identification_status'] == 'VERIFIED'
    return result


def module3_input(result, medication_id, prescription_ids):
    medication = result['original_medication']
    candidate = result['identified_candidate']
    # A parser failure can conceal an ingredient. Block the entire product in that case.
    identity = 'VERIFIED' if result['ready_for_identifier_handoff'] else result['identification_status']
    if result.get('ingredient_extraction', {}).get('status') != 'PARSED':
        identity = 'REVIEW_REQUIRED'
    return {'medication_id': medication_id, 'prescription_ids': deepcopy(prescription_ids),
        'brand_name': medication.get('brand_name') or medication.get('name_raw'),
        'identity_status': identity, 'identity_evidence': deepcopy(candidate['source_evidence']) if candidate else [],
        'source_kind': 'synthetic_fixture' if medication.get('synthetic_fixture') else result.get('reference_kind', 'DAV_reference'),
        'identity_verification_scope': result.get('identity_verification_scope', 'historical_product_identity_not_clinical'),
        'upstream_review_issues': deepcopy(result['issues']),
        'ingredients': [{'name': x['ddinter_generic_name'] or x['normalized_ingredient'],
            'original_ingredient_name': x['original_ingredient'], 'strength': x['strength_raw'],
            'ddinter_id': x['ddinter_id'], 'mapping_status': x['mapping_status'],
            'mapping_evidence': deepcopy(x['evidence'])} for x in result['ingredients']]}


def from_module1(extraction, reference, terminology, *, prescription_id='module1-prescription', confirmed=False):
    if not isinstance(extraction, dict):
        raise ValueError('Module 1 input must be an object')
    if isinstance(extraction.get('medications'), list):
        prescriptions = [{'prescription_id': prescription_id, 'medications': extraction['medications']}]
    elif isinstance(extraction.get('prescriptions'), list):
        prescriptions = extraction['prescriptions']
    else:
        raise ValueError('Module 1 input requires medications or prescriptions with medication arrays')
    prepared = []
    for prescription in prescriptions:
        if (not isinstance(prescription, dict) or not isinstance(prescription.get('prescription_id'), str)
                or not prescription['prescription_id'].strip() or not isinstance(prescription.get('medications'), list)):
            raise ValueError('Every prescription requires a nonempty ID and a medications array')
        prepared.extend((prescription['prescription_id'], index, raw)
                        for index, raw in enumerate(prescription['medications'], 1))
    results = []
    for source_prescription, index, raw in prepared:
        if not isinstance(raw, dict):
            raise ValueError('Each Module 1 medication must be an object')
        medication = deepcopy(raw)
        if confirmed and not raw.get('uncertain_fields') and not raw.get('uncertainty_issues'):
            medication['transcription_status'] = 'USER_CONFIRMED_TRANSCRIPTION'
        if raw.get('uncertain_fields') or raw.get('uncertainty_issues'):
            medication['transcription_status'] = 'REVIEW_REQUIRED'
        result = identify(medication, reference, terminology)
        result['module3_input'] = module3_input(result, raw.get('medication_id') or f'{source_prescription}-med-{index}',
                                              raw.get('prescription_ids') or [source_prescription])
        results.append(result)
    return results


def assess_prescriptions(extraction, reference, terminology, **options):
    results = from_module1(extraction, reference, terminology, **options)
    return {'schema_version': 'module2.direct_pipeline.v1', 'module2': results,
        'module3': assess([r['module3_input'] for r in results], terminology.dataset),
        'network_requests': 0, 'external_ai_calls': 0, 'requires_hcp_review': True}
