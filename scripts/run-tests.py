"""Focused offline regressions; --research-data attempts all original data suites.

Run python -B scripts/run-tests.py. Runtime dependencies are listed in requirements.txt. See scripts/provision-data.ps1 help for local data.
"""
import argparse
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT)]
sys.dont_write_bytecode = True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--research-data', action='store_true')
    args = parser.parse_args()
    scratch = ROOT / 'tests/artifacts/tmp'
    scratch.mkdir(parents=True, exist_ok=True)
    tempfile.tempdir = str(scratch)
    loader = unittest.TestLoader()
    if args.research_data:
        suite = loader.discover(str(ROOT / 'tests'), top_level_dir=str(ROOT))
    else:
        suite = loader.loadTestsFromNames([
            'tests.unit.module2.test_reference.ParserTests',
            'tests.unit.module3.test_official.ConflictTests',
            'tests.unit.test_source_integration',
        ])
        suite.addTests(loader.loadTestsFromNames(['tests.backend.test_image_input', 'tests.backend.test_headerless', 'tests.backend.test_numbered_layout']))
        print('Dataset-dependent original suites excluded; use --research-data to attempt them.', flush=True)
    return 0 if unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
