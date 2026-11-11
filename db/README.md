# Database V4

PostgreSQL 18 persistence for Modules 1–3: 20 owned tables, 193 attributes and
40 restrictive foreign keys. The external `identity.users(id uuid NOT NULL
UNIQUE/PRIMARY KEY)` contract must exist for deployment migrations.

```text
db/
  migrations/          # ordered V4 migrations; applied files are immutable
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
Install `db/requirements.txt` in your chosen environment. Provide the six
approved CSVs locally under `data/datasets/`; they are intentionally excluded
from Git. Missing source data is a setup requirement, not a reason to substitute
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
run `db/manage.py migrate`, then `db/manage.py import`. This does not authorize
synthetic tests there. The migration runner rejects the retired Phase 2 schema;
no automatic prototype-to-V4 conversion is supplied.

## Maintenance

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
