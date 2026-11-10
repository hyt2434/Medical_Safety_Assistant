import json
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from module1_intake.ocr.models.extraction import Extraction
from module1_intake.ocr.rechecks.receipts import parse_candidate, retry_receipt


class ReceiptRetryTests(unittest.TestCase):
    def test_cells_and_metadata(self):
        result = parse_candidate('Product Chai 1 40.232 40.232\nSố lô:010622 HSD:17/06/2025')
        self.assertEqual(result['quantity_raw'], '1')
        self.assertEqual(result['expiry_date_raw'], '17/06/2025')
        self.assertEqual(result['lot_number_raw'], '010622')
        self.assertIsNone(parse_candidate('Product 100ml 40.232')['quantity_raw'])
        self.assertIsNone(parse_candidate('Số 16:10211926')['lot_number_raw'])

    def test_candidates_do_not_replace_original_and_conflicts_are_reported(self):
        extraction = Extraction(document_type='PHARMACY_RECEIPT', receipt_items=[{
            'unit_price_raw': '31.565', 'amount_raw': '315.650',
            'item_region': {'left': 0, 'top': 0, 'width': 100, 'height': 100}, 'item_rechecks': []}])
        def recognize(command, **kwargs):
            Path(command[3]).write_text(json.dumps({'text': 'Product Viên 10 31.563 315.630'}), encoding='utf-8')
            return subprocess.CompletedProcess(command, 0)
        with tempfile.TemporaryDirectory() as directory, patch('module1_intake.ocr.rechecks.receipts.subprocess.run', side_effect=recognize):
            retry_receipt(Path('image'), Path('script'), Path(directory), extraction, time.monotonic()+30)
        item = extraction.receipt_items[0]
        self.assertEqual(item['unit_price_raw'], '31.565')
        self.assertEqual(item['item_rechecks'][0]['candidate_fields']['quantity_raw'], '10')
        self.assertTrue(any(d['kind'] == 'conflict' for d in item['item_rechecks'][0]['differences']))

    def test_failure_does_not_remove_original(self):
        extraction = Extraction(receipt_items=[{'product_raw': 'Product', 'item_region': {'left': 0}, 'item_rechecks': []}])
        with tempfile.TemporaryDirectory() as directory, patch('module1_intake.ocr.rechecks.receipts.subprocess.run', side_effect=subprocess.TimeoutExpired('node', 20)):
            retry_receipt(Path('image'), Path('script'), Path(directory), extraction, time.monotonic()+30)
        self.assertEqual(extraction.receipt_items[0]['product_raw'], 'Product')
        self.assertEqual(extraction.receipt_items[0]['item_rechecks'][0]['error_code'], 'REGION_OCR_TIMEOUT')
