# Module 4/5 validation

Branch: `feature/module4-hcp-module5-reminders`.

## G8 review fixes

- **G8-A:** Activation rejects any schedule with a child and uses the completed assessment attached to the reviewed case, provided its snapshot contains the exact entry. It does not require the latest assessment. The schedule list retains the last verified ancestor alongside its pending proposal and latest decision. The patient can disable the retained reminder and resend the pending proposal after REJECTED or CHANGES_REQUESTED.
- **G8-B:** Occurrences before `verified_at` (or `created_at`) are omitted. Dose writes require an exact occurrence of a verified schedule within its effective period, including timezone/DST boundaries. Historical corrections retain their original schedule identity. Schedule creation locks the entry and returns 409 if an active schedule already exists.
- **G8-C:** Only `domain_transaction()` composes domain operations. `transaction()` and inherited Core methods continue rejecting outer transactions. Structured errors lacking a message use a fallback. The assessment queue filters live cases to SAFETY, and SAFETY cases require a completed owned assessment.

No database migrations were added, edited, or applied. Existing database reminder eligibility rules remain authoritative: an ancestor can be disabled, but the guard rejects enabling a schedule with a child even while that child is unverified. The restored control reports the conflict rather than bypassing the guard; activate an approved current revision to enable its reminder.

## Required checks

- `venv/Scripts/python -m pytest tests/backend tests/unit -q`: **609 passed, 8 failed, 12 skipped, 85 errors**. Comparing failing test names against the previously recorded baseline found **no new failures or errors**. Missing reference/DDInter data and the existing CLI subprocess failure remain.
- `venv/Scripts/python -X utf8 C:/Users/Admin/AppData/Local/Temp/claude/54ac132e11eb8c9c/c1c36b89-014f-4804-af88-29f30dbea2c9/scratchpad/run_m45_db_tests.py`: **2 passed** against the existing marked loopback PostgreSQL test database.
- `npm run build`: **passed**.
- `npx playwright test`: **40 passed, 1 skipped**. The opt-in real intake/inference browser test remains skipped. Module 4/5 browser tests use HTTP fixtures and real local Auth; the separate PostgreSQL tests exercise real Core persistence.
- Focused G8-C run: **51 passed** across domain boundaries, review HTTP/Auth, and Module 5 unit tests.

Logs: `artifacts/g8-final-python.log`, `artifacts/g8-final-db.log`, `artifacts/g8-final-build.log`, `artifacts/g8-final-playwright.log`. Earlier group results are in `artifacts/g8-a-*` and `artifacts/g8-b-db.log`.

The formerly skipped integration fixture needed two corrections before it could execute: one-medication pair coverage is NOT_APPLICABLE, and FastAPI must override the original session dependency with a concrete signature. The dose fixture advances only the application clock to the next scheduled minute; database creation/verification timestamps remain real. No records are backdated or production guards disabled. Tests retain exact-owner cleanup on the marked database.

## Runtime notes

HCP review records only an outcome. Patient activation confirms the revision, enables its reminder using the reviewed assessment, and closes the case atomically. Rejected activation rolls back those changes; retries do not update an already-closed case.

Pending revisions do not end a verified ancestor's dose period. A verified replacement takes over at verification time, preserving earlier history and dose IDs. Notifications remain in-app banners refreshed every minute, with no background push service.
