import re
import unittest
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from module1_intake.ocr.models.api import MedicationIntake, ExtractionRun, MedicationEntry
from module1_intake.ocr.models.extraction import Extraction
from module1_intake.ocr.application.mapping import build_response


class ErdContractTest(unittest.TestCase):
    def test_transport_projects_literal_fields_into_core_v4_without_identity(self):
        from module1_intake.ocr.application.intake import core_medications
        from shared.db.intake_adapter import medication_fields
        extraction = Extraction.model_validate({'medications': [{'name_raw': 'Example',
            'strength_raw': '250 mg/5 mL', 'dose_raw': '1 mL', 'package_size_raw': '120ml',
            'evidence_text': 'Example 250 mg/5 mL, 1 mL',
            'administrations': [{'timing_raw': 'sáng', 'dose_raw': '1 mL'}]}]})
        response = build_response({'text': 'original OCR', 'words': []}, extraction, uuid4(),
                                  datetime.now(timezone.utc), datetime.now(timezone.utc))
        medication, = core_medications(response)
        fields = medication_fields(medication.model_dump())
        self.assertEqual(fields['schema'], 'medication-entry.v4')
        self.assertEqual(fields['strength_raw'], '250 mg/5 mL')
        self.assertEqual(fields['administrations'][0]['timing_raw'], 'sáng')
        self.assertNotIn('patient_user_id', fields)
        self.assertNotIn('product_id', fields)
        self.assertIsNone(response.medication_entries[0].confirmed_at)
        self.assertEqual(response.extraction_run.raw_output['parsed']['medications'][0]['package_size_raw'], '120ml')

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
