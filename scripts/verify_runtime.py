"""Read-only check of local Unified/Module 3 data: missing=2, invalid=1, ready=0.

See scripts/provision-data.ps1 help. No datasets are copied or regenerated.
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT)]
from module2_medications.unified import UnifiedMedicationReference, default_config
from module2_medications.service import assess_prescriptions


def main():
    config = default_config(ROOT)
    if not config.is_file():
        print('UNAVAILABLE: ' + str(config.relative_to(ROOT)))
        print('Supply reviewed supplements/evidence and DDInter CSVs; rebuild locally. See scripts/provision-data.ps1 help.')
        return 2
    try:
        reference = UnifiedMedicationReference(config)
        try:
            terminology = reference.terminology()
            result = assess_prescriptions({'medications': []}, reference, terminology)
            assert result['module3']['safe_to_take'] is None
            print('Unified Reference and DDInter data: PASS; no clinical data exercised.')
        finally:
            reference.close()
    except FileNotFoundError as exc:
        print('UNAVAILABLE local source: ' + str(exc))
        return 2
    except (ValueError, AssertionError) as exc:
        print('INVALID runtime data: ' + str(exc))
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
