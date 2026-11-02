# Specification trace — UC-01 to UC-18

Các nội dung dưới đây được giữ để đối chiếu với đặc tả đã cung cấp; không hiển thị thành hộp chú thích trên sơ đồ. A1…An trong từng file PlantUML tương ứng các mục bên dưới. Mũi tên include/extend không thay thế luồng điều khiển; vị trí tiếp tục được ghi trong tên chức năng và tại đây.

Registered User ở UC-01 và UC-17 bao gồm Patient / General User, HCP, Dataset Reviewer, Administrator và Technical Support.

## UC-01: Sign In

Pre-conditions:

Registered account; sign-in page accessible.

Basic Flow:

1. User enters account name and password.
2. System checks credentials and account status.
3. System verifies assigned role and permissions.
4. System creates an authenticated session and opens the permitted dashboard.

Alternative Flows:

A1 (step 2): Incorrect credentials.
Show an error; create no session.
User retries from step 1 or cancels.

A2 (step 2): Inactive or blocked account.
Deny sign-in; advise contacting support.
End without a session.

A3 (step 3): Role information unavailable.
Deny sign-in; no unrestricted session.
End with an access error.

Post-conditions:

Success: Session with verified role permissions.
Failure: No authenticated session.

## UC-02: Enter and Confirm Medication Information

Pre-conditions:

Signed in; medication entry accessible.

Basic Flow:

1. Patient provides OCR, chatbot text, voice or manual input.
2. System processes input and identifies the requested task when needed.
3. System shows recorded details for review.
4. Patient corrects errors and confirms details match the source.
5. System saves confirmed information; missing fields remain marked.

Alternative Flows:

A1 (step 2): Ask clarification or offer a function to select.
If clarified, return to step 2; otherwise end.

A2 (step 2): Show processing error; offer retry or another method.
If retrying, return to step 1; otherwise end.

A3 (step 3): Mark missing or unclear fields.
Patient corrects when possible, then continues to step 4.
Remaining gaps stay incomplete.

A4 (step 4): Patient does not confirm.
Do not release input for safety checks or reminder activation.
End without confirmation.

Post-conditions:

Confirmed input saved with remaining gaps.
Confirmation does not prove identity or safety.
Unconfirmed input is not released.

## UC-03: Check Medication Safety

Pre-conditions:

Signed in; at least one confirmed medication record.

Basic Flow:

1. Patient requests a check of confirmed medication information.
2. System attempts medicine and ingredient identification.
3. System performs supported interaction and duplicate-ingredient checks.
4. Record risk levels and supported or missing check statuses.
5. Show affected medicines, explanations, warnings, limits and next steps.
A no-issue statement covers completed checks only.
6. Save assessment, status and time.

Alternative Flows:

A1 (step 2): Medicine cannot be identified.
Mark unresolved; do not guess ingredients.
Perform assessable checks only, or report unassessed at step 4.

A2 (step 3): Required interaction data missing.
Mark affected check unassessed; perform independent supported checks.
Continue at step 4 with limitation.

A3 (step 3): Record and immediately show severe warning.
Recommend prompt HCP review.
Hold activation of new reminders for affected medicines only.
Existing reminders and prescriptions are unchanged.
Continue at step 4 for remaining supported checks.

A4 (step 3): Fewer than two identified medicines.
If only one was supplied, pairwise checks are not applicable.
If others are unresolved, related checks remain unassessed.
Continue at step 4.

A5 (steps 2-4): Assessment fails.
Report failed or incomplete, never safe.
Preserve any severe warning and reminder restriction already found.
Patient may retry step 1 or end.

Post-conditions:

Assessed, partially assessed or unassessed result saved.
Findings and limits retained; severe warnings activate safety gate.
No failed or unassessed check is presented as safe.

## UC-04: Request HCP Review

Pre-conditions:

Signed in; saved safety case exists.
Sharing permission is obtained during this UC.

Basic Flow:

1. Select a saved safety case and request HCP review.
2. Show case, findings, missing details and information to share.
3. Patient reviews information and grants permission.
4. Create Pending request; restrict access to authorized HCP accounts.
5. Show request status.

Alternative Flows:

A1 (step 3): Patient declines sharing.
Create no request or new access; end.

A2 (step 2): Case incomplete.
Highlight missing or unresolved details.
If minimum case information exists, patient may share a clearly limited case.
Otherwise patient may end to update it.

A3 (step 4): No reviewer available.
Request stays Pending and unassigned.
Continue at step 5; do not claim reviewed.

A4 (step 4): Active request already exists.
Do not duplicate; show existing request and status.
No additional information shared without permission; end.

A5 (step 4): Request cannot be saved.
Report failure; grant no new access.
Patient retries step 4 or ends.

Post-conditions:

New Pending or existing active request linked to case.
Only permitted HCP accounts access shared information.
Failure grants no new access; warnings and gates remain.

## UC-05: Review Medication Safety Case

Pre-conditions:

HCP signed in and authorized for request;
case shared with patient permission.

Basic Flow:

1. HCP selects an accessible queued case awaiting a decision.
2. Show patient-approved details, findings, warnings, limits and conversation.
3. HCP selects supported outcome with comments as needed.
4. Validate and record reviewer, time, outcome and reply.
5. Update case status; recheck affected pending reminders only when
an eligible schedule confirmation is recorded.
6. Show outcome, reply and status to patient and HCP.

Alternative Flows:

A1 (step 3): HCP specifies missing details in the conversation.
Mark Awaiting Patient Response.
Patient submits details in the SAME thread.
Mark Pending HCP Response and return to HCP queue.
When HCP reopens, resume at step 2.

A2 (after step 6): Patient submits a follow-up in the existing conversation.
Append to SAME thread; mark Pending HCP Response.
Return case to HCP queue.
Show chronological reply thread and new-patient-reply indication.
HCP reopens and continues from step 2.

A3 (step 3): HCP selects Unresolved and records reason.
Continue at step 4; required reminder holds remain.

A4 (step 5): No valid schedule confirmation.
Affected new reminders stay Pending; prescribed timing unchanged.
Continue at step 6 with restriction displayed.

A5 (steps 1 or 4): Unauthorized or changed case, or save fails.
Deny or stop action and report issue.
No unrecorded decision or reply counts as approval.

Post-conditions:

Traceable simulated outcome, information request or reply recorded.
Follow-up returns case to permitted HCP queue.
Only eligible recorded confirmation affects pending new reminders.
Failure changes no access, prescriptions or reminder restrictions.

## UC-06: Set Up Medication Reminders

Pre-conditions:

Signed in; medication record has instructions that can be verified.

Basic Flow:

1. Select medication with existing prescription or recorded HCP instructions.
2. Display recorded schedule, source and safety status.
3. Patient confirms schedule matches existing instructions.
4. Check schedule verification, recorded warnings and new-reminder safety gate.
5. Activate eligible reminders and display status.

Alternative Flows:

A1 (steps 2-3): Schedule missing or unverified.
Do not activate without a verified schedule.
Patient may correct information or end.

A2 (step 3): Patient proposes new timing.
Record Pending HCP Review.
Do not activate proposed schedule before required simulated confirmation.

A3 (step 4): Severe interaction affects medicine.
Keep affected NEW reminders Pending HCP Review.
Other eligible reminders may activate.
Existing reminders are not stopped automatically.

A4 (step 4): Safety check unavailable.
Report Unassessed rather than safe clearance.
Restrict reminder when review policy requires confirmation.

A5 (step 5): Browser notifications unavailable.
Report limitation; show eligible schedules in application.

Post-conditions:

Eligible new reminders active; restricted ones Pending with reason.
No unverified or blocked new reminder activated.
Prescriptions and existing reminders unchanged.

## UC-07: Manage Medication Reminders

Pre-conditions:

Signed in; patient owns an existing reminder.

Basic Flow:

1. Open an owned reminder and choose management.
2. Show schedule, source and notification settings.
3. Request notification change or schedule update.
4. Validate against verified instructions and safety rules.
5. Patient confirms request.
6. Save allowed setting or timing proposal as Pending HCP Review.

Alternative Flows:

A1 (step 3): Prepare to disable selected notification only.
Continue at step 5 for confirmation.
Medication instructions remain unchanged.

A2 (step 4): Proposed timing differs from verified instructions.
Mark as requiring HCP review; continue at step 5.
Existing schedule remains unchanged.

A3 (steps 5-6): Patient cancels or update fails.
Keep previous settings; report error when relevant.

Post-conditions:

Allowed setting saved or timing proposal Pending review.
Failure preserves prior settings, except an explicitly disabled notification.

## UC-08: Record Dose Status

Pre-conditions:

Signed in; accessible scheduled dose or adherence entry.

Basic Flow:

1. Select scheduled dose from reminder or adherence view.
2. Show medicine, scheduled time and current status.
3. Select Taken, Missed or Skipped.
4. Confirm entry.
5. Save dose status and recorded time.

Alternative Flows:

A1 (step 3): Show previous status for comparison.
Patient confirms correction; continue at step 5.

A2 (step 4): Patient cancels.
Keep previous entry and end.

A3 (steps 2 or 5): Dose event unavailable or save fails.
Explain entry cannot be saved.
Create no unsupported dose record.

Post-conditions:

Confirmed status saved and available in adherence history.
Failure changes no dose entry; no treatment recommendation.

## UC-09: View Adherence History

Pre-conditions:

Signed in; permitted to view own adherence records.

Basic Flow:

1. Open Adherence History.
2. Show available scheduled doses and recorded statuses.
3. Select a medicine or time period.
4. Show matching Taken, Missed and Skipped records with dates.

Alternative Flows:

A1 (step 4): No matching entries.
Show empty result; allow another filter.

A2 (step 2): History incomplete or unavailable.
Show available records and identify unavailable periods.

Post-conditions:

Permitted history shown without modification.
Failure changes no record.

## UC-10: View Medication and Safety History

Pre-conditions:

Signed in; permitted to view own records.

Basic Flow:

1. Open Medication and Safety History.
2. List permitted medication records and past assessments.
3. Select a record or assessment.
4. Show date, findings, limitations and linked HCP review status.
5. Clearly label results no longer matching the current medication record.

Alternative Flows:

A1 (step 2): No history available.
Show empty-state message and end.

A2 (step 3): Record unavailable or access denied.
Report limitation without exposing private data.
Patient may select another permitted record.

Post-conditions:

Historical information displayed; stored data unchanged.
Failure changes no record or treatment.

## UC-11: Ask a Medication Question

Pre-conditions:

Signed in; chatbot available.

Basic Flow:

1. Patient asks a medication question in text or voice.
2. Identify request and relevant authorized context.
3. Consult supported references and permitted patient records.
4. Answer with explanations and limits or ask a needed follow-up.
5. Patient may ask another question or open a supported feature.

Alternative Flows:

A1 (step 2): Ask a short follow-up.
If clarified, return to step 2; otherwise end.

A2 (step 3): Reliable information unavailable.
Explain the limit; do not invent medical claims.
End or patient asks another question.

A3 (step 2): Outside scope or suggests urgent danger.
No diagnosis, prescribing, treatment change or unvalidated emergency instructions.
Warn to seek qualified or emergency help.

A4 (step 5): Request would modify records.
Open the relevant separate confirmation use case.
Do not modify data from an unconfirmed chatbot message.

Post-conditions:

Supported answer, clarification or limitation provided.
No unsupported clinical decision or unconfirmed record change.

## UC-12: Generate Patient Health Summary

Pre-conditions:

Signed in; at least one permitted record or reported health detail.

Basic Flow:

1. Request Patient Health Summary.
2. Gather permitted medication records, reported details and available assessments.
3. Generate dated draft with known information gaps.
4. Patient reviews draft and corrects inaccurate reported details.
5. Patient confirms; save summary without automatically sharing.

Alternative Flows:

A1 (step 2): Information missing.
Label unavailable items; prepare limited draft only.
Continue at step 3.

A2 (step 4): Patient edits supported fields or corrects source records.
Update draft and return to step 4.

A3 (step 5): Patient cancels or save fails.
No new confirmed summary saved or shared.
Patient may retry after a save failure.

Post-conditions:

Reviewed summary stored for later viewing or optional sharing.
Summary is not a diagnosis; no unconfirmed summary shared.

## UC-13: Share Patient Health Summary with HCP

Pre-conditions:

Signed in; saved reviewed summary;
authorized target can be selected.

Basic Flow:

1. Select saved summary and Share with HCP.
2. Show summary and intended authorized recipient or case.
3. Patient reviews scope and confirms permission.
4. Grant access only to selected summary for that recipient or case.
5. Show sharing status.

Alternative Flows:

A1 (step 3): Patient declines permission.
Grant no new access; end.

A2 (step 4): Recipient or case unauthorized.
Deny sharing; request authorized choice.
Return to step 2 or cancel.

A3 (step 2): Summary outdated.
Warn about date or missing information.
Patient may share with limits visible or return to Generate Patient Health Summary.

A4 (step 4): Sharing fails.
Report error; do not claim success or create unintended access.

Post-conditions:

Only chosen summary accessible to permitted recipient or case.
Failure grants no new access.

## UC-14: Review Medication Dataset Record

Pre-conditions:

Dataset Reviewer signed in and permitted to review record.

Basic Flow:

1. Reviewer opens permitted list and selects medication record.
2. Show names, ingredients, mappings, source references and status.
3. Compare record with evidence.
4. Choose Accept, Reject or Needs Correction; enter reason.
5. Validate required details; save decision, reviewer, time and evidence.
6. Update dataset review status.

Alternative Flows:

A1 (steps 2-4): Source evidence missing.
Select Needs Correction or Reject; state missing evidence.
Do not mark clinically validated.

A2 (step 3): Inconsistent mapping found.
Record issue; choose Reject or Needs Correction.
Continue at step 5.

A3 (step 5): Record changed during review.
Ask reviewer to reload latest version before deciding.
Return to step 2.

A4 (steps 4-5): Reviewer cancels or save fails.
Save no new decision; retain previous status.

Post-conditions:

Source-linked quality decision and change history recorded.
No independent clinical validation claimed.
Failure saves no new decision.

## UC-15: Manage User Accounts and Roles

Pre-conditions:

Administrator signed in with account and role-management permission.

Basic Flow:

1. Open account management; select existing account or Create Account.
2. Show account fields, status and permitted role options.
3. Enter account details, status change or role assignment.
4. Validate against account and RBAC rules.
5. Administrator confirms proposed change.
6. Save authorized change and administrative activity.

Alternative Flows:

A1 (step 4): Invalid required data or duplicate account.
Explain problem and request correction.
Return to step 3 or end if canceled.

A2 (step 4): Action or role change not permitted.
Deny request without granting extra permissions.
End or select a valid action.

A3 (steps 5-6): Administrator cancels or save fails.
Keep previous account and role settings.
Report save error when relevant.

Post-conditions:

Permitted change stored with activity record.
No unauthorized change saved.

## UC-16: View Administrative Activity History

Pre-conditions:

Administrator signed in; permitted to view audit metadata.

Basic Flow:

1. Open Administrative Activity History.
2. Show permitted activity records and dates.
3. Filter by date, account or action type.
4. Show matching events and responsible accounts without restricted patient content.

Alternative Flows:

A1 (step 4): No matching records.
Show empty result; allow a different filter.

A2 (step 2): History service unavailable.
Report error; do not invent activity records.

Post-conditions:

Permitted history displayed without modifying records.
No audit or patient data changed.

## UC-17: Report Technical Issue

Pre-conditions:

Signed in; technical support feature accessible.

Basic Flow:

1. Open Report Technical Issue.
2. Show required fields and optional diagnostic details.
3. User describes problem and reviews attachments.
4. User submits report.
5. Save ticket; display identifier and status.

Alternative Flows:

A1 (step 4): Required information missing.
Highlight missing fields; return to step 3.

A2 (step 3): Attachment contains unnecessary patient information.
Request removal or masking before submission.
Return to step 3.

A3 (steps 4-5): User cancels or ticket creation fails.
Do not report successful submission.
User retries after error or ends.

Post-conditions:

Ticket stored and identifier shown without unnecessary patient data.
Failure creates no ticket.

## UC-18: Handle Technical Support Request

Pre-conditions:

Support signed in; permitted to access selected ticket.

Basic Flow:

1. Support selects a ticket from permitted queue.
2. Show description, status and allowed technical details.
3. Investigate and record relevant notes.
4. Record resolution or update status.
5. Save action, time and responsible account;
show updated status to reporting user.

Alternative Flows:

A1 (step 3): Request necessary technical details only.
Set Pending User Response; current use case ends.

A2 (step 4): Issue unresolved.
Record progress; keep ticket Open or In Progress.
Continue at step 5.

A3 (step 2): Unauthorized patient data present.
Restrict medical-content access.
Support uses permitted technical details only.

A4 (steps 1 or 5): Access denied or save fails.
Deny action or report error.
Record no unsupported resolution.

Post-conditions:

Ticket status and troubleshooting history saved; reporter sees status.
Failure creates no unsupported update or patient-data access.
