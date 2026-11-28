# Module 4/5 validation and remaining checkpoint

Branch: `feature/module4-hcp-module5-reminders`.

## Validation

- G4-fix: review route and atomic service added. `venv/Scripts/python -m pytest tests/backend/test_hcp_review.py tests/unit/module5 tests/integration/test_module4_5_api.py -q`: **18 passed, 1 skipped**. App import and OpenAPI review-route registration pass. The 8 new tests cover real Auth permissions, HTTP dispatch/validation, review evidence, and rollback using an isolated storage double; PostgreSQL closure remains unverified and subject to the existing guard.

- Current committed source, after archiving G4: `venv/Scripts/python -m pytest tests/backend tests/unit -q`: **568 passed, 8 failed, 12 skipped, 85 errors**. Comparison with the original baseline found **no new failing test names**. The latency test now passes.
- Current integration skeleton: `venv/Scripts/python -m pytest tests/integration/test_module4_5_api.py -q`: **1 skipped** because `MODULE2_TEST_DSN` is unset.

- Before implementation: `venv/Scripts/python -m pytest tests/backend tests/unit -q`: **557 passed, 9 failed, 12 skipped, 85 errors**. The extra failure compared with the handoff was the latency test.
- Historical run including the now-archived G4 draft: **578 passed, 8 failed, 12 skipped, 85 errors**. No new failing test names. Missing reference/DDInter data and the existing CLI subprocess failure remain.
- Historical targeted run (includes now-archived draft backend tests): `venv/Scripts/python -m pytest tests/backend/test_module4_5_api.py tests/unit/module5 tests/integration/test_module4_5_api.py -q`: **22 passed, 1 skipped**.
- Frontend baseline: build passed; **34 passed, 1 skipped**.
- Frontend revalidated after archiving G4: build passed; **37 passed, 1 skipped**. Existing specs were not edited. New browser tests use HTTP fixtures plus real local authentication; they do not establish PostgreSQL behavior.
- The PostgreSQL integration skeleton targets the full G4 review/closure contract, which remains blocked. Do not enable it as proof of a working flow until G4 is resolved within the approved scope. It requires a marked loopback database and performs no migrations or reference-data imports.

Logs are in ignored `artifacts/baseline-module45-*` and `artifacts/module45-*` files. The clean-source rerun uses `artifacts/module45-resume-build.log`, `artifacts/module45-resume-playwright.log`, `artifacts/module45-resume-python.log`, and `artifacts/module45-resume-integration.log`.

## G4 restriction

The handoff gained a prohibition on DB migration edits while implementation was underway. The existing `msa.system_domain_guard` invokes `msa.require_owner(NEW.user_id)` for a `review_cases` update, so the assigned HCP cannot close a case after recording an outcome. Changing the authenticated actor to impersonate the patient would violate the server identity contract.

The no-migration rule remains in force. The proposed SQL, review endpoint patch, and draft backend tests are archived in ignored `artifacts/module45-g4-draft/`, outside the active source and test trees. No migration is added or changed. The G4-fix now supplies the review endpoint and atomic review/closure service. Full HCP approval/activation remains blocked by the unchanged database guard; a rejected closure rolls back the outcome rather than reporting partial success. G4 remains blocked rather than bypassing the database guard or impersonating the patient. G1–G3 and G5 provide the handoff's minimum viable scope.

## Runtime behavior

- `GET /api/v1/hcp/capabilities` explicitly enables demo preview only when Core is unconfigured outside production. Failure of a configured Core never falls back to demo records.
- All domain reads run inside actor-scoped transactions. Multi-step domain writes compose atomically; the Core intake transaction rule remains unchanged. Existing database triggers persist business audit events.
- Reminder eligibility uses the latest completed assessment containing the exact entry. Risk/coverage conflicts return `HCP_REVIEW_REQUIRED`. Approval must match the same assessment before activation.
- Dose corrections append a record with `supersedes`; future doses cannot be recorded. Adherence counts due occurrences only and retains superseded schedule history. Root schedules begin on their creation date; revisions begin at their creation instant. DST gaps are omitted and repeated wall times occur once.
- Notifications are in-app banners on the reminder/history screen, refreshed every minute. No background push service is introduced.
