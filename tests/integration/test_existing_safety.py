"""Focused offline regression tests; never contribute to E2E verdicts."""
import json
from shared.paths import ProjectPath as Path, PROJECT_ROOT
import sys
import unittest
import httpx
import base64
import tempfile
from unittest.mock import MagicMock, patch

HERE=Path(__file__).resolve().parent
PROJECT=PROJECT_ROOT

from module1_intake.ocr.vision import extract_with_gemini
from module2_medications.curated import CuratedFactReference
from module2_medications.service import from_module1
from module2_medications.terminology import load_ddinter,DirectDDInter
from module3_interactions.engine import assess


class APIError(Exception):
    def __init__(self,code):
        self.code=code
        super().__init__('secret exception body must never enter callback events')


class RetryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        # Authored 1x1 PNG; retry tests mock the API and need no prescription.
        self.image = Path(self.temp.name) / 'synthetic.png'
        self.image.write_bytes(base64.b64decode(
            'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a7x8AAAAASUVORK5CYII='))

    def response(self):
        response=MagicMock()
        response.text=json.dumps({'medications':[],'document_instructions_raw':[],
                                  'warnings':[],'requires_user_review':True})
        response.usage_metadata=None
        return response

    def test_transient_retries_are_bounded_and_backoff_events_are_safe(self):
        client=MagicMock();client.__enter__.return_value=client
        client.models.generate_content.side_effect=[APIError(503),APIError(502),self.response()]
        events=[]
        with patch('module1_intake.ocr.vision.genai.Client',return_value=client),patch('module1_intake.ocr.vision.time.sleep') as sleep:
            extraction,metadata=extract_with_gemini(self.image,'unit-test-key',max_attempts=3,
                                                   backoff_seconds=2,progress=events.append)
        self.assertEqual([x.args[0] for x in sleep.call_args_list],[2,4])
        self.assertEqual(client.models.generate_content.call_count,3)
        self.assertEqual(len(metadata['attempts']),3)
        self.assertNotIn('unit-test-key',json.dumps(events))
        self.assertNotIn('secret exception body',json.dumps(events))
        self.assertTrue(extraction.requires_user_review)

    def test_nontransient_errors_do_not_retry(self):
        for code in (401,403,404,429):
            with self.subTest(code=code):
                client=MagicMock();client.__enter__.return_value=client
                client.models.generate_content.side_effect=APIError(code)
                with patch('module1_intake.ocr.vision.genai.Client',return_value=client),patch('module1_intake.ocr.vision.time.sleep') as sleep:
                    with self.assertRaises(APIError):extract_with_gemini(self.image,'unit-test-key',max_attempts=3)
                self.assertEqual(client.models.generate_content.call_count,1)
                sleep.assert_not_called()

    def test_historical_callers_still_get_one_attempt(self):
        client=MagicMock();client.__enter__.return_value=client
        client.models.generate_content.side_effect=APIError(503)
        with patch('module1_intake.ocr.vision.genai.Client',return_value=client):
            with self.assertRaises(APIError) as error:extract_with_gemini(self.image,'unit-test-key')
        self.assertEqual(len(error.exception.module1_attempts),1)


    def test_timeout_is_transient_but_still_bounded(self):
        client=MagicMock();client.__enter__.return_value=client
        client.models.generate_content.side_effect=httpx.ReadTimeout('private transport details')
        with patch('module1_intake.ocr.vision.genai.Client',return_value=client),patch('module1_intake.ocr.vision.time.sleep') as sleep:
            with self.assertRaises(httpx.ReadTimeout) as error:
                extract_with_gemini(self.image,'unit-test-key',max_attempts=3)
        self.assertEqual(client.models.generate_content.call_count,3)
        self.assertEqual(len(error.exception.module1_attempts),3)
        self.assertEqual([x.args[0] for x in sleep.call_args_list],[2,4])


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


