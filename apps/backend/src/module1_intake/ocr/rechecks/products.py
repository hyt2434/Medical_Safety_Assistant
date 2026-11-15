"""Compare product crops without promoting candidates to confirmed values."""
import json
import re
import subprocess
import time
from PIL import Image, ImageOps
from module1_intake.ocr.parsing.products import parse_numbered_product as product_fields
from module1_intake.ocr.parsing.products import parse_strength_product
from module1_intake.ocr.parsing.products import parse_quantity_product


def retry_products(image, script, directory, extraction, deadline):
    attempts = 0
    for index, medication in enumerate(extraction.medications):
        region = medication.product_region
        if not {'strength_structure', 'product_structure'}.intersection(medication.uncertain_fields) or not region:
            continue
        for variant in ('original', 'upscale_2x', 'upscale_2x_autocontrast'):
            if attempts >= 18 or time.monotonic() >= deadline:
                extraction.warnings.append('Product OCR retry budget exhausted; original evidence retained.')
                return
            attempts += 1
            metadata = {'variant': variant, 'source_region': region, 'psm': 6,
                        'coordinate_space': 'product_crop', 'scale': 1 if variant == 'original' else 2}
            try:
                with Image.open(image) as source:
                    x, y = region['left'], region['top']
                    if region['width'] <= 0 or region['height'] <= 0 or x + region['width'] > source.width or y + region['height'] > source.height:
                        raise ValueError('Invalid product region')
                    crop = source.crop((x, y, x + region['width'], y + region['height']))
                    if variant != 'original':
                        crop = crop.resize((crop.width * 2, crop.height * 2), Image.Resampling.LANCZOS)
                    if variant == 'upscale_2x_autocontrast':
                        crop = ImageOps.autocontrast(ImageOps.grayscale(crop))
                    crop_path = directory / f'product-{index}-{variant}.png'
                    crop.save(crop_path)
                config = directory / f'product-{index}-options.json'
                config.write_text(json.dumps({'psm': 6}), encoding='utf-8')
                output = directory / f'product-{index}-{variant}.json'
                process = subprocess.run(['node', str(script), str(crop_path), str(output), str(config)],
                    capture_output=True, text=True, encoding='utf-8',
                    timeout=max(.01, min(20, deadline-time.monotonic())), check=False)
                if process.returncode:
                    raise ValueError('Product OCR failed')
                raw = json.loads(output.read_text(encoding='utf-8'))
                product_text = re.sub(rf'^\s*{index + 1}[.)/]\s*', '', raw['text'])
                parse_product = {'strength_table': parse_strength_product,
                                 'quantity_table': parse_quantity_product}.get(medication.product_parser, product_fields)
                candidate, flags = parse_product(product_text)
                differences = []
                for key, value in candidate.items():
                    original = getattr(medication, key)
                    if original != value:
                        kind = 'additional_information' if original is None else 'less_information' if value is None else 'conflict'
                        differences.append({'field': key, 'original_value': original, 'candidate_value': value, 'kind': kind})
                medication.product_rechecks.append({'status': 'COMPLETED', 'preprocessing': metadata,
                    'ocr': raw, 'candidate_fields': candidate, 'uncertain_fields': flags,
                    'differences': differences, 'requires_user_review': True})
                if 'product_structure' not in flags or candidate.get('components_raw'):
                    # Group identical alternatives for display, never as a vote for truth.
                    existing = next((item for item in medication.product_review_candidates
                                     if item['candidate_fields'] == candidate), None)
                    reference = len(medication.product_rechecks) - 1
                    if existing:
                        existing['recheck_indices'].append(reference)
                    else:
                        medication.product_review_candidates.append({
                            'candidate_fields': candidate, 'uncertain_fields': flags,
                            'recheck_indices': [reference], 'confirmation_status': 'PENDING',
                            'requires_user_review': True})
            except (OSError, ValueError, KeyError, subprocess.TimeoutExpired) as error:
                medication.product_rechecks.append({'status': 'FAILED', 'preprocessing': metadata,
                    'error_code': 'PRODUCT_OCR_TIMEOUT' if isinstance(error, subprocess.TimeoutExpired) else 'PRODUCT_OCR_FAILED'})
