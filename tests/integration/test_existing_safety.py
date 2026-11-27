"""Focused offline regression tests; never contribute to E2E verdicts."""
from shared.paths import PROJECT_ROOT
import unittest

PROJECT=PROJECT_ROOT

from module2_medications.curated import CuratedFactReference
from module2_medications.service import from_module1
from module2_medications.terminology import load_ddinter,DirectDDInter
from module3_interactions.engine import assess


class ReferenceSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reference=CuratedFactReference(PROJECT_ROOT/'data/reference/provenance/real_medication_e2e/runs/integration_fix_20261013_001/curated_product_facts.json')
        cls.dataset=load_ddinter(PROJECT,'official-all')
        cls.terminology=DirectDDInter(cls.dataset)

    def test_product_identity_retains_source_and_clinical_review_scope(self):
        result=self.reference.lookup({'name_raw':'Clopidogrel 75 mg','strength_raw':'75mg'})
        self.assertEqual(result['identification_status'],'VERIFIED')
        self.assertFalse(result['clinical_verified'])
        candidate=result['candidates'][0]
        self.assertEqual(candidate['product_review_state'],'SOURCE_SUPPORTED')
        self.assertEqual(candidate['product']['original_observation_review_state'],'REVIEW_REQUIRED')
        self.assertFalse(candidate['synthetic_fixture'])

    def test_wrong_strength_or_misspelled_brand_never_supplies_ingredients(self):
        for medication in ({'name_raw':'Clopidogrel 75 mg','strength_raw':'100mg'},
                           {'name_raw':'ClopidogrelX 75 mg','strength_raw':'75mg'}):
            result=self.reference.lookup(medication)
            self.assertEqual(result['identification_status'],'UNRESOLVED')
            self.assertEqual(result['candidates'],[])

    def test_confirmation_and_unresolved_salt_keep_pair_unassessed(self):
        medications={'medications':[{'name_raw':'A.T Warfarin 1 mg','strength_raw':'1mg','uncertain_fields':[]},
                                   {'name_raw':'Aspirin DWP 100mg','strength_raw':'100mg','uncertain_fields':[]}]}
        unconfirmed=from_module1(medications,self.reference,self.terminology,confirmed=False)
        self.assertFalse(any(m['ready_for_identifier_handoff'] for m in unconfirmed))
        confirmed=from_module1(medications,self.reference,self.terminology,confirmed=True)
        self.assertEqual(confirmed[0]['ingredients'][0]['mapping_status'],'UNRESOLVED')
        assessment=assess([m['module3_input'] for m in confirmed],self.dataset)
        self.assertEqual(assessment['matched_interactions'],[])
        self.assertIsNone(assessment['safe_to_take'])
        self.assertTrue(assessment['requires_hcp_review'])


if __name__=='__main__':unittest.main(verbosity=2)


