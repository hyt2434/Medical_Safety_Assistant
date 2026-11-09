import json
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from module1_intake.ocr.parser_models import Administration, Extraction, Medication
from module1_intake.ocr.region_retry import compare_schedules, retry_schedules


class RegionRetryTests(unittest.TestCase):
    def test_conflict_and_missing_are_distinct(self):
        original = [Administration(timing_raw='Sáng', dose_raw='1')]
        self.assertEqual(compare_schedules(original, [{'timing_raw': 'Sáng', 'dose_raw': '2'}])[0]['kind'], 'conflict')
        self.assertEqual(compare_schedules(original, [])[0]['kind'], 'needs_review')
        self.assertEqual(compare_schedules(original, [{'timing_raw': 'Sáng', 'dose_raw': '1'}]), [])

    def test_retry_preserves_original_and_skips_readable_schedule(self):
        region = {'left': 1, 'top': 2, 'width': 100, 'height': 20}
        extraction = Extraction(medications=[Medication(schedule_region=region),
            Medication(schedule_region=region, administrations=[Administration(timing_raw='Sáng', dose_raw='1')])])
        def recognize(command, **kwargs):
            Path(command[3]).write_text(json.dumps({'text': 'Sáng: 1 Chiều: 1'}), encoding='utf-8')
            return subprocess.CompletedProcess(command, 0)
        with tempfile.TemporaryDirectory() as directory, patch('module1_intake.ocr.region_retry.subprocess.run', side_effect=recognize) as run:
            retry_schedules(Path('image.jpg'), Path('ocr.cjs'), Path(directory), extraction, time.monotonic() + 30)
        self.assertEqual(run.call_count, 2)
        self.assertEqual(extraction.medications[0].administrations, [])
        self.assertEqual(len(extraction.medications[0].schedule_rechecks[0]['administrations']), 2)
        self.assertEqual(extraction.medications[1].schedule_rechecks, [])

    def test_timeout_is_optional_failure(self):
        extraction = Extraction(medications=[Medication(schedule_region={'left': 1, 'top': 2, 'width': 100, 'height': 20})])
        with tempfile.TemporaryDirectory() as directory, patch('module1_intake.ocr.region_retry.subprocess.run', side_effect=subprocess.TimeoutExpired('node', 20)):
            retry_schedules(Path('image.jpg'), Path('ocr.cjs'), Path(directory), extraction, time.monotonic() + 30)
        self.assertEqual(extraction.medications[0].schedule_rechecks[0]['error_code'], 'REGION_OCR_TIMEOUT')
        self.assertIn('schedule_recheck_failed', extraction.medications[0].uncertain_fields)
