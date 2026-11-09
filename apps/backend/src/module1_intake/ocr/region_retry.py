"""Optional regional evidence: never replace the original transcription."""
import json
import subprocess
import time

from .numbered_parser import parse_timing_labels
from .table_parser import plain


def compare_schedules(original, candidate):
    old = {plain(a.timing_raw or ''): a.dose_raw for a in original}
    new = {plain(a['timing_raw']): a['dose_raw'] for a in candidate}
    differences = []
    for timing in sorted(old.keys() | new.keys()):
        if timing not in old or timing not in new or old[timing] != new[timing]:
            conflict = timing in old and timing in new and old[timing] is not None and new[timing] is not None
            differences.append({'timing': timing, 'original_dose': old.get(timing),
                                'candidate_dose': new.get(timing),
                                'kind': 'conflict' if conflict else 'needs_review'})
    return differences


def retry_schedules(image, script, directory, extraction, deadline):
    attempts = 0
    for index, medication in enumerate(extraction.medications):
        if not medication.schedule_region:
            continue
        if medication.administrations and not any(a.issue or a.dose_raw is None for a in medication.administrations):
            continue
        for psm in (6, 7):
            if attempts >= 8 or time.monotonic() >= deadline:
                extraction.warnings.append('Regional OCR retry budget exhausted; original evidence retained.')
                return
            attempts += 1
            options = {'psm': psm, 'rectangle': medication.schedule_region}
            config = directory / f'retry-{index}-{psm}-options.json'
            output = directory / f'retry-{index}-{psm}.json'
            config.write_text(json.dumps(options), encoding='utf-8')
            try:
                process = subprocess.run(['node', str(script), str(image), str(output), str(config)],
                                         capture_output=True, text=True, encoding='utf-8',
                                         timeout=max(.01, min(20, deadline - time.monotonic())), check=False)
                if process.returncode:
                    raise ValueError('Regional OCR failed')
                raw = json.loads(output.read_text(encoding='utf-8'))
                candidate = parse_timing_labels(raw['text'])
                differences = compare_schedules(medication.administrations, candidate)
                medication.schedule_rechecks.append({'status': 'COMPLETED', 'ocr': raw,
                    'administrations': candidate, 'differences': differences,
                    'requires_user_review': True})
                flag = 'schedule_recheck_conflict' if any(d['kind'] == 'conflict' for d in differences) else 'schedule_recheck_review'
                if flag not in medication.uncertain_fields:
                    medication.uncertain_fields.append(flag)
            except (subprocess.TimeoutExpired, OSError, ValueError, KeyError) as error:
                medication.schedule_rechecks.append({'status': 'FAILED', 'options': options,
                    'error_code': 'REGION_OCR_TIMEOUT' if isinstance(error, subprocess.TimeoutExpired) else 'REGION_OCR_FAILED'})
                if 'schedule_recheck_failed' not in medication.uncertain_fields:
                    medication.uncertain_fields.append('schedule_recheck_failed')
