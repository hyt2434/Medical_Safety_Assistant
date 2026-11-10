"""Read receipt item regions again, retaining candidates without overwriting."""
import json
import re
import subprocess
import time

FIELDS = ('unit_raw', 'quantity_raw', 'unit_price_raw', 'amount_raw', 'lot_number_raw', 'expiry_date_raw')


def parse_candidate(text):
    result = dict.fromkeys(FIELDS)
    # Require all four adjacent cells; never infer missing values arithmetically.
    cells = re.search(r'\b(Viên|Vien|Chai|Hộp|Hop|Gói|Goi|Ống|Ong|Tuýp)\s+(\d+)\s+(\d+(?:[.,]\d+)*)\s+(\d+(?:[.,]\d+)*)\b', text, re.I)
    if cells:
        result.update(zip(FIELDS[:4], cells.groups()))
    lot = re.search(r'Số\s+l[ôò]\s*:\s*([A-Za-z0-9-]+)', text, re.I)
    expiry = re.search(r'HSD\s*:\s*(\d{2}/\d{2}/\d{4})', text, re.I)
    result['lot_number_raw'] = lot[1] if lot else None
    result['expiry_date_raw'] = expiry[1] if expiry else None
    return result


def retry_receipt(image, script, directory, extraction, deadline):
    attempts = 0
    for index, item in enumerate(extraction.receipt_items):
        if not item.get('item_region') or not any(item.get(key) is None for key in FIELDS):
            continue
        # A region includes both the item row and its lot/expiry row.
        for psm in (6, 11):
            if attempts >= 8 or time.monotonic() >= deadline:
                extraction.warnings.append('Receipt retry budget exhausted; original evidence retained.')
                return
            attempts += 1
            options = {'psm': psm, 'rectangle': item['item_region']}
            config = directory / f'receipt-{index}-{psm}-options.json'
            output = directory / f'receipt-{index}-{psm}.json'
            try:
                config.write_text(json.dumps(options), encoding='utf-8')
                process = subprocess.run(['node', str(script), str(image), str(output), str(config)],
                    capture_output=True, text=True, encoding='utf-8',
                    timeout=max(.01, min(20, deadline-time.monotonic())), check=False)
                if process.returncode:
                    raise ValueError('Receipt retry failed')
                raw = json.loads(output.read_text(encoding='utf-8'))
                candidate = parse_candidate(raw['text'])
                differences = [{'field': key, 'original_value': item.get(key), 'candidate_value': candidate[key],
                    'kind': 'conflict' if item.get(key) is not None and candidate[key] is not None else 'needs_review'}
                    for key in FIELDS if item.get(key) != candidate[key]]
                item['item_rechecks'].append({'status': 'COMPLETED', 'ocr': raw,
                    'candidate_fields': candidate, 'differences': differences, 'requires_user_review': True})
            except (subprocess.TimeoutExpired, OSError, ValueError, KeyError) as error:
                item['item_rechecks'].append({'status': 'FAILED', 'options': options,
                    'error_code': 'REGION_OCR_TIMEOUT' if isinstance(error, subprocess.TimeoutExpired) else 'REGION_OCR_FAILED'})
