# Core Database V4

PostgreSQL 18 stores 36 Core tables, 326 columns and 71 restrictive foreign keys.
The original 20 tables / 193 columns / 40 FKs remain the Core V4 baseline; system
extensions add the SAD's 15 proposed tables and one per-box medication cabinet.
Eight Auth/RBAC tables remain in a separate store. `identity.users(id uuid NOT NULL
UNIQUE/PRIMARY KEY)` is the local Core identity registry, excluded from the Core
count and never altered by these migrations. Auth and Core use the same UUID.

For a new Core installation, `db/identity.sql` and the explicit
`manage.py provision-identity` command install that existing registry contract.
Retries validate its UUID key without changing rows or columns; a malformed
registry or an Auth database is refused. The test-only duplicate DDL has been
removed. Regular `migrate` still validates this prerequisite before any Core DDL.

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

Migrations 003–005 extend V4 without rewriting reference builds, confirmation
digests, UUIDs or existing source content. They add domain tables, row policies,
runtime guards and write audit. Use `manage.py migrate` for existing V4; never
edit an applied file or drop/recreate a database to bypass an upgrade.

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
RLS is enabled and forced on every Core business table. The authenticated UUID
and the existing Auth catalog's effective permissions are trusted server input,
never request fields. Each repository transaction clears a reused connection's
session baseline, sets its identity/permissions locally, and uses UTC. Public
reads establish the same context as writes; LOCAL context disappears on commit
or rollback. Missing context denies business access. Reference data stays public
to the application DB role. GUCs carry Auth decisions; they are not a second role
catalog or an authentication endpoint.

Deployment application roles must not own the tables/functions, be superuser,
have BYPASSRLS or be able to assume the migration owner. Grant only required
schema/table/function privileges. The small, fixed-query consent functions use
SECURITY DEFINER under the controlled migration owner to avoid RLS recursion;
their own actor, grant, scope and expiry checks remain mandatory. The summary
function rejects missing context before loading/rendering any data.

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

Auth, owner-scoped backend intake and RLS are implemented. Retention/backups,
deployment grants, external Module 2 crosswalks and clinical/data coverage remain
separate concerns. Persistence checks do not establish clinical correctness.

## System-wide SAD mapping

Design source: `docs/pa/pa3/Software Architecture Document.pdf`, 54 pages,
PA3-Group02-SAD Version 1.0. The six-page `build/main.pdf` is an older partial
document. The approved supplements override ERD 10's string timestamps/integer
success and composite user-role PK, and supply UC-19's missing physical box model.
The exact columns, keys, checks, indexes and row policies are in
[`schema_contract.json`](../schema_contract.json); it also records the unchanged
baseline and the separate Auth contract (eight tables / 33 columns). Contract
checks compare actual indexes, triggers, forced RLS and row policies on both a
fresh Core installation and an upgrade; native Auth checks also compare exact
constraints, including grant interval exclusion.

| SAD area | Physical representation | Implementation boundary |
| --- | --- | --- |
| ERD 01 | Existing four `msa_ref` tables; new `dataset_review_decisions` | Versioned references/importer retained. Review decisions use source IDs/evidence and never edit a released build. Reviewer API is not implemented. |
| ERDs 02–04 | Existing conversation/intake/entry/match/snapshot/assessment/finding tables | Existing Module 1–3 services, confirmation, revision, provenance and backend adapters retained; owner/RLS context added to reads. |
| ERD 05 | Existing `patient_health_sources`; new `patient_health_facts`, `patient_medication_uses` | A fact is an exact indexed projection of a source's fact array, not an editable competing copy. Medication-use dates/status are separate from cabinet stock/expiry. Profile APIs remain future work. |
| ERD 06 | Existing immutable `patient_health_summaries`; new `review_cases`, `review_case_permissions`, `review_case_messages`, `review_outcomes`, `summary_shares` | Concrete persistence in `DomainRepository`, consent guards, bounded HCP access and masked sharing. Case queue/clinical workflow/UI are not implemented. |
| ERD 07 | `medication_schedules`, `reminder_settings`, `schedule_change_requests`, `dose_records` | Concrete storage, exact-version verification, activation guards, idempotent occurrence recording and append-only corrections. Notification delivery, recurrence generation and adherence views are not implemented. |
| UC-19 / supplement A | `medication_cabinet_items` | Each UUID is one box/lot. Same product may have different or unknown expiry dates. Raw name survives unidentified products; optional product/build must be a valid pair. No quantity ledger or inferred dates. |
| ERD 08 | `support_tickets`, `support_messages` | Assigned-ticket access, replies and null-safe ownership enforced in DB. Admin `operations.assign` permits assignment metadata, not unrelated message content. Support service/UI remain future work. |
| ERD 09 | `msa.audit_events` | Transactional business write audit with actor, subject, resource and row digests; no copied patient payload. Separate from Auth events. |
| ERD 10 / supplements B–D | Separate Auth eight tables | Native UUID/aware times/boolean, immutable per-grant history, concurrent interval protection and last-permanent-admin guards; existing session/API services updated. |

## JSONB and schedule contracts

Existing V4 JSONB validators and digest algorithms remain unchanged.
`msa.domain_evidence` checks a versioned consent/review object with nonempty
`sources` containing a locator and SHA-256. Health fact projection checks compare
the original source's index, field, JSON value, raw text and uncertainty exactly.

`schedule.v1` requires nonempty distinct `HH:MM` clock slots and `dose_raw`.
An IANA zone is a separate required column. The full schedule JSON, zone,
source kind and exact entry-version UUID contribute to its generated digest.
This is stored instruction data; it does not generate a daily recurrence or
invent frequency/duration. A future scheduler must interpret only verified
instructions. UTC `scheduled_for` disambiguates a dose occurrence, including
repeated local times at a DST boundary; the DB checks its local clock slot.

Patient verification is allowed only for `PRESCRIPTION_TRANSCRIPTION` with clock
and dose pairs actually present in the original administrations. Missing or new
timing requires HCP review. `schedule-verification.v1` binds explicit consent,
the entry digest, schedule digest and a confirmation UUID; HCP verification also
pins an approved outcome for that exact schedule. A confirmation UUID cannot be
reused for another schedule. Revisions append rows and lose the old verification.

New reminders require current verified instructions and a completed assessment
containing the exact entry version. Unsupported coverage or an implicated severe
warning requires an explicit HCP outcome bound to that schedule and assessment.
Eligibility means permission to activate a reminder, not clinical safety. Existing
reminders and treatment are never changed automatically when new findings,
revisions, proposals or consent revocations arrive. Preferences use
`notification-preferences.v1` with `IN_APP` or `BROWSER`; delivery is not provided.

One dose is `(schedule_id, scheduled_for)`. A unique root and single-successor
chain prevent duplicate/conflicting histories even under concurrent requests.
Corrections append TAKEN/MISSED/SKIPPED rows for the same occurrence. No adherence
percentage, expiry flag or days-remaining value is persisted.

## Consent, ownership and audit

HCP role permission alone never opens patient records. An assigned HCP needs an
effective grant for the exact case. Its RLS scope includes that case's schedule,
entry versions, snapshot and assessment context, not the whole conversation or
health profile. Case access does not grant summary access.

Summary grants pin an immutable confirmed summary. FULL grants return it whole;
SECTIONS grants require existing section keys. `msa.shared_summary(grant_id)`
renders only permitted sections, omitting the unrestricted content and source
manifest. Row-level access alone is not used as section-level authorization.
Revocation/expiry applies to the selected grant and affects subsequent access;
it does not erase historical outcomes or clinical warnings. Existing outcomes
cannot approve another schedule revision or assessment.

Support requesters and assigned permitted staff can read the appropriate ticket
conversation; an unassigned NULL never authorizes another account. Business
mutations append audit in the same transaction, so failed writes leave neither
partial domain records nor success audit. Audit contains row digests rather than
duplicated source/clinical JSON. Authentication actions remain in the Auth store.

Core FKs use RESTRICT and retained history rejects DELETE/TRUNCATE. Mutable
settings/cabinet/ticket fields retain ownership and write audit; sources,
versions, review outcomes, messages and dose history append instead of rewriting.
Test teardown's narrowly scoped administrative cleanup is not a production API.

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
