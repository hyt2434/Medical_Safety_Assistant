"""Load repository reference CSVs into the configured application PostgreSQL.

Keeps source rows verbatim, separate from Core V4 clinical/identity tables.
Run: python db/scripts/import-reference.py
"""
import csv
import json
import sys
from pathlib import Path
from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps/backend/src"))
from auth.db import engine

SOURCES = ("medications", "ingredients", "medication_ingredients", "medication_indications", "medication_priorities", "ddinter_mappings")

def main():
    with engine().begin() as connection:
        connection.execute(text("CREATE TABLE IF NOT EXISTS reference_source_rows (source varchar(64) NOT NULL, ordinal integer NOT NULL, payload jsonb NOT NULL, PRIMARY KEY(source, ordinal))"))
        for source in SOURCES:
            path = ROOT / "data" / f"{source}.csv"
            with path.open(encoding="utf-8-sig", newline="") as stream:
                rows = list(csv.DictReader(stream))
            connection.execute(text("DELETE FROM reference_source_rows WHERE source=:source"), {"source": source})
            statement = text("INSERT INTO reference_source_rows(source,ordinal,payload) VALUES (:source,:ordinal,CAST(:payload AS jsonb))")
            for start in range(0, len(rows), 500):
                connection.execute(statement, [{"source": source, "ordinal": i + 1, "payload": json.dumps(row, ensure_ascii=False)} for i, row in enumerate(rows[start:start+500], start)])
            print(f"{source}: {len(rows)}")

if __name__ == "__main__":
    main()
