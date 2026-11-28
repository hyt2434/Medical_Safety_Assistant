# Module 4/5 validation

Branch: `feature/module4-hcp-module5-reminders`.

## G4-fix2

- HCP review calls only `record_review`. It does not update the patient's case.
- Patient activation selects the latest outcome for the current assessment and requires approval. It locks the owned case, confirms the revision, enables its reminder, and closes the case in one transaction. Failure rolls back activation; retrying an already-closed case does not update it again.
- Pending unverified revisions no longer truncate verified schedule history. Today, history, and adherence follow verified ancestors through revision chains. A verified replacement takes over at `verified_at`, preserving earlier occurrences and their original schedule IDs for recording/correction.
- No migrations or actor impersonation are required. The former ownership blocker is resolved by closing the case in the patient action.

Validation:

- `venv/Scripts/python -m pytest tests/unit/module5 tests/backend/test_hcp_review.py tests/integration/test_module4_5_api.py -q`: **26 passed, 1 skipped**. Includes eight new Module 5 service/selection regression cases, updated outcome-only HCP service checks, and existing HTTP/Auth validation.
- `npx playwright test tests/hcp-case.spec.ts tests/reminders.spec.ts`: **3 passed**. The review fixture now explicitly leaves the case OPEN until patient activation.
- The PostgreSQL integration test now checks pending-ancestor recording, OPEN after HCP review, and CLOSED after patient activation using the existing migrations. It skips because `MODULE2_TEST_DSN` is unset; real database execution remains unverified.
- Logs: `artifacts/g4-fix2-tests.log` and `artifacts/g4-fix2-playwright.log`.

## Earlier baseline evidence

- Original Python baseline: **557 passed, 9 failed, 12 skipped, 85 errors**.
- Last full Python run before these fixes: **568 passed, 8 failed, 12 skipped, 85 errors**, with no new failing test names. Missing reference/DDInter data and the existing CLI subprocess failure remain; the latency test passed on rerun.
- Frontend baseline: build passed; **34 passed, 1 skipped**. Last full browser run: **37 passed, 1 skipped**, and production build passed.
- These full-suite counts are historical, not a new full-suite run for G4-fix2. The targeted current results are listed above.

## Runtime behavior

- Explicit preview mode is available only when development Core is unconfigured. Failed requests to configured Core never fall back to synthetic records.
- Domain reads use actor-scoped transactions; compound patient activation is atomic. Database triggers retain business auditing.
- Risk/coverage conflicts return `HCP_REVIEW_REQUIRED`; activation requires approval for the latest completed assessment containing the exact entry.
- Root schedules begin on their creation date; verified revisions begin at verification time. DST gaps are omitted and repeated wall times occur once. Future doses cannot be recorded, and corrections append a record with `supersedes`.
- Notifications remain in-app banners refreshed every minute; no background push service is introduced.
