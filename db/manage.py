"""V4 baseline deployment and idempotent approved-data import; no identity migration."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from shared.db.importer import import_datasets

TEST_MARKER = "Medication Safety Assistant Core V4 isolated test"
# The earlier local baseline was reconstructed from the installed function bodies
# and matched this checksum byte for byte. 002 carries every difference forward.
# Keep both checksums pinned: this is not permission to accept arbitrary edits.
BASELINE_COMPATIBILITY = {
    "822b472e4d563978dac1698db1c021b9c40bf324883fb2be38a70d6c866d3827": {
        "282b3778b3485667a4eea9c8e87908472ebff052b5e1ec01fbb54b821b04796a"
    }
}


def identity_contract(db):
    row = db.execute("""
        SELECT a.attnum,a.atttypid='uuid'::regtype,a.attnotnull
        FROM pg_attribute a WHERE a.attrelid=to_regclass('identity.users')
        AND a.attname='id' AND NOT a.attisdropped
    """).fetchone()
    if not row or not row[1] or not row[2] or not db.execute("""
        SELECT EXISTS(SELECT 1 FROM pg_index WHERE indrelid='identity.users'::regclass
         AND indisunique AND indisvalid AND indnkeyatts=1 AND indkey[0]=%s AND indpred IS NULL)
    """, (row[0],)).fetchone()[0]:
        raise RuntimeError("BLOCKED: existing identity.users(id uuid NOT NULL UNIQUE/PK) contract required; identity is never altered")


def migrate(db):
    identity_contract(db)
    paths = sorted((ROOT / "db/migrations").glob("[0-9][0-9][0-9]_*.sql"))
    if not paths or paths[0].name != "001_v4.sql":
        raise RuntimeError("V4 baseline migration is missing")
    checksums = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    baseline = checksums["001_v4.sql"]
    with db.transaction():
        db.execute("SELECT pg_advisory_xact_lock(204004)")
        row = db.execute("SELECT obj_description(oid,'pg_namespace') FROM pg_namespace WHERE nspname='msa'").fetchone()
        if row:
            ledger = json.loads(row[0] or "{}")
            if ledger.get("version") != 4:
                raise RuntimeError("Retired prototype exists. Audit/remove only owned Core schemas before V4; no automatic destructive migration.")
            applied = dict(ledger.get("migrations", {"001_v4.sql": ledger.get("migration_sha256")}))
            if applied.get("001_v4.sql") != ledger.get("migration_sha256"):
                raise RuntimeError("V4 baseline ledger is inconsistent")
            for name, digest in applied.items():
                compatible = (name == "001_v4.sql" and digest in BASELINE_COMPATIBILITY.get(baseline, set()))
                if name not in checksums or (checksums[name] != digest and not compatible):
                    raise RuntimeError("Applied V4 migration checksum changed or file missing: " + name)
            # An applied migration after a missing predecessor is not a valid history.
            if list(applied) != list(checksums)[:len(applied)]:
                raise RuntimeError("V4 migration history is not an ordered prefix")
        else:
            applied = {}
            ledger = {"version": 4, "migration_sha256": baseline, "hash_contract": "pg-jsonb-text-v4"}
        pending = [path for path in paths if path.name not in applied]
        for path in pending:
            db.execute(path.read_text(encoding="utf-8"))
            applied[path.name] = checksums[path.name]
        ledger["migrations"] = applied
        db.execute(sql.SQL("COMMENT ON SCHEMA msa IS {}").format(sql.Literal(json.dumps(ledger, sort_keys=True))))
    return dict(ledger, reused_schema=row is not None, applied_migrations=[path.name for path in pending])


def bootstrap_test(dsn, *, explicit=False):
    options = conninfo_to_dict(dsn)
    name = options.get("dbname", "")
    if not explicit or not re.fullmatch(r"msa_core_test_v4[a-z0-9]+", name) or options.get("host") not in ("127.0.0.1", "::1", "localhost"):
        raise RuntimeError("Explicit --isolated-test, loopback and msa_core_test_v4<suffix> required")
    admin_dsn = make_conninfo(dsn, dbname="postgres")
    with psycopg.connect(admin_dsn, autocommit=True) as admin:
        found = admin.execute("SELECT pg_get_userbyid(datdba),shobj_description(oid,'pg_database') FROM pg_database WHERE datname=%s", (name,)).fetchone()
        if not found:
            admin.execute(sql.SQL("CREATE DATABASE {} ENCODING 'UTF8'").format(sql.Identifier(name)))
            admin.execute(sql.SQL("COMMENT ON DATABASE {} IS {}").format(sql.Identifier(name), sql.Literal(TEST_MARKER)))
        elif found[0] != admin.info.user or found[1] != TEST_MARKER:
            raise RuntimeError("Refusing to bootstrap an unowned/unmarked existing database")
    with psycopg.connect(dsn, autocommit=True) as db:
        if db.execute("SELECT to_regclass('identity.users')").fetchone()[0] is None:
            # Only a newly owned, explicitly marked isolated test database. Not a team identity deployment.
            if db.execute("SELECT count(*) FROM pg_namespace WHERE nspname NOT IN ('public','pg_catalog','information_schema') AND nspname NOT LIKE 'pg_%'").fetchone()[0]:
                raise RuntimeError("Test fixture requires otherwise empty database")
            with db.transaction():
                db.execute((ROOT / "db/tests/identity_fixture.sql").read_text(encoding="utf-8"))
        return migrate(db)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("bootstrap-test", "migrate", "import"))
    parser.add_argument("--dsn", default=os.environ.get("CORE_DB_DSN"))
    parser.add_argument("--csv-dir", type=Path, default=ROOT / "data/datasets")
    parser.add_argument("--report", type=Path)
    parser.add_argument("--isolated-test", action="store_true")
    args = parser.parse_args()
    if not args.dsn:
        parser.error("Provide CORE_DB_DSN or --dsn")
    if args.action == "bootstrap-test":
        result = bootstrap_test(args.dsn, explicit=args.isolated_test)
    else:
        with psycopg.connect(args.dsn, autocommit=True) as db:
            db.execute("SET TIME ZONE 'UTC'")
            result = migrate(db) if args.action == "migrate" else import_datasets(db, args.csv_dir)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
