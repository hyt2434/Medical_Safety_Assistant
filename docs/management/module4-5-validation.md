# Module 4/5 validation

Branch: `feature/module4-hcp-module5-reminders`.

## G11 scope and deferral

G11-A is deferred until after the PA4 deadline and coordination with the DB owner. The `one_schedule_root` index in migration 003 prevents a second standalone schedule for the same entry; the proposed model requires new migration 006. The uncommitted G11-A draft was removed. No migration was added, edited, or applied. The existing supersede-at-send model remains in place.

## Completed fixes

- G11-B: Re-enabling an HCP_VERIFIED schedule uses the APPROVED outcome referenced in its verification evidence and the reviewed case's assessment. That assessment must still be COMPLETED and cover the exact entry. Patient-confirmed schedules use the latest assessment. Disabling needs no assessment.
- G11-C: Schedule creation locks the medication item, checks that its entry is confirmed and newest, and rejects an active schedule on any version of the same item.
- G11-D: The due banner shows only pending enabled doses in the last 60 minutes. Older doses remain recordable. Adherence includes doses once they are at least 60 minutes overdue. Provider identity validation uses one Core ANY query, and case creation restricts the Auth query to the selected provider. Expected state errors use DomainConflict (409); unexpected ValueError returns a generic 500. Configuration errors retain their separate 503 mapping.

## Validation by commit

- G11-B: PostgreSQL 2 passed; production build passed; Playwright 41 passed / 1 skipped. Full Python 630 passed / 9 failed / 12 skipped / 85 errors: the baseline 8 failures plus a Module 1 latency failure under concurrent tests. The latency test passed in isolation without changes. Logs: `artifacts/g11-b-*`.
- G11-C: PostgreSQL 2 passed; production build passed; Playwright 41 passed / 1 skipped. Python 634 passed / 8 failed / 12 skipped / 85 errors, with no new failing names. Logs: `artifacts/g11-c-*`.
- G11-D: Focused Python 86 passed. PostgreSQL 2 passed; production build passed. Full Python 644 passed / 8 failed / 12 skipped / 85 errors, with no new failing names. Final Playwright rerun: 43 passed / 1 skipped. Logs: `artifacts/g11-d-*`.

All four requested commands were run for each goal before its commit. The existing Python failures/errors concern unavailable reference/DDInter data and the CLI subprocess import test. The browser suite's optional real intake/inference test remains skipped. Browser tests use HTTP fixtures and real local Auth; the PostgreSQL tests exercise actual Core persistence and exact-owner cleanup on the marked test database.

G11-D's initial browser run exposed an exact-text selector error in the new timing test and an old dated fixture in the existing banner test. The corrected fixture freezes the browser clock at the 60-minute boundary, where the banner and adherence eligibility both apply. Original behavioral assertions are retained.

## Runtime notes

HCP review records at most one outcome per case. Patient activation confirms the revision, enables its reminder using the reviewed assessment, and closes the case atomically. Failed activation rolls back those changes; retries do not update an already-closed case. Pending revisions preserve the previous verified schedule's dose period. Notifications remain in-app, with no background push service.
