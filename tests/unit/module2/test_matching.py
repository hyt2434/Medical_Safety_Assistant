"""Conservative strength equivalence and non-authoritative review candidates."""
from copy import deepcopy

import pytest

from module2_medications.core import CoreMedicationReference
from module2_medications.service import identify, module3_input
from module2_medications.text import strength_signature, complete_strength_signature
from tests.unit.module2.test_core import BUILD, OTHER_BUILD, ReferenceRows, product, component, mapping, confirmed


@pytest.mark.parametrize('left,right', [
    ('500mg/5ml', '100 mg/mL'), ('0,5g/5ml', '100mg/ml'),
    ('1mg/3ml', '2mg/6ml'), ('1g', '1000000μg'), ('2 gam', '2000mg'),
    ('0,2% (w/v)', '2mg/ml'), ('2% kl/tt', '20mg/ml'),
    ('2% (w/w)', '20mg/g'), ('2% kl/kl', '20mg/g'),
    ('2% (v/v)', '20ml/l'), ('2% tt/tt', '20ml/l'),
    ('20mg/ml (2% (w/v))', '100mg/5ml'),
    ('1.000.000 IU', '1 MIU'), ('1,000,000 UI', '1000000iu'),
    ('3 triệu iu', '3000000IU'),
    ('Paracetamol 500mg; Caffeine 65mg', 'caffeine 65000mcg + paracetamol 0,5g'),
    ('Minoxidil 20mg/ml', 'minoxidil 2% (w/v)'),
])
def test_only_explicit_complete_equivalences_normalize(left, right):
    assert strength_signature(left)[0] != 'raw'
    assert strength_signature(left) == strength_signature(right)


@pytest.mark.parametrize('left,right', [
    ('1mg/3ml', '0.3333333333mg/ml'), ('2% (w/v)', '2% (w/w)'),
    ('2% (v/v)', '2% (w/v)'), ('1IU', '1mg'),
    ('500mg;65mg', '65mg;500mg'),
    ('Paracetamol 500mg; Caffeine 65mg', 'Paracetamol 65mg; Caffeine 500mg'),
    ('Amoxicillin hydrochloride 500mg', 'Amoxicillin 500mg'),
])
def test_basis_labels_units_and_component_associations_are_not_discarded(left, right):
    assert strength_signature(left) != strength_signature(right)


@pytest.mark.parametrize('value', ['5%', '0,01', '750.000IU', '1,578g', '1.875g/15ml',
    '1mIU', '1miu', '20mg/ml (5% w/v)', 'A 10mg; 20mg', 'A 10mg; A 20mg',
    'mỗi 5ml chứa amoxicillin 500mg', 'A tương đương B 20mg', '5mg (salt',
    '1,000.000IU', '0mg', '5mg/0ml'])
def test_ambiguous_or_incomplete_strengths_stay_raw(value):
    assert strength_signature(value)[0] == 'raw'


def test_long_decimal_values_are_never_rounded_into_the_same_identity():
    left = '0.123456789012345678901234567891mg/ml'
    right = '0.123456789012345678901234567892mg/ml'
    assert strength_signature(left) != strength_signature(right)
    assert strength_signature(left) == strength_signature('0.000123456789012345678901234567891g/ml')
    assert strength_signature('1mg ' + '(' * 1000 + '1mg' + ')' * 1000)[0] == 'raw'


def reference_for(strength='500mg', *, name='Paracetamol', ingredient='Paracetamol', count=1):
    med = product(name=name, strength=strength, component_count=count)
    med['product_details']['source_identity_definition']['ingredients'] = ingredient
    comp = component(med)
    return CoreMedicationReference(ReferenceRows([med], [comp], [mapping(comp)]), BUILD)


def test_one_label_is_removed_only_with_agreeing_single_component_evidence():
    ref = reference_for('minoxidil 20mg/ml', name='Minorga', ingredient='minoxidil')
    result = identify(confirmed(name_raw='Minorga', strength_raw='2% w/v'), ref)
    assert result['identification_status'] == 'VERIFIED'
    assert result['original_medication']['strength_raw'] == '2% w/v'
    assert result['identified_candidate']['product']['strength'] == 'minoxidil 20mg/ml'
    assert ref.lookup({'name_raw': 'Minorga', 'strength_raw': 'OTHER 20mg/ml'})['candidates'] == []
    missing_evidence = reference_for('minoxidil 20mg/ml', name='Minorga', ingredient='unknown source label')
    assert not missing_evidence.lookup({'name_raw': 'Minorga', 'strength_raw': '20mg/ml'})['complete_identity']


def test_named_profile_cannot_conceal_a_missing_component():
    ref = reference_for('Paracetamol 500mg', count=2)
    result = ref.lookup({'name_raw': 'Paracetamol', 'strength_raw': 'Paracetamol 500mg'})
    assert not complete_strength_signature(strength_signature('Paracetamol 500mg'), 2)
    assert result['identification_status'] == 'REVIEW_REQUIRED'


def test_equivalent_concentrations_expose_duplicate_products_instead_of_selecting_one():
    rows = [product(name='Same Brand', strength=s) for s in ('500mg/5ml', '100mg/ml')]
    ref = CoreMedicationReference(ReferenceRows(rows), BUILD)
    result = ref.lookup({'name_raw': 'Same Brand', 'strength_raw': '100mg/ml'})
    assert result['identification_status'] == 'REVIEW_REQUIRED'
    assert {c['id'] for c in result['candidates']} == {r['id'] for r in rows}
    assert all(not c['establishes_identity'] for c in result['candidates'])


@pytest.mark.parametrize('name', ['Paracetamo1', 'Paracetmaol', 'Paracetmol', 'Paracetamoll'])
def test_ocr_and_typo_candidates_never_verify_even_when_unique_and_confirmed(name):
    ref = reference_for()
    result = identify(confirmed(name_raw=name, strength_raw='500mg'), ref)
    assert result['identification_status'] == 'REVIEW_REQUIRED'
    assert not result['ready_for_identifier_handoff'] and not result['complete_identity']
    candidate = result['candidates'][0]
    assert candidate['match_kind'] == 'SIMILAR_NAME_REVIEW_ONLY' and not candidate['establishes_identity']
    assert candidate['source_evidence'] == [ref.repo.products[0]['source_locator']]
    assert result['ingredients'][0]['ddinter_mappings'] == ref.repo.mappings
    assert module3_input(result, 'med', ['rx'])['identity_status'] == 'REVIEW_REQUIRED'


def test_numeric_release_and_explicit_strength_conflicts_never_become_fuzzy_candidates():
    ref = reference_for(name='Drug 20 XR')
    for name in ('Drug 25 XR', 'Drug 2O XR', 'Drug 20 SR', 'Drug 20 X'):
        assert ref.lookup({'name_raw': name})['candidates'] == []
    ref = reference_for()
    assert ref.lookup({'name_raw': 'Paracetamoll', 'strength_raw': '250mg'})['candidates'] == []


def test_multi_character_ocr_proposals_and_registration_still_require_name_review():
    ref = reference_for(name='Metformin')
    result = ref.lookup({'name_raw': 'Metforrnin', 'registration_token': 'VD-123-26'})
    assert result['identification_status'] == 'REVIEW_REQUIRED' and not result['complete_identity']
    assert result['candidates'][0]['match_kind'] == 'SIMILAR_NAME_REVIEW_ONLY'
    result = ref.lookup({'name_raw': 'Metforrnin'})
    assert result['candidates'] and result['identification_status'] == 'REVIEW_REQUIRED'


def test_unsupported_strength_retains_exact_name_for_review_without_ignoring_conflict():
    ref = reference_for()
    result = ref.lookup({'name_raw': 'Paracetamol', 'strength_raw': 'unreadable strength'})
    assert result['identification_status'] == 'REVIEW_REQUIRED'
    assert result['candidates'][0]['unresolved_qualifiers'] == ['strength_raw']
    assert not result['candidates'][0]['establishes_identity']
    assert ref.lookup({'name_raw': 'Paracetamol', 'strength_raw': '250mg'})['candidates'] == []


def test_attribute_only_candidates_require_two_known_attributes_and_never_establish_identity():
    ref = reference_for()
    assert ref.lookup({'strength_raw': '500mg'})['identification_status'] == 'UNRESOLVED'
    r = ref.lookup({'strength_raw': '0,5g', 'dosage_form_raw': 'tablet'})
    assert r['identification_status'] == 'REVIEW_REQUIRED' and not r['complete_identity']
    assert r['candidates'][0]['match_kind'] == 'ATTRIBUTES_REVIEW_ONLY'
    assert not r['candidates'][0]['establishes_identity']


def test_broad_missing_name_request_is_not_reduced_to_an_arbitrary_product():
    ref = CoreMedicationReference(ReferenceRows([product(name=f'Product {n}') for n in range(25)]), BUILD)
    r = ref.lookup({'strength_raw': '500mg', 'dosage_form_raw': 'tablet'})
    assert r['identification_status'] == 'UNRESOLVED' and r['candidates'] == []
    assert r['review_candidate_count'] == 25 and 'MISSING_ANCHOR_TOO_MANY_CANDIDATES_PROVIDE_NAME' in r['issues']


def test_fuzzy_candidates_respect_build_isolation_and_return_independent_evidence():
    local, foreign = product(name='Paracetamol'), product(name='Paracetamoll', build=OTHER_BUILD)
    ref = CoreMedicationReference(ReferenceRows([local, foreign]), BUILD)
    first = ref.lookup({'name_raw': 'Paracetamoll'})
    assert [c['id'] for c in first['candidates']] == [local['id']]
    original = deepcopy(first['candidates'][0]['source_evidence'])
    first['candidates'][0]['source_evidence'].clear()
    assert ref.lookup({'name_raw': 'Paracetamoll'})['candidates'][0]['source_evidence'] == original
