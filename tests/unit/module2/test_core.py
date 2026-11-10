"""Isolated Module 2/Core reference regressions; no network or database writes."""
from copy import deepcopy
import json
import unicodedata
from uuid import uuid4

import pytest

from module2_medications.core import CoreMedicationReference
from module2_medications.service import identify, from_module1, module3_input
from module2_medications.text import strength_signature

BUILD = 'a' * 64
OTHER_BUILD = 'b' * 64


def evidence(source_id):
    return {'schema': 'csv-source.v4', 'source_id': source_id, 'artifact_sha256': 'c' * 64,
            'legacy_review': {'status': 'REVIEW_REQUIRED', 'accepted': 'false'},
            'source_ref': {'uri': 'synthetic://module2-core-fixture/' + source_id},
            'manifest_locator': {'uri': 'synthetic://build', 'artifact_sha256': BUILD}}


def product(name='Thuốc Thử', strength='500mg', *, build=BUILD, **extra):
    identity = str(uuid4())
    return {'id': identity, 'source_medication_id': identity, 'dataset_build': build,
            'brand_name': name, 'dosage_form': 'Viên nén', 'manufacturer': None, 'route': None,
            'component_count': 1, 'source_locator': evidence(identity),
            'product_details': {'schema': 'product-details.v4', 'registration_token': 'VD-123-26',
                                'source_identity_definition': {'strength': strength}}, **extra}


def component(med, name='Source Alpha', *, ordinal=1, ingredient=True):
    identity = str(uuid4())
    ing = {'id': str(uuid4()), 'source_ingredient_id': 'I' + identity, 'dataset_build': med['dataset_build'],
           'name_original': name, 'name_normalized': name, 'acceptance_scope': 'SYNTHETIC_TEST',
           'source_locator': evidence('I' + identity)} if ingredient else None
    return {'id': identity, 'medication_id': med['id'], 'dataset_build': med['dataset_build'],
            'source_component_id': 'C' + identity, 'ordinal': ordinal, 'ingredient_record': ing,
            'ingredient_id': ing['id'] if ing else None, 'ingredient_name_raw': name,
            'ingredient_text_raw': name + ' 500mg', 'chemical_form_raw': None, 'equivalence_raw': None,
            'strength_basis': {'expression_raw': '500mg'}, 'source_locator': evidence('C' + identity)}


def mapping(comp, target='DDInter900001', name='Synthetic Alpha', **extra):
    identity = str(uuid4())
    loc = evidence('M' + identity)
    loc['source_attributes'] = {'source_name': name}
    return {'id': identity, 'source_mapping_id': 'M' + identity, 'component_id': comp['id'],
            'dataset_build': comp['dataset_build'], 'target_id': target, 'mapping_set_id': 'SET1',
            'target_catalog_sha256': 'd' * 64, 'source_locator': loc,
            'retrieval_evidence': [{'locator': 'synthetic://retrieval', 'sha256': 'e' * 64}], **extra}


class ReferenceRows:
    """Repository read boundary fixture, with explicit relational/build filtering."""
    def __init__(self, products, components=(), mappings=(), *, published=True):
        self.products, self.components, self.mappings = products, list(components), list(mappings)
        self.published = published
        self.queries = []

    def _one(self, sql, params=()):
        if 'msa.published' in sql:
            return {'ok': self.published}
        assert 'obj_description' in sql
        return {'ledger': json.dumps({'builds': {b: {'synthetic': True, 'published': True}
                                                for b in (BUILD, OTHER_BUILD)}})}

    def _all(self, sql, params=()):
        self.queries.append((sql, params))
        if 'SELECT * FROM msa_ref.medications' in sql:
            assert 'dataset_build=%s' in sql
            return deepcopy([p for p in self.products if p['dataset_build'] == params[0]])
        assert len(params) == 2 and 'dataset_build=%s' in sql
        med, build = params
        components = [c for c in self.components if c['medication_id'] == med and c['dataset_build'] == build]
        if 'SELECT c.*' in sql:
            assert 'i.dataset_build=c.dataset_build' in sql
            return deepcopy(components)
        assert 'SELECT d.*' in sql and 'c.dataset_build=d.dataset_build' in sql
        return deepcopy([m for m in self.mappings if m['dataset_build'] == build
                         and m['component_id'] in {c['id'] for c in components}])


@pytest.fixture
def reference():
    med = product()
    comp = component(med)
    repo = ReferenceRows([med], [comp], [mapping(comp)])
    return CoreMedicationReference(repo, BUILD)


def confirmed(**fields):
    return {'name_raw': 'Thuốc Thử', 'transcription_status': 'USER_CONFIRMED_TRANSCRIPTION', **fields}


@pytest.mark.parametrize('dose', ['500 mg', '0,5 g', '500000 µg', '0.5g'])
def test_vietnamese_unicode_strength_and_form(reference, dose):
    query = confirmed(name_raw=unicodedata.normalize('NFD', ' THUỐC   THỬ '),
                      strength_raw=dose, dosage_form_raw=' tablet ')
    result = identify(query, reference)
    assert result['schema_version'] == 'module2.medication_identity.v1'
    assert result['identification_status'] == result['mapping_status'] == 'VERIFIED'
    assert result['ready_for_identifier_handoff']
    assert result['original_medication'] == query
    assert result['interaction_assessment'] == 'NOT_PERFORMED'
    assert result['dataset_build'] == BUILD
    assert len(result['ingredient_extraction']['ingredients']) == 1


def test_unaccented_or_typo_names_are_not_guessed(reference):
    for name in ['Thuoc Thu', 'Thuốc Thửr', 'Thuốc Thử XR']:
        r = identify(confirmed(name_raw=name), reference)
        assert r['identification_status'] in {'UNRESOLVED', 'REVIEW_REQUIRED'}
        assert not r['ready_for_identifier_handoff']
        assert all(not c['establishes_identity'] for c in r['candidates'])


def test_ambiguous_products_retained_without_selection():
    repo = ReferenceRows([product(), product(strength='250mg')])
    ref = CoreMedicationReference(repo, BUILD)
    result = identify(confirmed(), ref)
    assert result['identification_status'] == result['mapping_status'] == 'REVIEW_REQUIRED'
    assert len(result['candidates']) == 2 and result['identified_candidate'] is None
    assert not result['ready_for_identifier_handoff']
    narrowed = ref.lookup(confirmed(strength_raw='0,5g'))
    assert narrowed['complete_identity'] and len(narrowed['candidates']) == 1


@pytest.mark.parametrize('fields', [
    {'manufacturer': 'Unknown manufacturer'}, {'route_raw': 'uống'},
    {'strength_raw': '250mg'}, {'dosage_form_raw': 'Viên nén giải phóng kéo dài'},
    {'name_raw': 'Thuốc Thử', 'brand_name': 'Different'},
    {'strength_raw': '500mg', 'strength': '250mg'},
])
def test_supplied_attributes_never_disappear(reference, fields):
    r = identify(confirmed(**fields), reference)
    assert r['identification_status'] != 'VERIFIED' and not r['ready_for_identifier_handoff']


def test_missing_input_attributes_are_not_invented(reference):
    r = identify(confirmed(), reference)
    assert r['identification_status'] == 'VERIFIED'
    assert 'strength_raw' not in r['original_medication']
    assert r['identified_candidate']['product']['manufacturer'] is None
    missing = identify(confirmed(manufacturer='A'), reference)
    assert missing['identification_status'] == 'REVIEW_REQUIRED'
    assert missing['identified_candidate']['missing_qualifiers'] == ['manufacturer']


def test_registration_is_an_explicit_constraint(reference):
    assert reference.lookup({'registration_token': 'VD-123-26'})['complete_identity']
    assert not reference.lookup(confirmed(registration_token='VD-124-26'))['candidates']
    assert reference.lookup(confirmed(registration_token='garbled'))['issues'] == ['REGISTRATION_UNREADABLE']


@pytest.mark.parametrize('token', ['VD3-192-22', 'SP3-1243-22', 'GC-343-22', 'QLSP-H03-1172-19'])
def test_retained_real_catalog_registration_formats_are_exact_constraints(token):
    med = product()
    med['product_details']['registration_token'] = token
    ref = CoreMedicationReference(ReferenceRows([med]), BUILD)
    by_name = ref.lookup(confirmed(registration_token=token.lower()))
    assert by_name['complete_identity'] and by_name['candidates'][0]['id'] == med['id']
    by_registration = ref.lookup({'registration_token': token})
    assert by_registration['complete_identity'] and by_registration['candidates'][0]['id'] == med['id']
    assert not ref.lookup(confirmed(registration_token=token + '9'))['candidates']


def test_real_catalog_locale_ambiguous_strengths_and_short_numeric_registration_are_not_guessed(reference):
    assert reference.lookup(confirmed(registration_token='89311087026'))['issues'] == ['REGISTRATION_UNREADABLE']
    assert strength_signature('1,578 g')[0] == strength_signature('1,875 g/15 mL')[0] == 'raw'


def test_indexed_anchors_never_override_conflicting_name_registration_or_strength():
    a, b = product(name='Alpha'), product(name='Beta', strength='250mg')
    b['product_details']['registration_token'] = 'GC-343-22'
    ref = CoreMedicationReference(ReferenceRows([a, b]), BUILD)
    assert ref.lookup({'registration_token': 'GC-343-22'})['candidates'][0]['id'] == b['id']
    assert ref.lookup({'name_raw': 'Beta', 'strength_raw': '250mg'})['complete_identity']
    assert ref.lookup({'name_raw': 'Alpha', 'registration_token': 'GC-343-22'})['candidates'] == []
    assert ref.lookup({'registration_token': 'GC-343-22', 'strength_raw': '500mg'})['candidates'] == []


def test_multi_component_and_multiple_targets_keep_all_source_rows():
    med = product(component_count=2)
    a, b = component(med), component(med, ordinal=2, ingredient=False)
    mappings = [mapping(a), mapping(a), mapping(b, 'DDInter900002', 'Synthetic Beta'),
                mapping(b, 'DDInter900003', 'Synthetic Gamma')]
    repo = ReferenceRows([med], [a, b], mappings)
    result = identify(confirmed(), CoreMedicationReference(repo, BUILD))
    assert len(result['ingredients']) == 2
    assert result['identification_status'] == 'VERIFIED'
    assert result['mapping_status'] == 'REVIEW_REQUIRED'
    assert result['verified_ddinter_ids'] == ['DDInter900001']
    assert result['approved_ddinter_ids'] == ['DDInter900001', 'DDInter900002', 'DDInter900003']
    assert result['ingredients'][1]['ddinter_id'] is None
    assert result['ingredients'][1]['ingredient_record'] is None
    preserved = [m for i in result['ingredients'] for m in i['ddinter_mappings']]
    assert preserved == mappings
    assert all(m['source_locator']['legacy_review']['accepted'] == 'false' for m in preserved)
    assert not result['ready_for_identifier_handoff']
    handoff = module3_input(result, 'med1', ['rx1'])
    assert handoff['ingredients'][1]['candidate_ddinter_ids'] == ['DDInter900002', 'DDInter900003']
    assert handoff['ingredients'][1]['ddinter_mappings'] == mappings[2:]
    json.dumps(result)


@pytest.mark.parametrize('targets', [[], [None], ['invalid'], ['DDInter900001', None]])
def test_missing_invalid_and_partial_mappings_never_verify(targets):
    med = product()
    comp = component(med)
    repo = ReferenceRows([med], [comp], [mapping(comp, target=t) for t in targets])
    result = identify(confirmed(), CoreMedicationReference(repo, BUILD))
    assert not result['ready_for_identifier_handoff']
    assert result['ingredients'][0]['ddinter_id'] is None
    assert len(result['ingredients'][0]['ddinter_mappings']) == len(targets)


def test_component_coverage_blocks_whole_product(reference):
    reference.repo.products[0]['component_count'] = 2
    r = identify(confirmed(), reference)
    assert r['ingredient_extraction']['issues'] == ['CORE_COMPONENT_COVERAGE_INCOMPLETE']
    assert not r['ready_for_identifier_handoff']
    assert module3_input(r, 'm', ['rx'])['identity_status'] == 'REVIEW_REQUIRED'


def test_build_isolation_applies_to_every_reference_table():
    med, foreign = product(), product(build=OTHER_BUILD)
    comp = component(med)
    leaked = mapping(comp, target='DDInter999999', dataset_build=OTHER_BUILD)
    repo = ReferenceRows([med, foreign], [comp, component(foreign)], [mapping(comp), leaked])
    r = identify(confirmed(), CoreMedicationReference(repo, BUILD))
    assert len(r['candidates']) == 1 and r['approved_ddinter_ids'] == ['DDInter900001']
    with pytest.raises(ValueError, match='not published'):
        CoreMedicationReference(ReferenceRows([], published=False), BUILD)


def test_returned_evidence_cannot_mutate_cached_reference(reference):
    r = identify(confirmed(), reference)
    r['identified_candidate']['source_evidence'].clear()
    r['ingredients'][0]['ddinter_mappings'][0]['retrieval_evidence'].clear()
    again = identify(confirmed(), reference)
    assert again['identified_candidate']['source_evidence']
    assert again['ingredients'][0]['ddinter_mappings'][0]['retrieval_evidence']


@pytest.mark.parametrize('fields', [{'uncertain_fields': ['name_raw']}, {'uncertainty_raw': 'không chắc'},
                                 {'transcription_status': 'REVIEW_REQUIRED'}])
def test_confirmation_never_overrides_uncertainty(reference, fields):
    r = from_module1({'medications': [confirmed(**fields)]}, reference, confirmed=False)[0]
    assert not r['ready_for_identifier_handoff'] and r['identification_status'] == 'REVIEW_REQUIRED'


def test_concentration_and_percentage_semantics_remain_conservative():
    assert strength_signature('1,34mg/ml') == strength_signature('1.34 mg/1 mL')
    assert strength_signature('500mg/5ml') != strength_signature('500mg/ml')
    assert strength_signature('5%')[0] == 'raw'


@pytest.mark.parametrize('problem', ['unconfirmed', 'digest', 'fields', 'conversation', 'intake', 'latest', 'duplicate'])
def test_confirmed_handoff_rechecks_entire_boundary_before_writes(problem, monkeypatch):
    from module1_intake.nlp.models import Medication, Module2Handoff, ConfirmedEntry
    from module1_intake.nlp.integration.persistence import fields
    from module2_medications.core import identify_confirmed
    convo, intake, entry, item = (uuid4() for _ in range(4))
    med = Medication(name_raw='Thuốc Thử', evidence_text='Thuốc Thử')
    handoff = Module2Handoff(conversation_id=convo, intake_id=intake, requested_workflows=['MEDICATION_INTAKE'],
        entries=[ConfirmedEntry(entry_version_id=entry, content_digest='d' * 64, medication=med)])
    row = {'id': entry, 'item_id': item, 'confirmed_at': 'confirmed',
           'content_digest': 'd' * 64, 'medication_fields': fields(med)}
    if problem == 'unconfirmed': row['confirmed_at'] = None
    if problem == 'digest': row['content_digest'] = 'e' * 64
    if problem == 'fields': handoff.entries[0].medication.strength_raw = '250mg'
    if problem == 'duplicate': handoff.entries.append(handoff.entries[0])

    class GuardRepository:
        owner = uuid4()
        def _owned(self, table, identity):
            return {'conversation_id': uuid4() if problem == 'conversation' else convo} if table == 'intake_sessions' else row
        def _all(self, query, params):
            if 'p.session_id' in query:
                return [{'session_id': uuid4() if problem == 'intake' else intake}]
            return [{'id': uuid4() if problem == 'latest' else entry}]

    def no_match(*args, **kwargs):
        pytest.fail('Invalid handoff reached the matcher')
    monkeypatch.setattr('module2_medications.core.run_identification', no_match)
    with pytest.raises(ValueError):
        identify_confirmed(GuardRepository(), handoff, dataset_build=BUILD)


def test_existing_legacy_reference_and_service_contract(tmp_path):
    from module2_medications import CoreMedicationReference as PublicCoreReference, identify_confirmed
    assert PublicCoreReference is CoreMedicationReference and callable(identify_confirmed)
    from module2_medications.fixtures import fixture_db
    from module2_medications.reference import MedicationReference, review_product
    from module2_medications.terminology import DirectDDInter
    from module3_interactions.engine import BoundedDataset, assess
    db, _, _ = fixture_db(tmp_path)
    ref = MedicationReference(db, allow_synthetic=True)
    try:
        row = {'DDInterID_A': 'DDInter582', 'Drug_A': 'Dolutegravir',
               'DDInterID_B': 'DDInter24', 'Drug_B': 'Aluminum hydroxide', 'Level': 'Major'}
        dataset = BoundedDataset([row], {'loaded_rows': 1, 'synthetic_fixture': True,
                                        'scope': 'Synthetic Module 2 contract regression'})
        query = {'name_raw': 'Fixture Dolutegravir', 'synthetic_fixture': True,
                 'transcription_status': 'USER_CONFIRMED_TRANSCRIPTION'}
        cid = ref.lookup(query)['candidates'][0]['candidate_key']
        review_product(db, cid, status='VERIFIED', reviewer='Synthetic reviewer',
                       evidence=[{'locator': 'synthetic://review', 'sha256': 'a' * 64}])
        result = from_module1({'medications': [query]}, ref, DirectDDInter(dataset))[0]
        assert result['ready_for_identifier_handoff']
        assert not assess([result['module3_input']], dataset)['unresolved_mappings']
    finally:
        ref.close()
