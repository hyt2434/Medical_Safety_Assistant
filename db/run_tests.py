"""Run real PostgreSQL V4 checks; record every PASS / FAIL / BLOCKED."""
import argparse
import json
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "db/tests"), str(ROOT / "db")]


class Results(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.records = []
    def addSuccess(self, test):
        super().addSuccess(test)
        self.records.append({"test": str(test), "status": "PASS"})
    def addFailure(self, test, error):
        super().addFailure(test, error)
        self.records.append({"test": str(test), "status": "FAIL", "details": self._exc_info_to_string(error, test)})
    def addError(self, test, error):
        super().addError(test, error)
        self.records.append({"test": str(test), "status": "FAIL", "details": self._exc_info_to_string(error, test)})
    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self.records.append({"test": str(test), "status": "BLOCKED", "details": reason})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dsn", default=os.environ.get("CORE_DB_DSN"))
    parser.add_argument("--report", type=Path, default=ROOT / "artifacts/core_db_v4/test-results.json")
    args = parser.parse_args()
    if not args.dsn:
        parser.error("Provide an isolated V4 checks CORE_DB_DSN")
    os.environ["CORE_DB_DSN"] = args.dsn
    suite = unittest.defaultTestLoader.discover(str(ROOT / "db/tests"), pattern="test_v4.py")
    result = unittest.TextTestRunner(verbosity=2, resultclass=Results).run(suite)
    payload = {"tests_run": result.testsRun, "PASS": sum(r["status"] == "PASS" for r in result.records),
               "FAIL": len(result.failures) + len(result.errors), "BLOCKED": len(result.skipped), "results": result.records}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in payload.items() if k != "results"}, indent=2))
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
