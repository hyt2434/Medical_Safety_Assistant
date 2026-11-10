import json
import unittest
from pathlib import Path
from module1_intake.ocr.parsing.receipt import extract_receipt
from module1_intake.ocr.models.extraction import Extraction
from module1_intake.ocr.parsing.dispatcher import extract_printed_prescription


class ReceiptTests(unittest.TestCase):
    def test_non_receipt_not_claimed(self):
        self.assertIsNone(extract_receipt([]))

    def test_local_receipt_preserves_missing_cells_and_groups(self):
        path = Path('data/local/module1/test-output/receipt-evidence.json')
        if not path.exists():
            self.skipTest('Local receipt evidence unavailable')
        result = Extraction.model_validate(extract_printed_prescription(json.loads(path.read_text(encoding='utf-8'))))
        self.assertEqual(result.document_type, 'PHARMACY_RECEIPT')
        self.assertEqual(len(result.receipt_items), 3)
        self.assertEqual(len(result.medications), 2)
        self.assertEqual(result.receipt_items[1]['package_size_raw'], '100ml')
        self.assertIsNone(result.receipt_items[1]['quantity_raw'])
        self.assertEqual(result.receipt_items[1]['lot_number_raw'], '010622')
        self.assertEqual(result.receipt_total_raw, '494.482')
        for medication in result.medications:
            self.assertEqual(medication.administrations, [])
            self.assertIsNone(medication.dose_raw)
            self.assertIsNone(medication.duration_raw)
            self.assertIsNone(medication.strength_raw)
            self.assertFalse(medication.schedule_requires_review)
