"""Focused adapter/boundary regressions using retained actual OCR evidence."""
import importlib.util
from shared.paths import ProjectPath as Path, PROJECT_ROOT
import sys
import unittest

HERE=Path(__file__).resolve().parent
ROOT = PROJECT_ROOT

from module1_intake.ocr.local_ocr_rows import extract_printed_rows
spec=importlib.util.spec_from_file_location('unified_runner',HERE/'run.py')
runner=importlib.util.module_from_spec(spec); spec.loader.exec_module(runner)


class IntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.truth={c['id']:c for c in runner.read(HERE/'ground_truth.json')['cases']}
        cls.artifacts=PROJECT_ROOT/'data/reference/provenance/unified_medication_e2e/runs/full_20261015_001'

    def test_extra_strength_product_does_not_hide_column_header(self):
        raw=runner.read(self.artifacts/'U21_ocr_evidence.json')
        extraction=extract_printed_rows(raw)
        self.assertIsNotNone(extraction)
        self.assertEqual(extraction['medications'][1]['name_raw'],'TYLENOL Extra Strength')
        self.assertTrue(all(c['pass'] for c in runner.extraction_checks(self.truth['U21'],extraction)))

    def test_missing_strength_is_preserved_and_not_invented(self):
        raw=runner.read(self.artifacts/'U26_ocr_evidence.json')
        extraction=extract_printed_rows(raw)
        self.assertIsNone(extraction['medications'][0]['strength_raw'])
        self.assertIn('strength_raw',extraction['medications'][0]['uncertain_fields'])
        self.assertTrue(all(c['pass'] for c in runner.extraction_checks(self.truth['U26'],extraction)))

    def test_real_ocr_strength_error_cannot_be_confirmed(self):
        extraction=runner.read(self.artifacts/'U18_module1.json')['actual_output']
        checks=runner.extraction_checks(self.truth['U18'],extraction)
        self.assertTrue(any(c['check']=='strength_raw' and not c['pass'] for c in checks))

    def test_low_confidence_correct_text_keeps_review_gate(self):
        extraction=runner.read(self.artifacts/'U02_module1.json')['actual_output']
        checks=runner.extraction_checks(self.truth['U02'],extraction)
        self.assertTrue(all(c['pass'] for c in checks if c['check']!='uncertainty'))
        self.assertFalse(all(c['pass'] for c in checks))
        self.assertIn('ocr_low_confidence',extraction['medications'][0]['uncertain_fields'])

    def test_original_layout_uses_unchanged_legacy_adapter(self):
        self.assertIsNone(extract_printed_rows(runner.read(self.artifacts/'TC01_ocr_evidence.json')))


if __name__=='__main__': unittest.main(verbosity=2)
