# Module 4/5 validation and remaining checkpoint

Branch: `feature/module4-hcp-module5-reminders`.

## Validation

- Before implementation: `venv/Scripts/python -m pytest tests/backend tests/unit -q`: **557 passed, 9 failed, 12 skipped, 85 errors**. The extra failure compared with the handoff was the latency test.
- After implementation (including the local G4 draft): **578 passed, 8 failed, 12 skipped, 85 errors**. No new failing test names. Missing reference/DDInter data and the existing CLI subprocess failure remain.
- Latest targeted run: `venv/Scripts/python -m pytest tests/backend/test_module4_5_api.py tests/unit/module5 tests/integration/test_module4_5_api.py -q`: **22 passed, 1 skipped**.
- Frontend baseline: build passed; **34 passed, 1 skipped**.
- Frontend final: build passed; **37 passed, 1 skipped**. Existing specs were not edited. New browser tests use HTTP fixtures plus real local authentication; they do not establish PostgreSQL behavior.
- PostgreSQL integration is skipped without `MODULE2_TEST_DSN`. It requires an existing marked loopback test database migrated through the proposed 006 migration; it does not migrate databases or import clinical/reference data.

Logs are in ignored `artifacts/baseline-module45-*` and `artifacts/module45-*` files.

## G4 restriction

The handoff gained a prohibition on DB migration edits while implementation was underway. The existing `msa.system_domain_guard` invokes `msa.require_owner(NEW.user_id)` for a `review_cases` update, so the assigned HCP cannot close a case after recording an outcome. Changing the authenticated actor to impersonate the patient would violate the server identity contract.

A local, uncommitted proposal adds `006_hcp_case_closure.sql`. It retains every existing guard and permits only the assigned HCP with current consent and `clinical.case_review` to move an OPEN/IN_REVIEW case to CLOSED after an outcome from that reviewer exists. No table or applied migration is changed. The review service records the outcome and closes the case atomically. Those service/route changes and their backend tests remain local pending an explicit exception to the handoff restriction. The draft PR does not contain the review endpoint.

## Runtime behavior

- `GET /api/v1/hcp/capabilities` explicitly enables demo preview only when Core is unconfigured outside production. Failure of a configured Core never falls back to demo records.
- All domain reads run inside actor-scoped transactions. Multi-step domain writes compose atomically; the Core intake transaction rule remains unchanged. Existing database triggers persist business audit events.
- Reminder eligibility uses the latest completed assessment containing the exact entry. Risk/coverage conflicts return `HCP_REVIEW_REQUIRED`. Approval must match the same assessment before activation.
- Dose corrections append a record with `supersedes`; future doses cannot be recorded. Adherence counts due occurrences only and retains superseded schedule history. Root schedules begin on their creation date; revisions begin at their creation instant. DST gaps are omitted and repeated wall times occur once.
- Notifications are in-app banners on the reminder/history screen, refreshed every minute. No background push service is introduced.
