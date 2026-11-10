import json
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from module1_intake.ocr.models.extraction import Administration, Extraction, Medication
from module1_intake.ocr.rechecks.products import retry_products


class ProductRetryTests(unittest.TestCase):
    def test_normalization_preserves_literal_and_does_not_guess(self):
        result = Administration(timing_raw='Chiêu', dose_raw='1')
        self.assertEqual(result.timing_normalized, 'afternoon')
        self.assertEqual(result.timing_raw, 'Chiêu')
        self.assertIsNone(Administration(timing_raw='khi đau').timing_normalized)

    def test_candidates_preserve_original_and_coordinate_metadata(self):
        extraction = Extraction(medications=[Medication(name_raw='Brand [CODE]',
            product_region={'left': 2, 'top': 3, 'width': 40, 'height': 20},
            uncertain_fields=['strength_structure'])])
        def recognize(command, **kwargs):
            Path(command[3]).write_text(json.dumps({'text': '1. Brand [CODE] 500mg + 20mg (Alpha)'}), encoding='utf-8')
            return subprocess.CompletedProcess(command, 0)
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            source = folder / 'input.png'
            Image.new('RGB', (100, 100), 'white').save(source)
            with patch('module1_intake.ocr.rechecks.products.subprocess.run', side_effect=recognize):
                retry_products(source, Path('ocr.cjs'), folder, extraction, time.monotonic()+30)
        medication = extraction.medications[0]
        self.assertIsNone(medication.strength_raw)
        self.assertEqual(len(medication.product_rechecks), 3)
        candidate = medication.product_rechecks[1]
        self.assertEqual(candidate['candidate_fields']['name_raw'], 'Brand [CODE]')
        self.assertEqual(candidate['candidate_fields']['strength_raw'], '500mg + 20mg')
        self.assertEqual(candidate['preprocessing']['scale'], 2)
        self.assertEqual(len(medication.product_review_candidates), 1)
        self.assertEqual(medication.product_review_candidates[0]['recheck_indices'], [0, 1, 2])
        self.assertEqual(medication.product_review_candidates[0]['confirmation_status'], 'PENDING')

    def test_timeout_retains_original(self):
        extraction = Extraction(medications=[Medication(name_raw='Brand',
            product_region={'left': 0, 'top': 0, 'width': 10, 'height': 10},
            uncertain_fields=['strength_structure'])])
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            source = folder / 'input.png'
            Image.new('RGB', (20, 20)).save(source)
            with patch('module1_intake.ocr.rechecks.products.subprocess.run', side_effect=subprocess.TimeoutExpired('node', 20)):
                retry_products(source, Path('ocr.cjs'), folder, extraction, time.monotonic()+30)
        self.assertEqual(extraction.medications[0].name_raw, 'Brand')
        self.assertEqual(extraction.medications[0].product_rechecks[0]['error_code'], 'PRODUCT_OCR_TIMEOUT')
