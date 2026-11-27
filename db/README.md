# Database V4

## Unified local deployment

Auth, existing OCR reference rows and Core can share one PostgreSQL database.
Auth stays in `public`; Core uses `identity`, `msa` and `msa_ref`. OCR, Voice,
manual input and NLP persist through the same Core workflows. Retained OCR images
remain in `data/local/module1/runs`; the database stores their provenance.

Configure `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` (or
`DATABASE_URL`) in `apps/backend/.env`. Remove SQLite `AUTH_DB_PATH` and conflicting
`AUTH_DATABASE_URL` settings. From the repository root:

```powershell
python db/setup_system.py          # read-only preflight
python db/setup_system.py --apply  # backup, migrate, import, link
```

The database must already exist. Setup verifies a `pg_dump` backup before writing,
preserves accounts/passwords/grants/sessions and legacy OCR rows, applies Core
migrations and imports the six approved CSVs idempotently. An insert trigger
registers new Auth UUIDs in `identity.users`; existing accounts are backfilled
without granting permissions. A separately configured Core database is never
silently abandoned. Backups/reports stay in ignored `artifacts/system-db`.

After success `.env` contains `DATABASE_MODE=unified` and `CORE_REFERENCE_BUILD`.
Restart backend. Core uses the Auth connection automatically. Explicit
`CORE_DB_DSN` overrides, including an empty value in tests, retain priority.
SQLite test/preview overrides never implicitly reach the shared Core database.

Install OCR dependencies with `npm.cmd ci` in `src/module1_intake/ocr/node/ocr`
and place English/Vietnamese Tesseract models in its `tessdata` folder. DDInter is
needed for assessment, not saving drafts. Qwen, Whisper and the RAG index remain
separate runtime dependencies. Missing interaction data never means a safe result.

`tests/integration/test_unified_system.py` accepts only a marked loopback test DB
through `UNIFIED_POSTGRES_TEST_DSN`; set `RUN_UNIFIED_OCR=1` to exercise real OCR.

PostgreSQL 18 system schema: 36 Core tables, 326 columns and 71 restrictive
foreign keys, plus eight tables / 33 columns in the separate [Auth database](auth/README.md).
The original Core V4 baseline (20 tables / 193 columns / 40 FKs) is preserved.
`identity.users(id uuid NOT NULL UNIQUE/PRIMARY KEY)` is the Core store's local
identity registry; a linked Auth account uses the same UUID. No cross-database
foreign key or second identity-mapping table is introduced.

```text
db/
  migrations/          # ordered V4 migrations; applied files are immutable
  identity.sql         # explicit new-install Core UUID registry, not Auth tables
  scripts/             # local PostgreSQL utilities and read-only inspection SQL
  tests/               # PostgreSQL integration checks and synthetic fixtures
  docs/CONTRACT.md     # schema, data, ownership and application contracts
  manage.py           # guarded deployment/import CLI
  run_tests.py        # isolated V4 test runner
  schema_contract.json
  requirements.txt
src/shared/db/        # repository, importer and Modules 1–3 adapters
```

`db/` is the canonical Core V4 source in this repository.
Application adapters live in `src/shared/db/`; no sibling checkout is required. See [the V4 contract](docs/CONTRACT.md) for the
domain map, integration boundaries and migration compatibility rules.

## Setup and testing

Run from the repository root; Python 3.10+ and PostgreSQL 18 are required.
Install `db/requirements.txt` in your chosen environment. The six approved CSVs
are versioned under `data/datasets/`, the canonical source directory. Other local
datasets remain ignored. Missing source data is a setup requirement, not a reason to substitute
invented or unapproved datasets.

```powershell
py -3 -m pip install -r db/requirements.txt
# Start an EXISTING cluster; set paths to your local installation.
& ./db/scripts/postgres-local.ps1 -Action Start -ClusterOnly -RuntimeDirectory <runtime-directory> -PgBin <postgres-bin-directory>
$env:CORE_DB_DSN='host=127.0.0.1 port=55432 dbname=msa_core_test_v4newchecks user=core_fixture_admin'
# Choose an unused test database name; bootstrap marks it before creating fixtures.
py -3 -X utf8 db/manage.py bootstrap-test --isolated-test
py -3 -X utf8 db/manage.py import --report artifacts/core_db_v4/import.json
py -3 -X utf8 db/run_tests.py --report artifacts/core_db_v4/test-results.json
```

Replace angle-bracket paths before running the startup command. The test suite
writes synthetic records and requires a marked loopback database named
`msa_core_test_v4<suffix>checks`. Never run it on a shared or production database.
Migration and import retries are idempotent; the suite reports PASS/FAIL/BLOCKED.

For the existing combined Module 1–3/NLP real-data fixture, use the
[verified E2E guide](../src/module3_interactions/README.md#reproduce-the-real-data-e2e-run).
A marked schema-only database or a published synthetic build alone is insufficient
for `tests/integration/test_module3_real_e2e.py`; its tests never import references.

For a new local test installation, `scripts/provision-postgres.ps1` accepts
`-Archive <zip>` and `-RuntimeDirectory <directory>`; without an archive it
downloads the pinned distribution. Only a deliberately new runtime should use
`postgres-local.ps1 -Action Start -ClusterOnly -Initialize`. Initialization is
refused for an existing cluster. Loopback trust authentication is for isolated
testing only. Use `-Action Status` or `-Action Stop` with the same runtime path.

For an authorized deployment with the agreed identity contract, set its DSN and
run `db/manage.py provision-identity` if the local registry has not been installed,
then `db/manage.py migrate` and `db/manage.py import`. Existing registry data is
validated and never rewritten; the separate-store command rejects an Auth database
(use `setup_system.py --apply` for deliberate unified deployment). This does not authorize
synthetic tests there. The migration runner rejects the retired Phase 2 schema;
no automatic prototype-to-V4 conversion is supplied.

## Maintenance

`003_system_domains.sql` adds the SAD's proposed tables and per-box cabinet;
`004_domain_access_and_audit.sql` adds scoped RLS and transactional business audit;
`005_schedule_runtime_guard.sql` completes runtime guards without changing the
already applied migrations. The [contract](docs/CONTRACT.md) maps all domains and
documents JSONB, deletion, schedule verification and sharing rules.

For a schema-empty marked upgrade test DB and a separate system test DB, run:

```powershell
# Supply only verified loopback ...checks DBs; do not use an application DB.
$env:SYSTEM_TEST_DSN = '<marked system test DSN>'
$env:SYSTEM_UPGRADE_TEST_DSN = '<schema-empty marked systemupgrade test DSN>'
# prepare-test creates/marks a new test DB without installing schema or resetting it.
./.venv/Scripts/python.exe db/manage.py prepare-test --dsn $env:SYSTEM_UPGRADE_TEST_DSN --isolated-test
$env:PYTHONPATH = 'src;.;db'
./.venv/Scripts/python.exe -m pytest db/tests/test_system_domains.py -q
```

The upgrade checks read the unchanged baseline SQL and exercise both successful
upgrade and rollback after a synthetic failure. Schema/data changes in that DB
are rolled back. Application E2E uses existing, hash-verified reference fixtures;
it never resets a database. `tests/db_cleanup.py` creates unique owners, checks
the marker and cleanup privilege first, and removes only their records after
multi-connection APIs commit. Teardown temporarily sets replication role inside
its own administrative transaction because Core history forbids ordinary DELETE;
all behavioral tests run with guards enabled. It verifies zero remaining rows
and restoration to `origin`. Never use this teardown against deployment data.

Run shared-DB test groups sequentially: global before/after integrity checks
intentionally detect unrelated concurrent writes. API concurrency is exercised
inside its dedicated tests with generated identities.

- Keep SQL migrations byte-for-byte stable after application. Add a numbered
  migration for future changes; `.gitattributes` preserves their exact bytes.
- Keep `CORE_DB_DSN` in the local environment. Runtime files, pgdata, retained
  manifests, test reports and interaction evidence stay in ignored
  `artifacts/core_db*` locations. Moving source must not break retained locators.
- `scripts/verify_v4_readonly.sql` inspects V4 in a read-only transaction; execute
  it as one script against the intended database.
- Secrets, local archives, virtual environments, caches, generated artifacts and
  private datasets do not belong in Git. Import approval is separate from
  dataset redistribution permission. Historical implementations and execution
  reports are local archive material, not active deployment dependencies.
