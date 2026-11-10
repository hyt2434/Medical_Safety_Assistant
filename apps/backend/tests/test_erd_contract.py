import re
import unittest
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from module1_intake.ocr.models.api import MedicationIntake, ExtractionRun, MedicationEntry
from module1_intake.ocr.models.extraction import Extraction
from module1_intake.ocr.application.mapping import build_response


class ErdContractTest(unittest.TestCase):
    def test_fields_match_design(self):
        root = Path(__file__).resolve().parents[3]
        design = (root / 'docs/design/database/simplified-35-tables/Unified-SQL-ERD.md').read_text(encoding='utf-8')
        for model, table in [(MedicationIntake, 'MEDICATION_INTAKES'),
                             (ExtractionRun, 'EXTRACTION_RUNS'),
                             (MedicationEntry, 'MEDICATION_ENTRIES')]:
            block = re.search(r'\b' + table + r'\s*\{([^}]+)\}', design).group(1)
            fields = {line.split()[1] for line in block.splitlines() if line.strip()}
            self.assertEqual(set(model.model_fields), fields)

    def test_mapping_preserves_evidence_without_confirming(self):
        extraction = Extraction.model_validate({'medications': [
            {'name_raw': 'Example', 'strength_raw': '10mg', 'package_size_raw': '120ml',
             'instructions_raw': 'Uống khi cần', 'evidence_text': 'Example 10mg'},
            {'name_raw': 'Unclear (label', 'product_raw': 'Unclear (label',
             'uncertain_fields': ['product_structure']}]})
        raw = {'text': 'complete OCR text', 'words': [], 'confidence': 77}
        run_id = uuid4()
        now = datetime.now(timezone.utc)
        result = build_response(raw, extraction, run_id, now, now)
        self.assertEqual(result.extraction_run.raw_output['ocr'], raw)
        self.assertEqual(result.extraction_run.raw_output['parsed']['medications'][0]['package_size_raw'], '120ml')
        first, second = result.medication_entries
        self.assertEqual(first.extracted_name, 'Example')
        self.assertEqual(first.dosage_instructions, 'Uống khi cần')
        self.assertEqual(first.extraction_run_id, run_id)
        self.assertEqual([first.ordinal, second.ordinal], [1, 2])
        self.assertIsNone(first.confirmed_data)
        self.assertIsNone(first.patient_user_id)
        self.assertEqual(first.confirmation_status, 'PENDING')
        self.assertIsNone(second.extracted_name)
        self.assertEqual(second.raw_text, 'Unclear (label')
