"""Module 2 projection of the published Core V4 reference; no reference writes."""
from copy import deepcopy
from collections import defaultdict
import json
from difflib import SequenceMatcher

from shared.db.identification_adapter import CoreMedicationReference as CoreReferenceAdapter
from shared.db.identification_adapter import run_identification
from shared.db.intake_adapter import assert_latest_entry, entry_medication
from shared.intake_contracts import Module2Handoff
from shared.dav_import.normalize import parse_strength
from module3_interactions.engine import valid_id

from .text import (brand_key, clean, key, normalized_form, registration, strength_signature,
                   comparable_strength, complete_strength_signature, review_name_compatible, ocr_name_key)


class CoreMedicationReference(CoreReferenceAdapter):
    """Extend the shared adapter with Module 2 normalization and source projections.

    One instance pins one immutable published build. The index is in memory only;
    neither source rows nor historical review flags are rewritten or filtered.
    """
    def __init__(self, repo, dataset_build):
        super().__init__(repo, dataset_build)
        ledger = repo._one("SELECT obj_description('msa_ref'::regnamespace,'pg_namespace') AS ledger")
        self.build_metadata = json.loads(ledger['ledger'])['builds'][dataset_build]
        self._products = None
        self._names = defaultdict(list)
        self._registrations = defaultdict(list)
        self._strengths = defaultdict(list)
        self._forms = defaultdict(set)
        self._deletions = defaultdict(set)
        self._ocr_names = defaultdict(set)
        self._source_strengths = {}

    def _load(self):
        if self._products is not None:
            return
        self._products = self.repo._all(
            'SELECT * FROM msa_ref.medications WHERE dataset_build=%s ORDER BY id', (self.build,))
        for row in self._products:
            name = brand_key(row['brand_name'])
            self._names[name].append(row)
            token = registration(row['product_details'].get('registration_token'))
            if token is not None:
                self._registrations[token].append(row)
            definition = row['product_details'].get('source_identity_definition') or {}
            original_signature = strength_signature(definition.get('strength'))
            signature = comparable_strength(original_signature,
                                            definition.get('ingredients'), row['component_count'])
            self._source_strengths[str(row['id'])] = signature
            if signature[0] != 'raw':
                self._strengths[signature].append(row)
                if original_signature != signature:
                    self._strengths[original_signature].append(row)
            if row.get('dosage_form'):
                self._forms[normalized_form(row['dosage_form'])].add(str(row['id']))
        for name in self._names:
            if 4 <= len(name) <= 120:
                self._ocr_names[ocr_name_key(name)].add(name)
                for i in range(len(name)):
                    self._deletions[name[:i] + name[i + 1:]].add(name)

    def _review_names(self, query):
        if not 4 <= len(query) <= 120:
            return []
        possible = set(self._ocr_names.get(ocr_name_key(query), ()))
        for token in {query, *(query[:i] + query[i + 1:] for i in range(len(query)))}:
            possible.update(self._deletions.get(token, ()))
            if token in self._names:
                possible.add(token)
        return sorted((n for n in possible if review_name_compatible(query, n)),
                      key=lambda n: (-SequenceMatcher(None, query, n).ratio(), n))

    def lookup(self, fields):
        if not isinstance(fields, dict):
            raise ValueError('Medication input must be an object')
        result = {'identification_status': 'UNRESOLVED', 'lookup_method': 'CORE_V4_NORMALIZED_EXACT',
                  'candidates': [], 'suggestions': [], 'issues': [], 'limitations': [],
                  'complete_identity': False, 'dataset_build': self.build,
                  'reference_build_metadata': deepcopy(self.build_metadata),
                  'reference_kind': 'Core_V4', 'current_authorization': 'UNKNOWN',
                  'identity_verification_scope': 'approved_reference_identity_not_clinical'}
        # All provided aliases are constraints; contradictory aliases never win by precedence.
        specs = (
            ('name_raw', 'brand_name', brand_key), ('strength_raw', 'strength', strength_signature),
            ('dosage_form_raw', 'dosage_form', normalized_form), ('route_raw', 'route', key),
            ('registration_token', 'registration_number', registration),
            ('manufacturer', 'manufacturer_raw', key),
        )
        supplied = {}
        for primary, alias, normalize in specs:
            values = [fields[n] for n in (primary, alias) if clean(fields.get(n))]
            if any(not isinstance(v, str) for v in values):
                raise ValueError('Identity fields must be strings or null')
            if values:
                normalized = [normalize(v) for v in values]
                if any(v != normalized[0] for v in normalized):
                    result['issues'].append('CONFLICTING_INPUT_' + primary.upper())
                supplied[primary] = normalized[0]
        result['normalized_input'] = deepcopy(supplied)
        if result['issues']:
            result['identification_status'] = 'REVIEW_REQUIRED'
            return result
        if 'registration_token' in supplied and supplied['registration_token'] is None:
            result['issues'].append('REGISTRATION_UNREADABLE')
            return result
        mode = 'EXACT'
        self._load()
        if 'name_raw' not in supplied and 'registration_token' not in supplied:
            result['issues'].append('BRAND_OR_REGISTRATION_REQUIRED')
            if 'strength_raw' not in supplied or supplied['strength_raw'][0] == 'raw' or 'dosage_form_raw' not in supplied:
                return result
            mode = 'ATTRIBUTES_REVIEW_ONLY'
            allowed = self._forms.get(supplied['dosage_form_raw'], set())
            rows = [r for r in self._strengths.get(supplied['strength_raw'], []) if str(r['id']) in allowed]
            if len(rows) > 20 and set(supplied) == {'strength_raw', 'dosage_form_raw'}:
                result['review_candidate_count'] = len(rows)
                result['issues'].append('MISSING_ANCHOR_TOO_MANY_CANDIDATES_PROVIDE_NAME')
                result['limitations'] = list(result['issues'])
                return result
        else:
            rows = (self._names.get(supplied['name_raw'], []) if 'name_raw' in supplied else
                    self._registrations.get(supplied['registration_token'], []))
            if not rows and 'name_raw' in supplied and 'registration_token' not in supplied:
                names = self._review_names(supplied['name_raw'])
                mode = 'SIMILAR_NAME_REVIEW_ONLY'
                rows = [row for name in names[:5] for row in self._names[name]]
                if len(names) > 5:
                    result['issues'].append('SIMILAR_NAME_RESULTS_LIMITED_TO_FIVE_NAME_GROUPS')
            elif not rows and 'name_raw' in supplied and 'registration_token' in supplied:
                rows = [r for r in self._registrations.get(supplied['registration_token'], [])
                        if review_name_compatible(supplied['name_raw'], brand_key(r['brand_name']))]
                mode = 'SIMILAR_NAME_REVIEW_ONLY'
        # The published build is immutable. Shortlisting by an exact required
        # anchor avoids rescanning the catalog; all qualifiers still apply below.
        attribute_matches = 0
        for row in rows:
            details = row['product_details']
            definition = details.get('source_identity_definition') or {}
            actual = {'name_raw': row['brand_name'], 'strength_raw': definition.get('strength'),
                      'dosage_form_raw': row.get('dosage_form'), 'route_raw': row.get('route'),
                      'registration_token': details.get('registration_token'),
                      'manufacturer': row.get('manufacturer')}
            missing, unresolved, incompatible = [], [], False
            for primary, alias, normalize in specs:
                if primary not in supplied:
                    continue
                value = actual[primary]
                if not clean(value):
                    missing.append(primary)
                elif primary == 'name_raw' and mode == 'SIMILAR_NAME_REVIEW_ONLY':
                    unresolved.append(primary)
                elif primary == 'strength_raw':
                    expected = self._source_strengths[str(row['id'])]
                    given = comparable_strength(supplied[primary], definition.get('ingredients'), row['component_count'])
                    if (not complete_strength_signature(expected, row['component_count']) or
                            not complete_strength_signature(given, row['component_count'])):
                        unresolved.append(primary)
                    elif expected != given:
                        incompatible = True
                        break
                elif normalize(value) != supplied[primary]:
                    incompatible = True
                    break
            # A name/registration anchor must actually match, never match an unknown value.
            anchors = [n for n in ('name_raw', 'registration_token') if n in supplied]
            if incompatible or any(n in missing for n in anchors):
                continue
            if mode == 'ATTRIBUTES_REVIEW_ONLY':
                attribute_matches += 1
                if attribute_matches > 20:
                    continue
            product = {**deepcopy(definition), 'brand_name': row['brand_name'],
                       'dosage_form': row.get('dosage_form'), 'route': row.get('route'),
                       'manufacturer': row.get('manufacturer'),
                       'registration_number': details.get('registration_token')}
            result['candidates'].append({
                'id': str(row['id']), 'candidate_key': str(row['id']),
                'source_medication_id': row['source_medication_id'], 'dataset_build': self.build,
                'product': product, 'product_details': deepcopy(details),
                'component_count': row.get('component_count'), 'missing_qualifiers': missing,
                'unresolved_qualifiers': unresolved, 'match_kind': mode,
                'establishes_identity': False,
                'source_locator': deepcopy(row['source_locator']),
                'source_evidence': [deepcopy(row['source_locator'])],
                'synthetic_fixture': bool(self.build_metadata.get('synthetic'))})
        if mode == 'ATTRIBUTES_REVIEW_ONLY' and attribute_matches > 20:
            result['review_candidate_count'] = attribute_matches
            result['candidates'] = []
            result['issues'].append('MISSING_ANCHOR_TOO_MANY_CANDIDATES_PROVIDE_NAME')
        if result['candidates'] and mode != 'EXACT':
            result['lookup_method'] = 'CORE_V4_' + mode
            result['issues'].append(mode)
            result['suggestions'] = [{'candidate_key': c['candidate_key'], 'brand_name': c['product']['brand_name'],
                                     'status': 'REVIEW_REQUIRED', 'establishes_identity': False}
                                    for c in result['candidates']]
        if not result['candidates']:
            result['issues'].append('NO_CANDIDATE_SATISFIES_SUPPLIED_IDENTITY')
            return result
        if len(result['candidates']) > 1:
            result['issues'].append('MULTIPLE_PRODUCT_CANDIDATES')
        if any(c['missing_qualifiers'] for c in result['candidates']):
            result['issues'].append('SUPPLIED_QUALIFIER_MISSING_IN_REFERENCE')
        if any('strength_raw' in c['unresolved_qualifiers'] for c in result['candidates']):
            result['issues'].append('STRENGTH_SEMANTICS_REVIEW_REQUIRED')
        if fields.get('uncertain_fields') or fields.get('uncertainty_issues') or fields.get('uncertainty_raw'):
            result['issues'].append('MODULE1_IDENTITY_UNCERTAINTY')
        result['complete_identity'] = not result['issues']
        if result['complete_identity']:
            result['candidates'][0]['establishes_identity'] = True
        result['identification_status'] = 'VERIFIED' if result['complete_identity'] else 'REVIEW_REQUIRED'
        result['limitations'] = list(result['issues'])
        return result

    def mapped_ingredients(self, candidate):
        """Keep every relational component, ingredient record and mapping row."""
        rows = self.repo._all('''SELECT c.*, row_to_json(i) AS ingredient_record
            FROM msa_ref.medication_ingredients c LEFT JOIN msa_ref.ingredients i
              ON i.id=c.ingredient_id AND i.dataset_build=c.dataset_build
            WHERE c.medication_id=%s AND c.dataset_build=%s ORDER BY c.ordinal''',
            (candidate['id'], self.build))
        mappings = self.repo._all('''SELECT d.* FROM msa_ref.ddinter_mappings d
            JOIN msa_ref.medication_ingredients c ON c.id=d.component_id AND c.dataset_build=d.dataset_build
            WHERE c.medication_id=%s AND d.dataset_build=%s ORDER BY d.id''',
            (candidate['id'], self.build))
        ingredients = []
        for row in rows:
            ingredient = deepcopy(row['ingredient_record'])
            targets = [deepcopy(m) for m in mappings if str(m['component_id']) == str(row['id'])]
            # UUIDs in public/persisted evidence are strings, while every other source value survives.
            for mapping in targets:
                mapping['id'], mapping['component_id'] = str(mapping['id']), str(mapping['component_id'])
            ids = sorted({m['target_id'] for m in targets if valid_id(m['target_id'])})
            names = {m['source_locator'].get('source_attributes', {}).get('source_name') for m in targets}
            names.discard(None)
            complete = bool(targets) and all(valid_id(m['target_id']) for m in targets)
            status = 'VERIFIED' if complete and len(ids) == 1 else 'REVIEW_REQUIRED' if targets else 'UNRESOLVED'
            strength = (row.get('strength_basis') or {}).get('expression_raw')
            ingredients.append({
                'component_id': str(row['id']), 'source_component_id': row['source_component_id'],
                'dataset_build': self.build, 'ordinal': row['ordinal'], 'ingredient_record': ingredient,
                'component_record': {k: str(v) if k in {'id', 'medication_id', 'ingredient_id'} and v is not None
                                     else deepcopy(v) for k, v in row.items() if k != 'ingredient_record'},
                'original_ingredient': row['ingredient_text_raw'],
                'normalized_ingredient': (ingredient or {}).get('name_normalized') or
                                         (ingredient or {}).get('name_original') or row.get('ingredient_name_raw'),
                'source_form_declaration': row.get('chemical_form_raw'),
                'strength_raw': strength, 'strength': parse_strength(strength),
                'extraction_status': 'PARSED', 'extraction_issues': [],
                # Core preserves the source target name inside the mapping locator; no dictionary guess.
                'ddinter_generic_name': next(iter(names)) if len(names) == 1 and status == 'VERIFIED' else None,
                'ddinter_id': ids[0] if status == 'VERIFIED' else None,
                'candidate_ddinter_ids': ids, 'ddinter_mappings': targets, 'mapping_status': status,
                'match_method': 'APPROVED_CORE_V4_COMPONENT_MAPPINGS',
                'unresolved_reason': None if status == 'VERIFIED' else
                                     'MULTIPLE_OR_INCOMPLETE_CORE_TARGETS' if targets else 'NO_CORE_MAPPING',
                'evidence': [deepcopy(row['source_locator']),
                             *([deepcopy(ingredient['source_locator'])] if ingredient else []),
                             *[deepcopy(m['source_locator']) for m in targets],
                             *[deepcopy(e) for m in targets for e in m['retrieval_evidence']]]})
        complete = bool(rows) and candidate['component_count'] == len(rows)
        extracted = [{k: deepcopy(i[k]) for k in ('ordinal', 'original_ingredient', 'normalized_ingredient',
                      'strength_raw', 'strength', 'source_form_declaration', 'extraction_status')}
                     | {'issues': deepcopy(i['extraction_issues'])} for i in ingredients]
        return ingredients, {'original_text': candidate.get('product', {}).get('ingredients'),
                             'original_strength': candidate.get('product', {}).get('strength'),
                             'ingredients': extracted, 'status': 'PARSED' if complete else 'REVIEW_REQUIRED',
                             'issues': [] if complete else ['CORE_COMPONENT_COVERAGE_INCOMPLETE']}


def _input_evidence(repo, row, intake_id):
    """Keep original and corrected input provenance separate from reference evidence."""
    item = repo._owned('intake_items', row['item_id'])
    source_extraction = row.get('source_extraction_id')
    extractions, inputs = {}, {}
    for identity in (item['extraction_id'], source_extraction):
        if identity is None:
            continue
        extraction = repo._owned('intake_extractions', identity)
        inp = repo._owned('intake_inputs', extraction['input_id'])
        if str(inp['session_id']) != str(intake_id):
            raise ValueError('Source extraction belongs to a different intake')
        extractions[str(identity)] = {k: deepcopy(extraction[k]) for k in (
            'id', 'input_id', 'attempt_no', 'extractor_name', 'extractor_version', 'status', 'result', 'errors') if k in extraction}
        inputs[str(inp['id'])] = {k: deepcopy(inp[k]) for k in (
            'id', 'session_id', 'message_id', 'modality', 'content_type', 'payload_or_locator', 'input_digest') if k in inp}
    return json.loads(json.dumps({'item_id': str(item['id']), 'origin_evidence': deepcopy(item.get('origin_evidence')),
        'source_extraction_id': str(source_extraction) if source_extraction is not None else None,
        'issues': [] if source_extraction is not None else ['CURRENT_SOURCE_EXTRACTION_NOT_RECORDED'],
        'inputs': list(inputs.values()), 'extractions': list(extractions.values())}, default=str))


def identify_confirmed(repo, handoff: Module2Handoff, *, dataset_build):
    """Consume the unchanged Module 1 DTO and persist through the existing Core adapter.

    Validate the whole DTO before matching any entry. The NLP compatibility
    handoff delegates here so there is one authoritative identification boundary.
    """
    from .service import identify

    intake = repo._owned('intake_sessions', handoff.intake_id)
    if str(intake['conversation_id']) != str(handoff.conversation_id):
        raise ValueError('Handoff conversation differs from its owned intake')
    entries = []
    seen = set()
    for item in handoff.entries:
        if item.entry_version_id in seen:
            raise ValueError('Duplicate handoff entry')
        seen.add(item.entry_version_id)
        row = repo._owned('medication_entry_versions', item.entry_version_id)
        sources = repo._all('''SELECT p.session_id FROM msa.intake_items i
            JOIN msa.intake_extractions x ON x.id=i.extraction_id
            JOIN msa.intake_inputs p ON p.id=x.input_id WHERE i.id=%s AND i.user_id=%s''',
            (row['item_id'], repo.owner))
        if not sources or str(sources[0]['session_id']) != str(handoff.intake_id):
            raise ValueError('Handoff entry belongs to a different intake')
        assert_latest_entry(repo, row)
        if row['confirmed_at'] is None or row['content_digest'] != item.content_digest:
            raise ValueError('Handoff is stale or unconfirmed')
        if entry_medication(row) != item.medication:
            raise ValueError('Handoff fields differ from confirmed Core version')
        if not item.medication.negation_raw:
            entries.append(row)
    if not entries:
        return []
    entries = [(row, _input_evidence(repo, row, handoff.intake_id)) for row in entries]
    reference = CoreMedicationReference(repo, dataset_build)
    results = []
    for row, input_evidence in entries:
        fields = {**deepcopy(row['medication_fields']), 'transcription_status': 'USER_CONFIRMED_TRANSCRIPTION'}
        identity = identify(fields, reference)
        crosswalk = {c['candidate_key']: c['id'] for c in identity['candidates']}
        match, _ = run_identification(repo, row['id'], dataset_build=dataset_build,
            reference=reference, accepted_source_crosswalk=crosswalk, matcher_version='module2-core-v4-normalized-v1')
        identity['confirmation_evidence'] = {'entry_version_id': str(row['id']),
                                              'content_digest': row['content_digest']}
        identity['input_evidence'] = input_evidence
        results.append((match, identity))
    return results
