"""Offline tests; source fixtures never imply clinical validation."""
from copy import deepcopy
import json
from shared.paths import ProjectPath as Path, PROJECT_ROOT
import unittest
from module3_interactions.engine import BoundedDataset,assess,load_existing_dataset,module2_input
from tests.unit.module3.scenarios import fixture,build_scenarios

ROOT = PROJECT_ROOT
class EngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dataset=load_existing_dataset(ROOT)
        cls.scenarios=build_scenarios(cls.dataset,ROOT)
    def run_scenario(self,name):return assess(deepcopy(self.scenarios[name]),self.dataset)
    def med(self,identifier,med_id='test'):return fixture(self.dataset,med_id,[identifier])

    def test_real_positive_record(self):
        result=self.run_scenario('positive_real_source_pair')
        match=result['matched_interactions'][0]
        self.assertEqual(match['drug_id_pair'],['DDInter1','DDInter1263'])
        self.assertEqual(match['original_level'],'Moderate')
        self.assertEqual(match['source_records'][0]['evidence']['csv_record_1_based'],1)
        self.assertFalse(match['source_records'][0]['evidence']['source_kind']=='synthetic_fixture')
    def test_reversed_order(self):
        forward=self.run_scenario('positive_real_source_pair');reverse=self.run_scenario('reversed_order')
        # The input audit retains its original order; all derived checks are symmetric.
        self.assertEqual(forward.pop('input_medications'),list(reversed(reverse.pop('input_medications'))))
        self.assertEqual(forward,reverse)
    def test_three_medication_pairs(self):
        result=self.run_scenario('three_medications_multiple_prescriptions')
        self.assertEqual(len(result['checked_medication_pairs']),3)
        self.assertEqual(len(result['matched_interactions']),2)
        self.assertEqual(sum(p['status']=='NO_RECORD_IN_LOADED_SUBSET' for p in result['checked_ingredient_pairs']),1)
    def test_multiple_prescription_contexts(self):
        result=self.run_scenario('positive_real_source_pair')
        self.assertEqual(result['checked_medication_pairs'][0]['prescription_ids'],['fixture-rx-1','fixture-rx-2'])
    def test_duplicate_separate_rule(self):
        result=self.run_scenario('duplicate_ingredient')
        self.assertEqual(len(result['duplicate_ingredients']),1)
        self.assertEqual(result['checked_ingredient_pairs'],[])
        self.assertEqual(result['matched_interactions'],[])
        self.assertFalse(result['duplicate_ingredients'][0]['dosage_totals_computed'])
    def test_duplicate_inside_combination(self):
        result=assess([fixture(self.dataset,'combo',['DDInter1','DDInter1'])],self.dataset)
        self.assertEqual(len(result['duplicate_ingredient_pairs']),1)
        self.assertTrue(result['duplicate_ingredient_pairs'][0]['context']['within_one_medication'])
    def test_combination_all_components(self):
        result=self.run_scenario('combination_fixture')
        self.assertEqual(result['completeness']['all_component_pairs_generated'],3)
        self.assertEqual(len(result['matched_interactions']),2)
        self.assertTrue(any(c['within_one_medication'] for p in result['matched_interactions'] for c in p['contexts']))
    def test_lookup_deduplicated_contexts_retained(self):
        result=assess([self.med('DDInter1','a'),self.med('DDInter1263','b'),self.med('DDInter1','c')],self.dataset)
        self.assertEqual(len(result['checked_ingredient_pairs']),1)
        self.assertEqual(len(result['checked_ingredient_pairs'][0]['contexts']),2)
        self.assertEqual(len(result['checked_medication_pairs']),3)
    def test_unknown_identifier_unassessed(self):
        result=self.run_scenario('unknown_identifier')
        self.assertEqual(result['assessment_status'],'INCOMPLETE_IDENTITIES')
        self.assertEqual(result['checked_ingredient_pairs'],[])
        self.assertEqual(result['unassessed_ingredient_pairs'][0]['status'],'UNASSESSED_IDENTITY')
    def test_missing_identifier(self):
        meds=deepcopy(self.scenarios['positive_real_source_pair']);meds[0]['ingredients'][0]['ddinter_id']=None
        self.assertTrue(assess(meds,self.dataset)['unresolved_mappings'])
    def test_rxcui_not_used_as_ddinter_id(self):
        med=self.med('DDInter14');med['ingredients'][0]['ddinter_id']='161'
        self.assertIn('MISSING_OR_INVALID_DDINTER_IDENTIFIER',assess([med],self.dataset)['unresolved_mappings'][0]['issues'])
    def test_ambiguous_candidates(self):
        result=self.run_scenario('ambiguous_identifier')
        self.assertEqual(result['unresolved_mappings'][0]['status'],'AMBIGUOUS')
        self.assertEqual(result['matched_interactions'],[])
    def test_name_identifier_conflict(self):
        result=self.run_scenario('conflicting_name_identifier')
        self.assertIn('INGREDIENT_NAME_IDENTIFIER_CONFLICT',result['unresolved_mappings'][0]['issues'])
    def test_fuzzy_names_rejected(self):
        med=self.med('DDInter1');med['ingredients'][0]['name']='Abacavirr'
        self.assertTrue(assess([med],self.dataset)['unresolved_mappings'])
    def test_explicit_paracetamol_synonym(self):
        med=self.med('DDInter14');med['ingredients'][0]['name']='Paracetamol'
        self.assertEqual(assess([med],self.dataset)['unresolved_mappings'],[])
    def test_upstream_review_gate(self):
        result=self.run_scenario('mypara_real_candidate_review_blocked')
        mypara=result['input_medications'][1] if result['input_medications'][1]['medication_id']=='mypara500' else result['input_medications'][0]
        self.assertEqual(mypara['ingredients'][0]['ddinter_id'],'DDInter14')
        self.assertEqual(mypara['brand_name'],'Mypara 500')
        self.assertEqual(mypara['identity_status'],'REVIEW_REQUIRED')
        self.assertEqual(result['checked_ingredient_pairs'],[])
        self.assertEqual(result['checked_medication_pairs'][0]['status'],'UNASSESSED')
    def test_missing_identity_evidence(self):
        med=self.med('DDInter1');med['identity_evidence']=[]
        self.assertTrue(assess([med],self.dataset)['unresolved_mappings'])
    def test_missing_prescription_context(self):
        med=self.med('DDInter1');med['prescription_ids']=[]
        self.assertTrue(assess([med],self.dataset)['unresolved_mappings'])
    def test_malformed_prescription_values_safe_failure(self):
        for malformed in [None,'rx',{},[None,{}]]:
            med=self.med('DDInter1');med['prescription_ids']=malformed
            result=assess([med,self.med('DDInter1263','second')],self.dataset)
            self.assertTrue(result['unresolved_mappings'])
            self.assertEqual(result['checked_medication_pairs'][0]['status'],'UNASSESSED')
    def test_malformed_candidates(self):
        med=self.med('DDInter1');med['ingredients'][0]['candidate_ddinter_ids']=''
        self.assertIn('INVALID_CANDIDATE_IDENTIFIERS',assess([med],self.dataset)['unresolved_mappings'][0]['issues'])
    def test_empty_ingredients_unresolved(self):
        med=self.med('DDInter1');med['ingredients']=[]
        result=assess([med,self.med('DDInter1263','other')],self.dataset)
        self.assertEqual(result['checked_medication_pairs'][0]['status'],'UNASSESSED')
    def test_duplicate_medication_ids_rejected(self):
        with self.assertRaises(ValueError):assess([self.med('DDInter1'),self.med('DDInter1263')],self.dataset)
    def test_non_array_ingredients_rejected(self):
        med=self.med('DDInter1');med['ingredients']=None
        with self.assertRaises(ValueError):assess([med],self.dataset)
    def test_absent_pair_insufficient_coverage(self):
        result=self.run_scenario('absent_pair_in_subset')
        self.assertEqual(result['checked_ingredient_pairs'][0]['coverage_conclusion'],'INSUFFICIENT_COVERAGE')
        self.assertIsNone(result['checked_ingredient_pairs'][0]['safe'])
    def test_ddinter14_identity_not_interaction_coverage(self):
        result=self.run_scenario('acetaminophen_entity_fixture_absent_pair')
        self.assertEqual(result['checked_ingredient_pairs'][0]['status'],'NO_RECORD_IN_LOADED_SUBSET')
        self.assertEqual(result['matched_interactions'],[])
    def test_partial_coverage_even_positive(self):
        result=self.run_scenario('positive_real_source_pair')
        self.assertTrue(any(a['kind']=='LIMITED_DATASET_COVERAGE' for a in result['review_alerts']))
        self.assertFalse(result['completeness']['clinical_assessment_complete'])
    def test_major_warning_immediate(self):
        result=self.run_scenario('major_real_source_pair')
        alert=next(a for a in result['review_alerts'] if a['kind']=='DDI_SOURCE_RECORD')
        self.assertEqual(alert['original_source_levels'],['Major'])
        self.assertEqual(alert['routing_priority'],'PROMPT')
        self.assertEqual(alert['display_timing'],'IMMEDIATE')
        self.assertFalse(alert['wait_for_hcp_before_display'])
    def test_all_levels_verbatim_no_delayed_warning(self):
        # Synthetic level tests are NOT new clinical source evidence.
        for label in ['Minor','Moderate','Major','Critical','Uninterpreted source label']:
            rows=[{'DDInterID_A':'DDInter1','Drug_A':'Abacavir','DDInterID_B':'DDInter1263','Drug_B':'Naltrexone','Level':label}]
            ds=BoundedDataset(rows,{'loaded_rows':1,'synthetic_fixture':True})
            result=assess([self.med('DDInter1','a'),self.med('DDInter1263','b')],ds)
            self.assertEqual(result['matched_interactions'][0]['original_level'],label)
            self.assertFalse(result['review_alerts'][0]['wait_for_hcp_before_display'])
    def test_conflicting_source_levels_not_selected(self):
        rows=[{'DDInterID_A':'DDInter1','Drug_A':'Abacavir','DDInterID_B':'DDInter1263','Drug_B':'Naltrexone','Level':level} for level in ['Moderate','Minor']]
        ds=BoundedDataset(rows,{'loaded_rows':2,'synthetic_fixture':True})
        result=assess([self.med('DDInter1','a'),self.med('DDInter1263','b')],ds)
        self.assertEqual(result['assessment_status'],'SOURCE_CONFLICT_REVIEW_REQUIRED')
        self.assertEqual(result['matched_interactions'],[])
        self.assertIsNone(result['conflicting_source_pairs'][0]['original_level'])
        self.assertEqual(result['conflicting_source_pairs'][0]['original_levels'],['Moderate','Minor'])
    def test_missing_level_rejected(self):
        row={'DDInterID_A':'DDInter1','Drug_A':'Abacavir','DDInterID_B':'DDInter1263','Drug_B':'Naltrexone','Level':''}
        with self.assertRaises(ValueError):BoundedDataset([row],{'loaded_rows':1})
    def test_conflicting_dataset_identity_rejected(self):
        rows=[{'DDInterID_A':'DDInter1','Drug_A':name,'DDInterID_B':'DDInter1263','Drug_B':'Naltrexone','Level':'Moderate'} for name in ['Abacavir','Other']]
        with self.assertRaises(ValueError):BoundedDataset(rows,{'loaded_rows':2})
    def test_scope_more_than_ten_rejected(self):
        row={'DDInterID_A':'DDInter1','Drug_A':'Abacavir','DDInterID_B':'DDInter1263','Drug_B':'Naltrexone','Level':'Moderate'}
        with self.assertRaises(ValueError):BoundedDataset([row]*11,{'loaded_rows':11})
    def test_no_clinical_fields_invented(self):
        for result in [self.run_scenario(name) for name in self.scenarios]:
            self.assertIsNone(result['no_interactions']);self.assertIsNone(result['safe_to_take'])
            self.assertIsNone(result['clinical_recommendations']);self.assertFalse(result['autonomous_prescribing'])
            self.assertFalse(result['automated_schedule_optimization'])
            for match in result['matched_interactions']:
                for row in match['source_records']:
                    self.assertIsNone(row['mechanism']);self.assertIsNone(row['management']);self.assertIsNone(row['clinical_references'])
    def test_input_unchanged(self):
        meds=deepcopy(self.scenarios['combination_fixture']);before=deepcopy(meds)
        assess(meds,self.dataset);self.assertEqual(meds,before)
    def test_pair_accounting(self):
        for name in self.scenarios:
            count=self.run_scenario(name)['completeness']
            self.assertEqual(count['all_component_pairs_generated'],count['component_pair_contexts_looked_up']+count['unassessed_component_pairs']+count['duplicate_component_pairs'])
    def test_sample_source_hash_and_counts(self):
        self.assertEqual(self.dataset.coverage['loaded_rows'],10)
        self.assertEqual(self.dataset.coverage['unique_interaction_pairs'],10)
        self.assertEqual(self.dataset.coverage['unique_pair_endpoint_ids'],12)
        self.assertEqual(self.dataset.coverage['identity_evidence_entries'],13)
        self.assertEqual(self.dataset.coverage['csv_sha256'],'a22ca451d2b755ca2331886f7e00540c86f555f9f55704a59a19c691251f52e0')
    def test_empty_input_not_safe(self):
        result=assess([],self.dataset)
        self.assertEqual(result['assessment_status'],'INSUFFICIENT_COVERAGE')
        self.assertFalse(result['completeness']['identifiers_complete']);self.assertIsNone(result['safe_to_take'])

if __name__=='__main__':unittest.main()
