"""Synthetic medication scenarios with real, previously inspected source entities.

VERIFIED here is a fixture input gate for named drug entities. It is NOT evidence
that these products/prescriptions exist or that a patient's medication is verified.
"""
from copy import deepcopy
import json
from shared.paths import ProjectPath as Path, PROJECT_ROOT
from module3_interactions.engine import module2_input

def fixture(dataset,medication_id,identifiers,prescriptions=None):
    return {'medication_id':medication_id,'prescription_ids':prescriptions or ['fixture-rx-'+medication_id],
      'brand_name':None,'identity_status':'VERIFIED',
      'identity_evidence':[{'kind':'synthetic_scenario_entity_selection',
          'scope':'fixture gate only; not a real product or patient verification'}],
      'source_kind':'synthetic_medication_scenario',
      'ingredients':[{'name':dataset.identities[i]['name'],'ddinter_id':i,
                      'mapping_status':'VERIFIED','strength':None} for i in identifiers]}

def build_scenarios(dataset,project_root):
    a=fixture(dataset,'a',['DDInter1263'],['fixture-rx-1'])
    b=fixture(dataset,'b',['DDInter1'],['fixture-rx-2'])
    c=fixture(dataset,'c',['DDInter1348'],['fixture-rx-3'])
    unknown=deepcopy(c);unknown['ingredients'][0].update(ddinter_id='DDInter999999',name='Unknown test entity')
    ambiguous=deepcopy(c);ambiguous['ingredients'][0].update(mapping_status='AMBIGUOUS',candidate_ddinter_ids=['DDInter1','DDInter1348'])
    conflict=deepcopy(c);conflict['ingredients'][0]['ddinter_id']='DDInter1'
    candidate_path=Path(project_root)/'data/reference/test_fixtures/module2_api_quicktest/ingredient_ddinter_poc/runs/approved_csv_002/mypara500.json'
    candidate=json.loads(candidate_path.read_text(encoding='utf-8'))
    mypara=module2_input(candidate,['scenario-rx-mypara'])
    return {
      'positive_real_source_pair': [a,b],
      'reversed_order': [b,a],
      'three_medications_multiple_prescriptions':[a,b,c],
      'major_real_source_pair':[fixture(dataset,'aluminum',['DDInter58']),fixture(dataset,'dolutegravir',['DDInter582'])],
      'duplicate_ingredient':[b,fixture(dataset,'second_abacavir',['DDInter1'],['fixture-rx-other'])],
      'combination_fixture':[fixture(dataset,'combo',['DDInter1','DDInter1348']),a],
      'unknown_identifier':[b,unknown],
      'ambiguous_identifier':[b,ambiguous],
      'conflicting_name_identifier':[b,conflict],
      'absent_pair_in_subset':[a,c],
      'mypara_real_candidate_review_blocked':[mypara,b],
      'acetaminophen_entity_fixture_absent_pair':[fixture(dataset,'acetaminophen_entity',['DDInter14']),b],
    }
