"""Build PA4 test-case workbook (Group 02) from the instructor's template.

Run from repo root:  python docs/pa/pa4/tools/build_test_cases.py
Status policy: Pass = covered by an automated test that passed in the 28 Nov 2026
system run (test named in Remark); Not run = not executed yet (reason in Remark).
"""
from copy import copy
from datetime import datetime
from pathlib import Path
import openpyxl

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / 'test-cases template-v1.1.xlsx'
OUT = ROOT / 'PA4-Group02-Test-Cases.xlsx'
DATE = datetime(2026, 11, 28)
TESTER = 'HYTrang'
P, N = 'Pass', 'Not run'
SAME = 'The same as ER'

# Implementation level per use case (shown in Features sheet).
LIVE = 'Implemented (server + UI)'
PROTO = 'UI prototype only (local data, not persisted)'
FUTURE = 'Out of scope for this release (future development)'

UC = [
 ('UC-01', 'Sign In', 'A registered user signs in and receives access to the features permitted by their role.', LIVE, [
  ('Sign in with valid patient credentials', '1. Open /login\n2. Enter a valid patient account and password\n3. Click Sign in', '1. Session cookie is created\n2. Patient dashboard opens with patient features only', P, SAME, 'Auto: test_auth::test_login_me_and_logout; workflows.spec "password login, locked account, multi-role context, refresh and logout"'),
  ('Sign in with wrong password', '1. Enter a valid account\n2. Enter a wrong password\n3. Click Sign in', '1. Error message is shown\n2. No session is created', P, SAME, 'Auto: test_auth::test_wrong_password_and_locked_account'),
  ('Sign in with a locked or inactive account', '1. Use an account that is locked/inactive\n2. Enter its correct password', 'Access is denied and no session is created (A2)', P, SAME, 'Auto: test_rbac::test_expiration_and_account_lock'),
  ('Sign in with blank account name and password', '1. Leave both fields empty\n2. Click Sign in', 'The form blocks submission and shows required-field errors', N, '', 'Manual UI check pending'),
  ('Repeated failed sign-ins are throttled', '1. Submit wrong passwords repeatedly for one account\n2. Restart the server\n3. Try again', 'Further attempts are rate-limited, also after restart', P, SAME, 'Auto: test_security_audit::test_login_throttle_persists_across_restart'),
  ('Multi-role user selects a context', '1. Sign in with an account holding patient and HCP roles\n2. Switch context to HCP', 'Only the permissions of the selected context are granted; context is stored on the server', P, SAME, 'Auto: test_auth::test_single_and_multi_role_payloads; rbac.spec "server context persists and client storage cannot escalate privileges"'),
  ('Role revoked while signed in', '1. Sign in as HCP\n2. Administrator revokes the HCP role\n3. Open an HCP page', 'Access is denied immediately (A3); no stale protected data is shown', P, SAME, 'Auto: test_rbac::test_live_revocation_invalidates_active_role; rbac.spec "live role revocation and 401 restore route protection"'),
 ]),
 ('UC-02', 'Enter and Confirm Medication Information', 'The patient enters medication information (manual, OCR image, voice or chatbot text) and confirms it before use.', LIVE, [
  ('Manual entry with catalog suggestion', '1. Open Intake > Manual\n2. Type "augmen" and choose a suggested product\n3. Enter dose and timing\n4. Confirm', 'Entry is saved as confirmed with the selected product', P, SAME, 'Auto: ocr-review.spec "manual catalog preserves second product and build through form edits"'),
  ('OCR prescription image is reviewed before confirmation', '1. Upload a prescription image\n2. Review recognized fields\n3. Edit a wrong field\n4. Confirm', 'Edited values are saved; confirmation happens only after review', P, SAME, 'Auto: ocr-review.spec "persisted OCR edits, revision and confirmation precede explicit safety requests"'),
  ('Voice input keeps an editable transcript', '1. Record a medication by voice\n2. Edit the transcript\n3. Submit', 'Reviewed transcript is submitted; invalid audio keeps the transcript editable', P, SAME, 'Auto: ocr-review.spec "Voice retains editable transcript after invalid audio and submits the reviewed transcript"'),
  ('Unclear OCR text is not treated as "nothing found"', '1. Upload an image with unsupported layout', 'System explains recognized text and marks unsupported structure (A1)', P, SAME, 'Auto: ocr-review.spec "OCR explains recognized text with unsupported structure"'),
  ('Editing a confirmed entry invalidates confirmation', '1. Confirm an entry\n2. Edit it', 'Entry returns to unconfirmed; no assessment is fabricated (A3)', P, SAME, 'Auto: workflows.spec "Core edits invalidate confirmation and do not fabricate assessments"'),
  ('Input service failure keeps user input', '1. Simulate API failure / deny microphone\n2. Submit input', 'Input is retained; no sample safety result is displayed (A2)', P, SAME, 'Auto: ocr-review.spec "API failures and denied microphone retain input and never display sample safety results"'),
  ('Spelling correction requires explicit choice', '1. Enter a misspelled medicine name\n2. Review the suggestion', 'Correction is applied only after the patient chooses it and saves', P, SAME, 'Auto: medicine-spelling.spec "spelling corrections require a choice and Save"'),
 ]),
 ('UC-03', 'Check Medication Safety', 'The patient receives supported risk findings, warnings, limitations and next steps.', LIVE, [
  ('Safety check runs only after confirmation', '1. Confirm medication entries\n2. Request a safety check', 'Assessment is created only from confirmed entries', P, SAME, 'Auto: ocr-review.spec "persisted OCR edits, revision and confirmation precede explicit safety requests"'),
  ('Drug-drug interaction is reported from DDInter', '1. Confirm two interacting medicines\n2. Run the safety check', 'Interaction finding with severity and source is shown', N, '', 'Requires local DDInter reference data (B001); pending'),
  ('Duplicate active ingredient is detected', '1. Confirm two products with the same ingredient\n2. Run the check', 'Duplicate-ingredient warning is shown', N, '', 'Requires local reference data (B001); pending'),
  ('Unknown medicine is marked Unassessed', '1. Confirm an unidentified medicine\n2. Run the check', 'Affected checks are Unassessed; the system does not claim safety (A1)', N, '', 'Requires local reference data (B001); pending'),
  ('Single medicine: pair checks are not applicable', '1. Confirm one medicine\n2. Run the check', 'DDI/duplicate checks are reported as Not applicable', P, SAME, 'Auto: test_module4_5_api (PostgreSQL) creates a completed single-medicine assessment'),
  ('Severe finding holds new reminders', '1. Have an assessment with a MAJOR finding\n2. Try to enable a reminder', 'Reminder stays on hold and HCP review is offered (A3)', P, SAME, 'Auto: reminders.spec "patient creates schedule, consents to review, activates approval"'),
 ]),
 ('UC-04', 'Arrange HCP Review', 'The patient arranges an HCP review for an assessment or a schedule with case-specific consent.', LIVE, [
  ('Create a schedule review case with consent', '1. Open Reminders\n2. Choose "Gửi chuyên gia" on a schedule\n3. Pick an HCP and tick consent\n4. Submit', 'Case is created, access granted to the chosen HCP, status OPEN', P, SAME, 'Auto: reminders.spec; test_module4_5_api (PostgreSQL)'),
  ('Submit without consent', '1. Choose an HCP\n2. Leave consent unticked\n3. Submit', 'Request is rejected; no HCP receives access (A1)', N, '', 'Manual check pending (server rule: "Explicit patient consent required")'),
  ('Choose an inactive or unknown HCP', '1. Send a case with an HCP id that is not an active provider', 'Request rejected; no access granted (A2/A4)', P, SAME, 'Auto: test_hcp_providers::test_unlinked_or_inactive_requested_provider_is_a_conflict'),
  ('Safety case needs a completed assessment', '1. Send a SAFETY case for a running/failed assessment', 'Request rejected with a clear message', P, SAME, 'Auto: test_reminder_assessment::test_safety_case_rejects_incomplete_or_missing_assessment'),
  ('Patient sees own case status', '1. Open My cases after submitting', 'Case appears with status and latest outcome', P, SAME, 'Auto: hcp-case.spec; test_module4_5_api'),
  ('Duplicate request is reused', '1. Submit the same pending proposal twice', 'Existing request is reused, no duplicate case (A3)', N, '', 'Expected to fail - see B007; manual verification pending'),
 ]),
 ('UC-05', 'Review Medication Safety Case', 'An assigned HCP reviews a shared case, messages the patient and records an outcome.', LIVE, [
  ('HCP opens assigned case', '1. Sign in as HCP\n2. Open Queue\n3. Open a case', 'Shared findings/schedule and conversation are shown', P, SAME, 'Auto: hcp-case.spec "assigned HCP records review and leaves closure to patient activation"'),
  ('HCP records APPROVED outcome', '1. Open case\n2. Choose APPROVED, add notes\n3. Save', 'Outcome saved with reviewer and time; visible to patient', P, SAME, 'Auto: hcp-case.spec; test_module4_5_api (PostgreSQL)'),
  ('HCP cannot record a second outcome', '1. Record an outcome\n2. Try to record another', 'Second outcome rejected; review form hidden', P, SAME, 'Auto: test_hcp_review::test_review_rejects_second_outcome_for_open_case'),
  ('Unassigned / revoked HCP is denied', '1. Open a case not assigned to the HCP (or after consent revoked)', 'Access denied; no demo data fallback (A5)', P, SAME, 'Auto: hcp-case.spec "denied HCP case does not fall back to demo data"'),
  ('HCP and patient exchange messages', '1. HCP sends a message\n2. Patient replies', 'Both messages appear in the same case thread (A1/A2)', P, SAME, 'Auto: test_module4_5_api (PostgreSQL)'),
  ('Assessment queue lists only SAFETY cases', '1. Open the assessment queue', 'Only SAFETY cases are listed', P, SAME, "Auto: hcp-case.spec 'assessment queue filters live cases to SAFETY'"),
 ]),
 ('UC-06', 'Set Up Medication Reminders', 'The patient creates a verified schedule and activates eligible reminders.', LIVE, [
  ('Create and confirm a schedule', '1. Reminders > New\n2. Pick a confirmed medicine\n3. Enter times 08:00, 20:00 and dose\n4. Tick confirmation and save', 'Schedule saved as PATIENT_CONFIRMED', P, SAME, 'Auto: reminders.spec; test_module4_5_api'),
  ('Enable reminder for a low-risk schedule', '1. Click "Bật nhắc" on a confirmed schedule', 'Reminder enabled (in-app)', P, SAME, 'Auto: test_reminder_assessment::test_patient_confirmed_reminder_uses_latest_assessment'),
  ('Enable reminder that needs HCP review', '1. Click "Bật nhắc" for a medicine with risky/unassessed coverage', '409 HCP_REVIEW_REQUIRED; send-to-HCP form is offered (A3/A4)', P, SAME, 'Auto: reminders.spec; test_module4_5_api'),
  ('Activate HCP-approved schedule', '1. After APPROVED outcome click "Kích hoạt lịch đã duyệt"', 'Schedule becomes HCP_VERIFIED, reminder enabled, case closed', P, SAME, 'Auto: reminders.spec "activates approval"'),
  ('Invalid time format is rejected', '1. Enter times "8:00, 25:00,"\n2. Save', 'Client validation blocks invalid HH:MM; empty tokens ignored', P, SAME, 'Auto: reminders.spec (HH:MM validation and empty tokens)'),
  ('Schedule for an outdated medicine version', '1. Edit a medicine (new version)\n2. Create schedule for the old version', 'Rejected: newest confirmed version required; one active schedule per medicine', P, SAME, 'Auto: test_schedule_creation_rejects_unconfirmed_and_stale_entries; test_duplicate_schedule_creation_locks_entry_and_rejects_without_writes'),
  ('Invalid timezone', '1. Submit timezone "Asia"', 'Validation error (422), not a server error', P, SAME, 'Auto: test_g9_boundaries::test_timezone_lookup_failure_is_validation_error'),
 ]),
 ('UC-07', 'Manage Medication Reminders', 'The patient changes notification settings or proposes timing changes.', LIVE, [
  ('Disable an enabled reminder', '1. Click "Tắt nhắc"', 'Notification disabled; schedule unchanged (A1)', P, SAME, "Auto: reminders.spec 'undecided proposal blocks enabling but still allows disabling'"),
  ('Disable stays available during a pending proposal', '1. Send schedule to HCP\n2. Click "Tắt nhắc" while undecided', 'Disable succeeds', P, SAME, "Auto: reminders.spec 'undecided proposal ... still allows disabling'"),
  ('Re-enable an HCP-approved reminder after a new assessment', '1. Disable reminder\n2. Run a new assessment\n3. Enable again', 'Reminder re-enabled using the reviewed assessment', P, SAME, 'Auto: test_reminder_assessment::test_hcp_reminder_uses_exact_reviewed_assessment_not_latest'),
  ('Propose different timing to HCP', '1. Send schedule to HCP with new time 20:00', 'Proposal stores the new timing as Pending HCP Review (A2)', N, '', 'Expected to fail - see B005 (proposal copies old timing); deferred'),
  ('Current schedule stays effective while proposal pending', '1. Send schedule to HCP\n2. Try "Bật nhắc" on the current schedule', 'Previous verified schedule remains usable (A2)', N, '', 'Expected to fail - see B006; deferred'),
  ('Cancel change keeps previous settings', '1. Open edit\n2. Cancel', 'Previous settings unchanged (A3)', N, '', 'Manual UI check pending'),
 ]),
 ('UC-08', 'Record Dose Status', 'The patient records Taken, Missed or Skipped for a scheduled dose.', LIVE, [
  ('Mark a due dose as Taken', '1. Open Today\n2. Click Taken on a due dose', 'Dose saved as TAKEN with recorded time', P, SAME, 'Auto: reminders.spec "corrects dose"; test_module4_5_api'),
  ('Correct a recorded dose', '1. Mark Taken\n2. Change to Skipped', 'Correction supersedes the earlier record (A1)', P, SAME, 'Auto: test_adherence::test_corrections_replace_original_and_skipped_remains_in_denominator'),
  ('Future dose cannot be recorded', '1. Try to record a dose scheduled later today', 'Rejected: cannot record a future dose', N, '', 'Manual check pending (server rule: "Cannot record a future dose")'),
  ('Dose outside the schedule period is rejected', '1. POST a dose time that is not an occurrence of the schedule', 'Rejected; no unsupported record created (A3)', N, '', 'Manual check pending (server rule: "outside the verified schedule effective period")'),
  ('Old due dose stays recordable', '1. Leave a morning dose unrecorded\n2. Record it in the evening', 'Dose can still be recorded; due banner not shown', P, SAME, "Auto: reminder-timing.spec 'old due doses stay recordable'"),
  ('Double click records once', '1. Click Taken twice quickly', 'Only one record is stored', N, '', 'Manual check pending (repository returns the existing record)'),
 ]),
 ('UC-09', 'View Adherence History', 'The patient reviews recorded medication use over time.', LIVE, [
  ('View 7-day adherence rate', '1. Open Dose history', 'Taken / due doses for the last 7 days are shown', P, SAME, 'Auto: test_adherence::test_seven_calendar_days_and_no_doses_before_creation_instant'),
  ('Days use the schedule timezone', '1. Schedule in Asia/Ho_Chi_Minh\n2. View history near midnight UTC', 'Doses are grouped by local day', P, SAME, 'Auto: test_adherence::test_day_is_schedule_local_not_utc'),
  ('No schedules gives empty state, not 0%', '1. New patient opens history', 'Empty state shown; rate is not reported as 0% (A1)', P, SAME, 'Auto: test_adherence::test_empty_and_unverified_are_not_zero_percent'),
  ('Grace period before counting a dose as missed', '1. Dose became due 30 minutes ago', 'Not counted against adherence yet', P, SAME, 'Auto: test_adherence::test_adherence_has_a_full_hour_grace_period'),
  ('Daylight-saving transitions', '1. Schedule across a DST gap/fold', 'Gap time skipped; fold counted once', P, SAME, 'Auto: test_adherence::test_dst_gap_is_skipped_and_fold_is_one_occurrence'),
  ('Filter by medicine', '1. Select a medicine filter', 'Only that medicine\'s doses are shown', N, '', 'Manual UI check pending'),
 ]),
 ('UC-10', 'View Medication and Safety History', 'The patient reviews saved medication records and past assessments.', PROTO, [
  ('List saved medications and assessments', '1. Open History', 'Permitted records listed with dates', N, '', 'History view is prototype; manual check pending'),
  ('Open a past assessment', '1. Select an assessment', 'Findings, limitations and HCP status shown', N, '', 'Manual check pending'),
  ('Outdated result is labelled', '1. Edit a medicine after an assessment\n2. Open the old assessment', 'Result labelled as not matching current record', N, '', 'Manual check pending'),
  ('Empty history', '1. New patient opens History', 'Empty-state message (A1)', P, SAME, 'Auto: workflows.spec "filters, local upload, profile, guard and empty dates"'),
  ('Other patient\'s record is denied', '1. Request another patient\'s record id', 'Access denied without private data (A2)', N, '', 'Manual check pending'),
 ]),
 ('UC-11', 'Ask a Medication Question', 'The patient asks the chatbot a medication question and receives a grounded answer.', LIVE, [
  ('Ask a supported question', '1. Open Chat\n2. Ask "Panadol dùng thế nào?"', 'Answer with supporting sources and limitations', P, SAME, 'Auto: ocr-review.spec "chat renders backend QA"'),
  ('Chat does not create a medication draft by itself', '1. Mention a medicine in chat', 'No medication record is created without confirmation (A4)', P, SAME, 'Auto: ocr-review.spec "does not create a local medication draft"'),
  ('Conversation resumes after reload', '1. Start a chat\n2. Reload the page', 'Server workflow and history are restored', P, SAME, "Auto: workflows.spec 'chat resumes its server workflow after navigation and reload'"),
  ('Unclear question asks follow-up', '1. Ask an ambiguous question', 'Short clarification question (A1)', N, '', 'Needs local Ollama model (NLP_RUN_REAL_OLLAMA); pending'),
  ('No reliable information', '1. Ask about an unknown medicine', 'Limitation explained, no invented claims (A3)', N, '', 'Needs local Ollama model; pending'),
  ('Clinical decision request is redirected', '1. Ask "Should I stop this medicine?"', 'Chatbot refuses to decide and points to HCP workflow (A4)', N, '', 'Needs local Ollama model; pending'),
 ]),
 ('UC-12', 'Generate Patient Health Summary', 'The patient generates and confirms a structured health summary.', PROTO, [
  ('Generate draft summary', '1. Open Summary\n2. Click Generate', 'Draft with sources, dates and gaps', N, '', 'Prototype UI; server API not exposed yet (B014)'),
  ('Incomplete information marked', '1. Generate with missing allergies', 'Gaps listed; limited draft (A1)', N, '', 'Prototype; pending'),
  ('Correct draft before confirmation', '1. Edit a field\n2. Re-review', 'Draft updated (A2)', N, '', 'Prototype; pending'),
  ('Confirm and save summary', '1. Confirm draft', 'Summary saved for later viewing', N, '', 'Prototype; pending'),
  ('Cancel keeps no new summary', '1. Cancel at confirmation', 'No new summary saved (A3)', N, '', 'Prototype; pending'),
 ]),
 ('UC-13', 'Share Patient Health Summary with HCP', 'The patient shares a confirmed summary with an authorized HCP and may revoke it.', PROTO, [
  ('Share summary with HCP', '1. Select summary\n2. Choose HCP and sections\n3. Confirm permission', 'Only selected sections become visible to that HCP', P, SAME, 'Auto (prototype UI): figma-flows.spec "patient can create and revoke local sharing"'),
  ('Revoke sharing', '1. Click Revoke on an active share', 'Access withdrawn', P, SAME, 'Auto (prototype UI): figma-flows.spec "... revoke local sharing"'),
  ('Decline permission', '1. Cancel at permission step', 'No access granted (A1)', N, '', 'Manual check pending'),
  ('Unauthorized recipient', '1. Choose an account without HCP role', 'Sharing denied (A2)', N, '', 'Server API not exposed yet (B014)'),
  ('Unconfirmed summary cannot be shared', '1. Try to share a draft', 'Sharing blocked (A3)', N, '', 'Server API not exposed yet (B014)'),
 ]),
 ('UC-14', 'Review Medication Reference Data', 'The Dataset Reviewer records a traceable data-quality decision.', PROTO, [
  ('Record a decision with reason', '1. Sign in as reviewer\n2. Open a record\n3. Choose Needs Correction + reason\n4. Save', 'Decision saved and listed in history', P, SAME, 'Auto (prototype UI): figma-flows.spec "reviewer records a decision with a reason and finds it in history"'),
  ('Reviewer edits catalog data', '1. Edit a catalog field\n2. Save', 'Change stored with reviewer identity', P, SAME, 'Auto: workflows.spec "reviewer edits catalog data"'),
  ('Decision without reason', '1. Choose Reject without reason', 'Validation error', N, '', 'Manual check pending'),
  ('Non-reviewer is denied', '1. Patient opens /reviewer/queue', 'Access denied', P, SAME, 'Auto: test_rbac::test_all_role_permission_matrix'),
  ('Record changed during review', '1. Two reviewers edit the same record', 'Reload requested (A2)', N, '', 'Manual check pending'),
 ]),
 ('UC-15', 'Manage User Accounts and Roles', 'The Administrator manages accounts and role assignments.', LIVE, [
  ('Grant a role to a user', '1. Admin > Users\n2. Grant HCP role\n3. Confirm', 'Role granted and recorded in audit log', P, SAME, 'Auto: test_rbac::test_grant_revoke_and_restart_preserves_changes'),
  ('Revoke a role', '1. Revoke a granted role', 'Role removed; active sessions lose it', P, SAME, 'Auto: test_rbac::test_live_revocation_invalidates_active_role'),
  ('Cannot remove the last administrator', '1. Revoke admin role from the only admin', 'Request rejected (A5)', P, SAME, 'Auto: test_rbac::test_privilege_escalation_catalog_and_last_admin'),
  ('Non-admin cannot call admin API', '1. Patient calls /api/admin/users', '403 Forbidden', P, SAME, 'Auto: test_auth::test_admin_guard; test_security_audit::test_full_endpoint_matrix'),
  ('View audit history', '1. Admin opens Audit', 'Events with actor and time listed', P, SAME, 'Auto: test_rbac::test_audit_actor_labels_and_read_permissions_preserve_stored_events'),
  ('Concurrent grants keep one row', '1. Grant the same role twice concurrently', 'Only one grant stored', P, SAME, 'Auto: test_security_audit::test_concurrent_grants_keep_one_row_and_last_admin'),
 ]),
 ('UC-16', 'Report Technical Issue', 'A registered user reports a technical problem and receives a ticket.', PROTO, [
  ('Create a ticket', '1. Support > Report issue\n2. Enter title and description\n3. Submit', 'Ticket id and initial status shown', P, SAME, 'Auto (prototype UI): figma-flows.spec "support creates a ticket"'),
  ('Missing required fields', '1. Submit empty form', 'Missing fields highlighted (A1)', N, '', 'Manual check pending'),
  ('Attachment with patient data', '1. Attach a file containing patient data', 'Masking requested (A2)', N, '', 'Not implemented in prototype'),
  ('Cancel submission', '1. Cancel', 'No ticket created (A3)', N, '', 'Manual check pending'),
  ('Ticket persisted on server', '1. Create ticket\n2. Sign in from another browser', 'Ticket visible', N, '', 'Server API not exposed yet (B014)'),
 ]),
 ('UC-17', 'Handle Technical Support Request', 'Technical Support updates ticket status and records a resolution.', PROTO, [
  ('Save response and status', '1. Support opens a ticket\n2. Write response, set Resolved', 'Status and response saved', P, SAME, 'Auto (prototype UI): figma-flows.spec "saves its response and status"'),
  ('Request more information', '1. Mark Pending User Response', 'Status updated (A1)', N, '', 'Manual check pending'),
  ('Unresolved ticket stays open', '1. Save progress note only', 'Ticket remains In Progress (A2)', N, '', 'Manual check pending'),
  ('Support cannot see medical data', '1. Support opens a ticket with medical content', 'Medical content restricted (A3)', P, SAME, 'Auto: test_rbac::test_all_role_permission_matrix (support has no patient permissions)'),
  ('Unauthorized staff denied', '1. Patient opens support queue', 'Access denied (A4)', P, SAME, 'Auto: rbac.spec route protection'),
 ]),
 ('UC-18', 'Manage Patient Health Profile', 'The patient manages conditions, allergies and other health information.', PROTO, [
  ('Update profile fields', '1. Open Profile\n2. Add an allergy\n3. Save', 'Information saved and shown', P, SAME, 'Auto (prototype UI): workflows.spec "filters, local upload, profile, guard and empty dates"'),
  ('Profile completion reminder', '1. Sign in with an incomplete profile', 'Reminder dialog offers to fill or snooze 7 days', P, SAME, 'Auto: figma-flows.spec (snoozes the profile reminder during sign-in)'),
  ('Invalid value', '1. Enter an invalid birth year', 'Error highlighted (A2)', N, '', 'Manual check pending'),
  ('Unknown value', '1. Enter "Chưa rõ"', 'Stored as patient-reported/uncertain (A3)', N, '', 'Manual check pending'),
  ('Cancel edit', '1. Cancel', 'No change applied (A4)', N, '', 'Manual check pending'),
 ]),
 ('UC-19', 'Manage Personal Medication Cabinet', 'Reserved for future development.', FUTURE, [
  ('Add a cabinet item', '1. Open Cabinet\n2. Add medicine', 'Item saved', N, '', 'Out of scope (UC-19 reserved for future development)'),
  ('View expiring medicines', '1. Open expiring list', 'Expiring items shown', N, '', 'Out of scope'),
  ('Update usage status', '1. Mark as discontinued', 'Status updated', N, '', 'Out of scope'),
  ('Missing required field', '1. Save without name', 'Validation error', N, '', 'Out of scope'),
  ('Separate boxes stay separate', '1. Add the same medicine twice with different expiry', 'Two items stored', N, '', 'Out of scope (DB layer exists; test blocked by B001)'),
 ]),
 ('UC-20', 'Manage Personal Account', 'A registered user views or updates account details and password.', PROTO, [
  ('View personal account', '1. Open Account', 'Own account details shown (A1)', P, SAME, 'Auto: test_auth::test_login_me_and_logout (/api/auth/me)'),
  ('Cannot read another user\'s account', '1. Request /api/auth/accounts/{other id}', 'Access denied', P, SAME, 'Auto: test_rbac::test_cookie_rotation_expiration_logout_and_owner'),
  ('Update display name', '1. Edit name\n2. Confirm', 'Name saved', N, '', 'Server API not exposed yet (B014)'),
  ('Change password with wrong current password', '1. Enter wrong current password', 'Error, password unchanged (A4)', N, '', 'Server API not exposed yet (B014)'),
  ('Logout ends the session', '1. Click Logout\n2. Press Back', 'Protected pages require sign-in again', P, SAME, 'Auto: test_rbac::test_cookie_rotation_expiration_logout_and_owner; rbac.spec "expired admin session shows login"'),
 ]),
]


def style_like(dst, src):
    dst.font, dst.border, dst.fill = copy(src.font), copy(src.border), copy(src.fill)
    dst.alignment, dst.number_format = copy(src.alignment), src.number_format


def main():
    wb = openpyxl.load_workbook(TEMPLATE)
    feat, cases = wb['Features'], wb['Test cases']
    # Features sheet
    feat['A1'] = 'Project: Medication Safety Assistant'
    feat['A2'] = 'Team: Group 02'
    proto = [feat.cell(6, c) for c in range(1, 5)]
    feat.delete_rows(6, feat.max_row)
    for i, (uid, name, desc, level, _) in enumerate(UC):
        for c, v in enumerate((uid, name, desc, level), 1):
            cell = feat.cell(6 + i, c, v)
            style_like(cell, proto[c - 1])
            cell.alignment = copy(cell.alignment) if cell.alignment else None
    feat.column_dimensions['A'].width = 8
    # Test cases sheet
    head = cases.cell(2, 1)
    body = [cases.cell(3, c) for c in range(1, 11)]
    head_style = [cases.cell(2, c) for c in range(1, 11)]
    cases.delete_rows(2, cases.max_row)
    r = 2
    for n, (uid, name, _, _, rows) in enumerate(UC, 1):
        for c in range(1, 11):
            style_like(cases.cell(r, c), head_style[c - 1])
        cases.cell(r, 1, f'Function {n:02d}: {name}')
        r += 1
        for k, (title, steps, er, status, actual, remark) in enumerate(rows, 1):
            values = (uid, f'TC{n:02d}-{k:02d}', title, steps, er, actual, status,
                      TESTER if status == P else '', DATE if status == P else None, remark)
            for c, v in enumerate(values, 1):
                cell = cases.cell(r, c, v)
                style_like(cell, body[c - 1])
                cell.alignment = openpyxl.styles.Alignment(wrap_text=True, vertical='top')
            cases.cell(r, 9).number_format = 'yyyy-mm-dd'
            r += 1
    cases.column_dimensions['J'].width = 45
    cases.column_dimensions['B'].width = 10
    wb.save(OUT)
    total = sum(len(u[4]) for u in UC)
    passed = sum(1 for u in UC for row in u[4] if row[3] == P)
    print(f'{OUT.name}: {len(UC)} use cases, {total} test cases, {passed} pass, {total - passed} not run')
    assert all(len(u[4]) >= 5 for u in UC)


if __name__ == '__main__':
    main()
