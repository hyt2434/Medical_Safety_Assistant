"""Patient-free regressions for the integrated boundaries; no clinical evidence.

All product rows, OCR coordinates, reviews and interaction rows here are invented
engineering fixtures. No downloaded dataset or API is consulted.
"""
from copy import deepcopy
import importlib
import json
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import patch

from module1_intake.ocr.local_ocr_rows import extract_printed_rows
from module2_medications.fixtures import fixture_db
from module2_medications.reference import MedicationReference, review_product
from module2_medications.service import assess_prescriptions
from module2_medications.terminology import DirectDDInter
from module2_medications.unified import normalize_product, strength_signature, validate_product
from module3_interactions.engine import BoundedDataset
from shared.paths import PROJECT_ROOT, resolve_path


class OCRRowsTests(unittest.TestCase):
    def raw(self):
        def word(text, x, y, confidence=99):
            return {'text': text, 'confidence': confidence,
                    'bbox': {'x0': x, 'x1': x+35, 'y0': y, 'y1': y+15}}
        return {'words': [word('Strength', 500, 10), word('1.', 10, 100),
                          word('Fixture', 70, 100), word('500mg', 500, 100),
                          word('Form:', 70, 150), word('tablet', 150, 150)]}

    def test_literal_fields_and_review_gate(self):
        result = extract_printed_rows(self.raw())
        med = result['medications'][0]
        self.assertEqual((med['name_raw'], med['strength_raw'], med['dosage_form_raw']),
                         ('Fixture', '500mg', 'tablet'))
        self.assertIsNone(med['dose_raw'])
        self.assertTrue(result['requires_user_review'])

    def test_missing_strength_never_invented(self):
        raw = self.raw()
        raw['words'] = [w for w in raw['words'] if w['text'] != '500mg']
        med = extract_printed_rows(raw)['medications'][0]
        self.assertIsNone(med['strength_raw'])
        self.assertIn('strength_raw', med['uncertain_fields'])

    def test_low_confidence_requires_review(self):
        raw = self.raw()
        raw['words'][2]['confidence'] = 40
        self.assertIn('ocr_low_confidence', extract_printed_rows(raw)['medications'][0]['uncertain_fields'])

    def test_unrecognized_layout_defers_to_legacy(self):
        self.assertIsNone(extract_printed_rows({'words': []}))


class SyntheticPipelineTests(unittest.TestCase):
    def setUp(self):
        self.network = patch.object(socket, 'socket', side_effect=AssertionError('Network forbidden'))
        self.network.start()
        self.addCleanup(self.network.stop)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        db, _, _ = fixture_db(self.temp.name)
        self.db = db
        self.reference = MedicationReference(db, allow_synthetic=True)
        self.addCleanup(self.reference.close)
        # Explicitly synthetic interaction level, never a real clinical assertion.
        row = {'DDInterID_A': 'DDInter582', 'Drug_A': 'Dolutegravir',
               'DDInterID_B': 'DDInter24', 'Drug_B': 'Aluminum hydroxide', 'Level': 'Major'}
        self.dataset = BoundedDataset([row], {'loaded_rows': 1, 'synthetic_fixture': True,
            'scope': 'invented integration fixture', 'source_url': 'synthetic://integration'})
        self.mapper = DirectDDInter(self.dataset)

    def sample(self, reviewed=True):
        value = json.loads((PROJECT_ROOT/'data/samples/synthetic_pipeline.json').read_text())
        if reviewed:
            for prescription in value['prescriptions']:
                for med in prescription['medications']:
                    candidate = self.reference.lookup(med)['candidates'][0]['candidate_key']
                    review_product(self.db, candidate, status='VERIFIED', reviewer='Synthetic test adjudication',
                                   evidence=[{'locator': 'synthetic://test-only', 'sha256': '0'*64}])
        return value

    def assess(self, value):
        return assess_prescriptions(value, self.reference, self.mapper)

    def test_reviewed_synthetic_handoff_and_immediate_warning(self):
        value = self.sample()
        before = deepcopy(value)
        result = self.assess(value)
        self.assertEqual(value, before)
        self.assertTrue(all(m['ready_for_identifier_handoff'] for m in result['module2']))
        assessment = result['module3']
        self.assertEqual(assessment['matched_interactions'][0]['original_level'], 'Major')
        self.assertEqual(assessment['checked_medication_pairs'][0]['prescription_ids'],
                         ['synthetic-rx-1', 'synthetic-rx-2'])
        self.assertTrue(any(a['routing_priority'] == 'PROMPT' and a['display_timing'] == 'IMMEDIATE'
                            for a in assessment['review_alerts']))
        self.assertIsNone(assessment['safe_to_take'])
        self.assertTrue(assessment['requires_hcp_review'])

    def test_unreviewed_products_never_reach_pair_lookup(self):
        result = self.assess(self.sample(reviewed=False))
        self.assertFalse(any(m['ready_for_identifier_handoff'] for m in result['module2']))
        self.assertEqual(result['module3']['matched_interactions'], [])

    def test_uncertain_transcription_blocks_reviewed_identity(self):
        value = self.sample()
        value['prescriptions'][0]['medications'][0]['uncertain_fields'] = ['name_raw']
        result = self.assess(value)
        self.assertFalse(result['module2'][0]['ready_for_identifier_handoff'])
        self.assertEqual(result['module3']['matched_interactions'], [])
        self.assertIsNone(result['module3']['safe_to_take'])

    def test_real_input_cannot_use_synthetic_reference(self):
        result = self.reference.lookup({'brand_name': 'Fixture Dolutegravir'})
        self.assertEqual(result['candidates'], [])


class UnifiedBoundaryTests(unittest.TestCase):
    def test_strength_units_preserve_concentration(self):
        self.assertEqual(strength_signature('0.5 g'), strength_signature('500 mg'))
        self.assertNotEqual(strength_signature('10 mg/mL'), strength_signature('10 mg'))

    def test_missing_identity_fields_block_product(self):
        product = {'source_product_code': 'SYNTHETIC:1', 'ingredients': 'Invented 10mg'}
        _, parsed = normalize_product(product)
        self.assertTrue(validate_product(product, parsed)['block_product_identity'])

    def test_literal_salts_have_distinct_product_keys(self):
        product = {'brand_name': 'Invented', 'ingredients': 'Metformin 500mg',
                   'source_product_code': 'SYNTHETIC:1', 'dosage_form': 'tablet'}
        other = {**product, 'ingredients': 'Metformin hydrochloride 500mg'}
        self.assertNotEqual(normalize_product(product)[0]['product_key'], normalize_product(other)[0]['product_key'])


class ImportIsolationTests(unittest.TestCase):
    def test_runtime_modules_resolve_to_team_source(self):
        for name in ('module1_intake.ocr.local', 'module2_medications.reference',
                     'module2_medications.unified', 'module3_interactions.engine',
                     'module3_interactions.official_ddinter.dataset', 'shared.dav_import.pipeline'):
            module = importlib.import_module(name)
            self.assertTrue(Path(module.__file__).resolve().is_relative_to(PROJECT_ROOT/'src'), name)

    def test_historical_data_paths_stay_in_team(self):
        path = resolve_path('Medication-Safety-Assistant/data/reference/example.json')
        self.assertEqual(path, PROJECT_ROOT/'data/reference/example.json')
        self.assertTrue(path.is_relative_to(PROJECT_ROOT))
