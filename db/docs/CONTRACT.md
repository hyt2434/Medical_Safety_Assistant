# Core Database V4

PostgreSQL 18 stores exactly 20 Core tables: four reference tables, nine
conversation/intake tables, five safety tables and two patient health tables.
The schema has 193 attributes and 40 foreign keys with restrictive update/delete
behavior. `identity.users(id uuid NOT NULL UNIQUE/PRIMARY KEY)` is an external
dependency, excluded from the Core count and never altered by migrations.

Setup, runtime utilities and test commands are in [../README.md](../README.md).

## Migration and preserved history

`001_v4.sql` remains the existing local V4 baseline. The additive
`002_v4_guard_completion.sql` publishes the completed reference, finding and
workflow guards and removes an ambiguous SQL alias in terminal coverage checks.
It changes functions and a trigger, without rewriting tables, UUIDs, historical
confirmations, snapshot hashes or assessment results.

`manage.py migrate` holds one advisory lock and applies all pending files in one
transaction. The `msa` schema comment records every applied file's SHA-256.
Retries apply no files. Changed or missing applied migrations are rejected.
The exact earlier local V4 baseline (`282b3778...04796a`) is compatible with the
unchanged current baseline (`822b472e...6d3827`): its original bytes were
reconstructed from the installed functions and verified against its recorded
checksum. Migration 002 carries every audited difference forward, and the
original checksum remains in the ledger. This exception accepts only the pinned
pair of checksums; it does not accept arbitrary baseline changes.

The retired 19-table prototype is rejected. Migration from that schema needs an
explicit history compatibility plan; this implementation supplies no destructive
reset or automatic conversion of old confirmations into V4 semantics.

## Approved reference data

The six unchanged CSVs in `data/datasets/` produce one atomic immutable build:

| Source | Stored records |
| --- | ---: |
| medications | 10,670 relational rows |
| ingredients | 1,940 relational rows |
| medication_ingredients | 12,899 relational rows |
| ddinter_mappings | 5,675 relational rows |
| medication_indications | 5,614 JSONB elements on medications |
| medication_priorities | 6,105 JSONB elements on medications |

All 42,903 source IDs remain represented: 31,184 relational rows and 11,719
related JSONB elements. The build pins six byte hashes, projection version
`core-db-v4.1`, approval scope and hash contract. IDs are deterministic within the
build. Retries reconcile exact source-ID sets and reuse the published build.
Historical review flags remain provenance and do not filter approved mappings.

DDInter rows preserve source names in `source_locator.source_attributes`, target
IDs, mapping sets, catalog hashes and retrieval evidence. Missing values remain
unknown. Snapshots pin all mapping UUIDs and builds, including multiple targets;
approved mapping availability does not imply complete loaded interaction scope.
Registration and release details remain in product JSONB. Route, equivalence
text and match confidence retain their nullable contracts.

## Application boundary

```python
import psycopg
from shared.db import CoreRepository

with psycopg.connect(dsn, autocommit=True) as connection:
    repo = CoreRepository(connection, authenticated_owner=server_subject_uuid)
    conversation = repo.create_conversation()
    intake = repo.create_intake(conversation["id"])
```

The owner UUID comes from trusted server identity. Repository methods set a
transaction-local owner context and own independent transactions. They reject an
outer transaction so a published warning commits before later fallible checks.
These guards are not authentication or database RLS: deployment roles and the
server's identity integration must enforce who may set this context.

- Module 1's `persist_module1` retains original input digests, typed extraction
  output and unconfirmed entry versions. `confirm_entry` requires an explicit
  owner action, the exact displayed digest and an idempotency key. Corrections
  append versions and require fresh confirmation.
- Module 2's `run_identification` uses the approved Core build or an existing
  identifier with an explicit accepted source crosswalk. Confirmed input is
  required; ambiguous and missing identities remain represented in snapshots.
- Module 3's `run_safety` calls the existing dataset lookup for each supported
  target combination, commits findings before the next lookup and records
  coverage separately from execution. Duplicate exposure has a separate rule.
  Conflicts, missing loaded targets, absent pair records and later failures keep
  their limitations. The output does not infer a safe medication list from
  empty findings. Retry attempts preserve earlier warnings.
- Summary drafts pin content and source manifests. `confirm_summary` saves an
  immutable version only after exact owner confirmation, then completes the
  workflow atomically. Cross-owner questions, changed source digests and stale
  revisions are rejected.

Application JSON hashes use `pg-jsonb-text-v4` through PostgreSQL `msa.digest`.
File hashes use original bytes; manifest hashes use the versioned canonical
manifest encoding. Keep source CSVs, manifest artifacts and interaction evidence
available for the lifetime of records that reference them.

Production authentication/RBAC/RLS, HTTP/UI confirmation handlers, retention,
backups, external Module 2 crosswalks and real DDInter catalog coverage remain
deployment integration work. The synthetic PostgreSQL suite verifies persistence
behavior and does not establish clinical correctness or real coverage.

## Domain map

The schema and repository share transaction and ownership guards across domains.
They stay intact rather than splitting SQL history or introducing empty domain
packages. New independent features can add focused modules under `src/shared/db`
and additive, numbered migrations under `db/migrations`.

| Responsibility | Current implementation |
| --- | --- |
| Medication reference | `msa_ref`, `src/shared/db/importer.py`, `identification_adapter.py` |
| Conversation and intake | `msa` conversation/intake tables, `intake_adapter.py`, repository methods |
| Safety assessment | `msa` snapshots/assessments/findings, `safety_adapter.py`, repository methods |
| Patient health | `msa` health sources/summaries/workflow, repository methods |
| Shared persistence | `src/shared/db/repository.py`; owner and transaction boundaries |
| Deployment and contract | `db/manage.py`, `db/migrations/`, `db/schema_contract.json` |

Modules 1, 2 and 3 keep their existing algorithms. Their persistence adapters
now import from `shared.db`; public method signatures remain unchanged.
