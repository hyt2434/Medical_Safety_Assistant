import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4
from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
from pydantic import ValidationError

from api.routes.ocr import router
from module1_intake.ocr.imaging.regions import ImageRegion, crop_region
from module1_intake.ocr.imaging.input import prepare_image
from module1_intake.ocr.application.mapping import build_response
from module1_intake.ocr.models.extraction import Extraction
from module1_intake.ocr.application.service import LocalOcrService


class RegionTests(unittest.TestCase):
    def test_rejects_empty_reversed_outside_and_nonfinite_regions(self):
        for override in ({'right': 0}, {'left': .8, 'right': .2}, {'bottom': 2},
                         {'top': -1}, {'left': float('nan')}, {'right': float('inf')},
                         {'extra': 1}):
            with self.subTest(override=override), self.assertRaises(ValidationError):
                ImageRegion.model_validate({'left': 0, 'top': 0, 'right': 1, 'bottom': 1, **override})

    def test_crop_preserves_pixels_and_reports_offset_without_changing_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, target = Path(tmp)/'source.png', Path(tmp)/'crop.png'
            original = Image.new('RGB', (200, 100), 'white')
            original.paste('red', (100, 25, 200, 100))
            original.save(source)
            before = source.read_bytes()
            metadata = crop_region(source, target, ImageRegion(left=.5, top=.25, right=1, bottom=1))
            with Image.open(target) as result:
                self.assertEqual(result.size, (100, 75))
                self.assertEqual(result.getpixel((0, 0)), (255, 0, 0))
            self.assertEqual(source.read_bytes(), before)
            self.assertEqual(metadata['region_to_full_normalized'], [[1, 0, 100], [0, 1, 25], [0, 0, 1]])

    def test_region_uses_exif_oriented_dimensions(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, normalized, target = [Path(tmp)/n for n in ('source.jpg', 'normalized.png', 'crop.png')]
            im = Image.new('RGB', (200, 100), 'white')
            exif = im.getexif(); exif[274] = 6
            im.save(source, exif=exif)
            prepare_image(source, normalized)
            result = crop_region(normalized, target, ImageRegion(left=0, top=.5, right=1, bottom=1))
            self.assertEqual(result['full_normalized_size'], [100, 200])
            self.assertEqual(result['ocr_size'], [100, 100])

    def test_rejects_tiny_crop(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp)/'in.png'; Image.new('RGB', (100, 100)).save(source)
            with self.assertRaises(ValueError):
                crop_region(source, Path(tmp)/'out.png', ImageRegion(left=0, top=0, right=.1, bottom=1))


class RegionApiTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(router)
        route = next(r for r in router.routes if r.path == '/api/v1/ocr/extractions')
        app.dependency_overrides[route.dependant.dependencies[0].call] = lambda: {}
        self.client = TestClient(app)
        output = io.BytesIO(); Image.new('RGB', (100, 100), 'white').save(output, format='PNG')
        self.image = output.getvalue()

    def post(self, region=None):
        return self.client.post('/api/v1/ocr/extractions', files={'file': ('image.png', self.image, 'image/png')},
                                data={} if region is None else {'region': region})

    def test_invalid_json_does_not_start_ocr(self):
        with patch('api.routes.ocr.service.extract') as extract:
            for region in ('not json', '{}', '{"left":0,"top":0,"right":2,"bottom":1}'):
                self.assertEqual(self.post(region).status_code, 422)
            extract.assert_not_called()

    def test_optional_region_keeps_old_api_and_unconfirmed_contract(self):
        now = datetime.now(timezone.utc)
        response = build_response({'text': 'Example'}, Extraction(medications=[{'name_raw': 'Example'}]), uuid4(), now, now)
        with patch('api.routes.ocr.service.extract', return_value=response) as extract:
            self.assertEqual(self.post().status_code, 200)
            self.assertEqual(extract.call_args.kwargs, {})
            result = self.post(json.dumps({'left': .5, 'top': 0, 'right': 1, 'bottom': 1}))
            self.assertEqual(result.status_code, 200)
            self.assertEqual(extract.call_args.kwargs['region'].left, .5)
            self.assertEqual(result.json()['medication_entries'][0]['confirmation_status'], 'PENDING')


class DiagnosticTests(unittest.TestCase):
    def test_preprocessed_text_survives_when_both_layout_parsers_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root/'input.png'; Image.new('RGB', (200, 100), 'white').save(source)
            service = LocalOcrService()
            service.script = root/'node'/'local_ocr.cjs'
            (service.script.parent/'ocr/node_modules/tesseract.js').mkdir(parents=True)
            service.artifact_root = root/'runs'
            def recognize(args, **_kwargs):
                raw = {'text': 'Example 10mg' if Path(args[3]).name == 'cv-evidence.json' else '',
                       'words': [], 'confidence': 50, 'provider': 'test'}
                Path(args[3]).write_text(json.dumps(raw), encoding='utf-8')
                return SimpleNamespace(returncode=0)
            with patch('module1_intake.ocr.application.service.shutil.which', return_value='node'), \
                 patch('module1_intake.ocr.application.service.subprocess.run', side_effect=recognize), \
                 patch('module1_intake.ocr.application.service.extract_printed_prescription', side_effect=ValueError('unsupported')):
                result = service.extract(source)
            raw = result.extraction_run.raw_output
            self.assertEqual(result.medication_entries, [])
            self.assertTrue(raw['ocr']['diagnostics']['text_detected'])
            self.assertFalse(raw['ocr']['diagnostics']['structure_recognized'])
            self.assertEqual(raw['parsed']['review_guidance']['reason'], 'STRUCTURE_NOT_RECOGNIZED')
            self.assertEqual(raw['ocr']['preprocessing']['ocr_variants'][1]['text'], 'Example 10mg')
            self.assertTrue((service.artifact_root/str(result.extraction_run.extraction_run_id)/'result.json').exists())
