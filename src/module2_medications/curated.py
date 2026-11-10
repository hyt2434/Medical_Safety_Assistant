"""Small manually maintained factual research reference; not a DAV export importer.

This backend uses the existing conservative product keys and the identify service
contract. Bulk import, observations, grants and regulatory states are untouched.
VERIFIED here means the hash-linked historical product facts were reviewed, never
clinical suitability, regulatory validity, or authorization to copy a registry.
"""
from copy import deepcopy
import hashlib
import json
from shared.paths import ProjectPath as Path, PROJECT_ROOT
from .reference import candidate_key
from .text import brand_key, strength_key, form_key, key, registration


class CuratedFactReference:
    def __init__(self, path):
        self.path = Path(path)
        artifact = json.loads(self.path.read_text(encoding='utf-8'))
        if artifact.get('schema_version') != 'module2.curated_product_facts.v1':
            raise ValueError('Unsupported curated fact reference')
        decision = artifact.get('use_assessment', {})
        if decision.get('decision') != 'LOCAL_FACTS_ONLY' or not decision.get('source_basis'):
            raise ValueError('Missing scoped factual-use assessment; no authorization inferred')
        self.products = artifact.get('products', [])
        if not 1 <= len(self.products) <= 4:
            raise ValueError('Curated test reference is limited to four individually reviewed products')
        seen = set()
        for entry in self.products:
            product = entry['product']
            review = entry.get('fact_review', {})
            if review.get('status') != 'SOURCE_SUPPORTED' or not review.get('reviewer') or not review.get('reviewed_at'):
                raise ValueError('Each historical product fact requires explicit source review')
            if not entry.get('source_evidence') or product.get('synthetic_fixture'):
                raise ValueError('Real product facts with evidence are required')
            if product['registration_number'] in seen:
                raise ValueError('Duplicate registration requires review')
            seen.add(product['registration_number'])
            for proof in entry['source_evidence']:
                if not proof.get('locator') or not proof.get('source_url'):
                    raise ValueError('Evidence requires an explicit source locator')
                path = Path(proof['path'])
                if hashlib.sha256(path.read_bytes()).hexdigest() != proof.get('sha256'):
                    raise ValueError('Curated source evidence hash mismatch')

    def lookup(self, medication):
        result = {'identification_status': 'UNRESOLVED', 'lookup_method': 'CURATED_EXACT_PRODUCT_FACTS',
                  'candidates': [], 'suggestions': [], 'issues': [], 'current_authorization': 'UNKNOWN',
                  'reference_kind': 'curated_source_product_facts',
                  'identity_verification_scope': 'source_supported_historical_product_facts_only',
                  'clinical_verified': False, 'regulatory_current_verified': False}
        if medication.get('synthetic_fixture'):
            result['issues'].append('SYNTHETIC_INPUT_NOT_SUPPORTED')
            return result
        brand = medication.get('brand_name') or medication.get('name_raw')
        reg = medication.get('registration_number')
        if not brand and not reg:
            result['issues'].append('BRAND_OR_REGISTRATION_REQUIRED')
            return result
        if reg and registration(reg) is None:
            result['issues'].append('REGISTRATION_UNREADABLE')
            return result
        for entry in self.products:
            product = entry['product']
            if brand and brand_key(brand) != brand_key(product['brand_name']):
                continue
            if reg and registration(reg) != registration(product['registration_number']):
                continue
            constraints = [('strength','strength_raw',strength_key),
                           ('dosage_form','dosage_form_raw',form_key),
                           ('manufacturer','manufacturer_raw',key)]
            if any((value := medication.get(field) or medication.get(raw)) and
                   normalize(value) != normalize(product.get(field)) for field,raw,normalize in constraints):
                continue
            result['candidates'].append({'candidate_key': candidate_key(product), 'product': deepcopy(product),
                'registration_number': product['registration_number'], 'source_evidence': deepcopy(entry['source_evidence']),
                'synthetic_fixture': False, 'independent_review': deepcopy(entry['fact_review']),
                'ingestion_statuses': ['CURATED_FACTS_NOT_DAV_BULK_INGESTION'],
                'registration_description_conflict': False, 'current_authorization': 'UNKNOWN',
                'product_review_state': 'SOURCE_SUPPORTED', 'clinical_verified': False})
        if len(result['candidates']) == 1:
            result['identification_status'] = 'VERIFIED'
        elif result['candidates']:
            result.update(identification_status='REVIEW_REQUIRED', issues=['MULTIPLE_PRODUCT_CANDIDATES'])
        else:
            result['issues'].append('NO_CANDIDATE_SATISFIES_SUPPLIED_IDENTITY')
        return result

    def close(self):
        pass
