import tempfile
import unittest
from pathlib import Path
from PIL import Image
from module1_intake.ocr.imaging.preprocessing import preprocess_document
from module1_intake.ocr.application.selection import extraction_quality, cv_selection_blockers
from module1_intake.ocr.models.extraction import Extraction, Medication


class PreprocessingTests(unittest.TestCase):
    def test_gain_cannot_replace_missing_schedule_or_route(self):
        old = Extraction.model_validate({'medications': [{'name_raw': 'A', 'route_raw': 'Xịt',
            'administrations': [{'timing_raw': 'Sáng', 'dose_raw': '1'}]}]})
        new = Extraction(medications=[Medication(name_raw='A', strength_raw='10mg')])
        reasons = cv_selection_blockers(old, new)
        self.assertIn('medication_1:route_raw_changed_or_missing', reasons)
        self.assertIn('medication_1:schedule_changed_or_missing', reasons)

    def test_name_change_blocked_and_addition_allowed(self):
        old = Extraction(medications=[Medication(name_raw='A')])
        new = Extraction(medications=[Medication(name_raw='¡ A', strength_raw='10mg')])
        self.assertTrue(cv_selection_blockers(old, new))
        new.medications[0].name_raw = 'A'
        self.assertEqual(cv_selection_blockers(old, new), [])

    def test_changed_dose_blocked(self):
        old = Extraction.model_validate({'medications': [{'administrations': [{'timing_raw': 'Chiêu', 'dose_raw': '1'}]}]})
        new = old.model_copy(deep=True)
        new.medications[0].administrations[0].dose_raw = '2'
        self.assertTrue(cv_selection_blockers(old, new))
    def test_preserves_frame_and_maps_coordinates(self):
        with tempfile.TemporaryDirectory() as folder:
            source, target = Path(folder)/'in.png', Path(folder)/'out.png'
            Image.new('RGB', (600, 800), 'white').save(source)
            result = preprocess_document(source, target)
            with Image.open(target) as output:
                self.assertEqual(output.size, (1200, 1600))
                self.assertEqual(output.mode, 'L')
            self.assertEqual(result['source_to_output'], [[2, 0, 0], [0, 2, 0], [0, 0, 1]])
            self.assertEqual(result['page_crop'], 'disabled_to_preserve_content')

    def test_large_image_not_upscaled(self):
        with tempfile.TemporaryDirectory() as folder:
            source, target = Path(folder)/'in.png', Path(folder)/'out.png'
            Image.new('RGB', (2000, 2000), 'white').save(source)
            result = preprocess_document(source, target)
            self.assertEqual(result['output_size'], [2000, 2000])

    def test_quality_is_structural_not_confidence(self):
        missing = Extraction(medications=[Medication(name_raw='A')])
        complete = Extraction(medications=[Medication(name_raw='A', strength_raw='10mg')])
        self.assertGreater(extraction_quality(complete), extraction_quality(missing))
