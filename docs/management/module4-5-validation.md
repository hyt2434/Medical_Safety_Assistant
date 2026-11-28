# Module 4/5 validation

Branch: `feature/module4-hcp-module5-reminders`.

## G8 review fixes

- **G8-A:** Activation rejects any schedule with a child and uses the completed assessment attached to the reviewed case, provided its snapshot contains the exact entry. It does not require the latest assessment. The schedule list retains the last verified ancestor alongside its pending proposal and latest decision. The patient can resend the pending proposal after REJECTED or CHANGES_REQUESTED. G10 restores disabling and restricts pending status to undecided proposals.
- **G8-B:** Occurrences before `verified_at` (or `created_at`) are omitted. Dose writes require an exact occurrence of a verified schedule within its effective period, including timezone/DST boundaries. Historical corrections retain their original schedule identity. Schedule creation locks the entry and returns 409 if an active schedule already exists.
- **G8-C:** Only `domain_transaction()` composes domain operations. `transaction()` and inherited Core methods continue rejecting outer transactions. Structured errors lacking a message use a fallback. The assessment queue filters live cases to SAFETY, and SAFETY cases require a completed owned assessment.

No database migrations were added, edited, or applied. Existing database reminder eligibility rules remain authoritative: an ancestor can be disabled, but the guard rejects enabling a schedule with a child even while that child is unverified. The UI blocks enabling while an undecided proposal exists, but always permits disabling when idle. Reviewed leaves remain separate actionable entries. Database eligibility still applies to enable requests; activate an approved current revision to enable its reminder.

## G9 review fixes

Timezone lookup OSError becomes request validation failure. The original G9 pending-toggle behavior is superseded by G10; HCP_REVIEW_REQUIRED selects the proposal ID for the send form. Owner/DSN configuration failures map to 503 before the domain ValueError-to-409 boundary; unauthorized owner failures remain 403. Thirteen focused backend regression checks pass.

## G10 final fixes

Only undecided leaves are grouped as pending proposals; reviewed leaves remain visible for resend or activation. An undecided proposal blocks enabling but never disabling an existing reminder. Review submission locks the accessible case and rejects any existing outcome before recording; the UI hides the review form once an outcome exists. Schedule creation trims comma-separated times, removes empty tokens, and rejects empty or invalid HH:MM values before sending a request.

## Required checks

- `venv/Scripts/python -m pytest tests/backend tests/unit -q`: **626 passed, 8 failed, 12 skipped, 85 errors**. Comparing failing test names against the previously recorded baseline found **no new failures or errors**. Missing reference/DDInter data and the existing CLI subprocess failure remain.
- `venv/Scripts/python -X utf8 C:/Users/Admin/AppData/Local/Temp/claude/54ac132e11eb8c9c/c1c36b89-014f-4804-af88-29f30dbea2c9/scratchpad/run_m45_db_tests.py`: **2 passed** against the existing marked loopback PostgreSQL test database.
- `npm run build`: **passed**.
- `npx playwright test`: **41 passed, 1 skipped**. The opt-in real intake/inference browser test remains skipped. Module 4/5 browser tests use HTTP fixtures and real local Auth; the separate PostgreSQL tests exercise real Core persistence.
- Focused G10 run: **46 passed** across review HTTP/Auth and Module 5 unit tests.

G10 logs: `artifacts/g10-python.log`, `artifacts/g10-db.log`, `artifacts/g10-build.log`, `artifacts/g10-playwright.log`. Module 4/5 work stops after the final G10 commit.

G9 historical logs: `artifacts/g9-python.log`, `artifacts/g9-db.log`, `artifacts/g9-build.log`, `artifacts/g9-playwright-verified.log`. The initial browser run loaded stale reminder assertions. A rerun exposed a pre-existing HCP role-switch/navigation race; HCP tests now wait for the authenticated workspace before navigating, with all original assertions retained. Earlier attempts remain in `artifacts/g9-playwright.log` and `artifacts/g9-playwright-final.log`. G8 logs remain in `artifacts/g8-*`.

The formerly skipped integration fixture needed two corrections before it could execute: one-medication pair coverage is NOT_APPLICABLE, and FastAPI must override the original session dependency with a concrete signature. The dose fixture advances only the application clock to the next scheduled minute; database creation/verification timestamps remain real. No records are backdated or production guards disabled. Tests retain exact-owner cleanup on the marked database.

## Runtime notes

HCP review records at most one outcome per case. Patient activation confirms the revision, enables its reminder using the reviewed assessment, and closes the case atomically. Rejected activation rolls back those changes; retries do not update an already-closed case.

Pending revisions do not end a verified ancestor's dose period. A verified replacement takes over at verification time, preserving earlier history and dose IDs. Notifications remain in-app banners refreshed every minute, with no background push service.
