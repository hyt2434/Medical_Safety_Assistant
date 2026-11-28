# Handoff: Module 4 (Patient ↔ HCP) + Module 5 (Medication reminders) — MVP

Branch: `feature/module4-hcp-module5-reminders` (from `dev` @ `eb64ca7a`). Deadline: 28/11 12:00.
Goal: real backend API + wire existing UI, enough to demo one end-to-end flow. Do NOT redesign DB.

## 0. Goals & checkpoints (work strictly in order)
Rules:
- One goal at a time. When its "Done" check passes: commit with prefix `[G#]`, then update this table (☑ + short hash + notes) **in the same commit**.
- New session? Read this table first and continue from the first ☐ goal.
- Do not edit DB migrations. Do not weaken or edit existing tests to make them pass.
- Blocked > 20 min on a goal: write the reason in Notes, mark ⚠, move to the next goal.
- Minimum viable demo = G1–G3 + G5. G4, G6, G7 are stretch.

| Goal | Scope | Done when | Status | Commit | Notes |
|---|---|---|---|---|---|
| G1 | M5 pure functions: today's occurrences from `times`+timezone, merge dose records, adherence % | `pytest tests/unit/module5 -q` passes | ☑ | 656133f0 | 18 Module 5 tests pass, including activation and pending-revision regressions; timezone, DST, corrections and historical schedules. |
| G2 | M5 service + routes `/entries`, `/schedules` (POST/GET), `/today`, `/doses`, `/adherence`; register router | `python -c "import apps.backend.api.app"` OK; G1 tests still pass | ☑ | 923822ca | App import and 10 G1 tests pass; includes reminder gating/activation service. |
| G3 | M4 service + routes `/providers`, `POST /cases`, `/cases/mine`, `/cases` (queue), `/cases/{id}`, `/messages`; register router | app imports OK; `pytest tests/backend -q` no new failures | ☑ | 27a74741 | Consent-scoped cases/messages; full Python run has no new failures. |
| G4 | M4 review records outcome; patient M5 activation closes case and enables reminders | app imports OK; manual curl/TestClient of the flow, or integration test skeleton | ☑ | b6cfdc92 | HCP writes only outcome; patient activation atomically confirms/enables/closes. Pending revisions preserve verified ancestor doses until verification. 26 targeted Python tests pass; 3 browser tests pass; PostgreSQL integration skips without DSN. No DB migration changes. |
| G5 | Frontend `api.ts` helpers; `Reminders` + `DoseHistory` use API (demo fallback) | `npm run build` OK; existing Playwright specs still pass | ☑ | e6672693 | Revalidated without G4 draft: production build passes; 37 Playwright pass / 1 skip. Existing specs unchanged; explicit server preview preserves existing flows. |
| G6 | Frontend `HcpQueue` + `HcpCase` use API; patient "send to HCP" (provider picker + consent) | `npm run build` OK | ☑ | ba157962 | Revalidated in the G5 production build and 37-pass browser suite: live queue/detail, consent picker, and denied-access behavior. Review records the HCP outcome; patient activation closes the case. Mocked browser tests are UI contracts only. |
| G7 | `tests/integration/test_module4_5_api.py` (skip without `MODULE2_TEST_DSN`), `hcp-case.spec.ts`, `reminders.spec.ts` | baseline holds (pytest ≥558 pass, Playwright ≥34 pass) + new tests pass/skip cleanly | ☑ | 7c3ec4e6 | Clean-source rerun: Python 568 pass / 8 existing failures / 85 existing errors; no new failing names. Build passes; Playwright 37 pass / 1 skip. PostgreSQL skeleton skips without DSN. G4-fix2 targeted checks: 26 Python pass / 1 integration skip; 3 browser pass. Previous full-suite counts retained above. |
| G8-A | Reviewed-schedule activation and retained schedule/proposal listing | 24 unit / 3 browser / 1 real DB checks pass | ☑ | 73a9ac47 | Reject superseded activation; retain verified ancestor with pending review/resend UI; use completed assessment from the reviewed case. |
| G8-B | Verified occurrence bounds and duplicate schedule prevention | 34 unit / 1 real DB checks pass | ☑ | 608d4f0f | Skip pre-verification doses; validate exact effective-period occurrences before writes; serialize and reject duplicate active schedules (409). |
| G8-C | Core transaction boundary, structured errors, SAFETY queue and assessment checks | Full requested validation completed | ☑ | 844a0dc5 | 609 Python pass; same 8 failures / 85 errors, no new failing names. Real PostgreSQL 2 pass. Build passes; Playwright 40 pass / 1 skip. Domain helper nests without relaxing Core. |
| G9 | Timezone validation, pending-proposal controls, and configuration errors | All four requested checks completed | ☑ | d389664f | 13 new backend checks pass; Python 622 pass with the same 8 failures / 85 errors (no new failing names). PostgreSQL 2 pass; build passes; Playwright 40 pass / 1 skip. Pending toggle disabled; review-required opens proposal send form; config failures return 503. HCP browser tests await context switch before navigation. |
| G10 | Final M4/M5: undecided proposals, disable controls, single review outcome, client time validation | All four requested checks completed | ☑ | [G10] (this commit) | 46 focused Python pass. Full Python 626 pass with the same 8 failures / 85 errors; PostgreSQL 2 pass; build passes; Playwright 41 pass / 1 skip. Reviewed proposals remain visible separately; disabling remains available. Duplicate outcomes rejected under a case lock; form hidden after review. Times trimmed, empty tokens removed, HH:MM checked. Final M4/M5 commit; stop further changes. |
| G11-A | **Re-model schedule proposals (root cause of repeated review findings).** A SCHEDULE case must create a *standalone* draft `save_schedule(entry, details, tz, origin='PROPOSED_CHANGE')` with **no `supersedes`** (schema allows it), so the current schedule stays usable (toggle reminders, doses) while under review. `CaseRequest` accepts `times`, `dose_raw`, `timezone` (default = current schedule). Current schedule of a medication = verified schedule with latest `verified_at` per `item_id`. `activate(proposal)`: confirm HCP_VERIFIED → disable old schedule's reminder → enable proposal's reminder → close case (patient owner). Reject a new case while the medication has an undecided proposal; after REJECTED/CHANGES_REQUESTED allow resending with new times. Rework `verified_schedule_periods` / `current_schedule_listing` / `occurrences` by `item_id` + `verified_at` (old schedule effective until the activated proposal's `verified_at`), not supersede chains. UI (`PersistentCare.tsx`): send form has times/dose fields; list current schedule + proposals with decision; "Kích hoạt" only when APPROVED. | Unit + DB test of: send → pending (old still toggles) → REJECTED → resend with new time → APPROVED → activate → old reminder off, new on, today/adherence use new times; `run_m45_db_tests.py` passes | ☐ | | |
| G11-B | Re-enabling a reminder on an HCP_VERIFIED schedule uses the reviewed case's assessment (`verification_evidence.review_outcome_id` → case → `safety_assessment_id`) if still COMPLETED and covering the entry; only PATIENT_CONFIRMED schedules use `latest_assessment`. | Test: approved risky schedule, new assessment, disable → enable succeeds | ☐ | | |
| G11-C | `ReminderService.create`: entry must be confirmed and the newest version of its item; duplicate active schedule check by `item_id` (409). | Tests for unconfirmed, stale version, second version of same item | ☐ | | |
| G11-D | Nits: due banner only for doses due within the last 60 min; adherence ignores doses less than 60 min overdue; `providers()` validates identities with one `id = ANY(%s)` query and `create` checks only the requested `hcp_id`; add `DomainConflict(ValueError)` and map only it to 409 (other ValueError → 500). | pytest, `npm run build`, Playwright ≥ previous counts | ☐ | | |

## 1. What already exists (reuse, don't rewrite)
- **Persistence**: `src/shared/db/domain_repository.py` → `DomainRepository(conn, authenticated_actor=UUID, permissions=[...])`
  - M4: `create_case(kind, assessment=, schedule=)`, `grant_case_access(case, hcp, consent)`, `assign_case(case, hcp)`, `case_message(case, text)`, `record_review(case, decision, evidence, notes=)`, `revoke_access(grant)`.
  - M5: `save_schedule(entry_version, details, tz, origin=, supersedes=)`, `confirm_schedule(schedule, digest, uuid4(), explicit_confirmation=True, review_outcome=)`, `set_reminder(schedule, enabled=, preferences=, assessment=)`, `record_dose(schedule, scheduled_for, status, supersedes=)`.
  - Base `CoreRepository` (`src/shared/db/repository.py`) has `_one/_all/_owned/_insert`, `transaction()` sets actor/permissions session vars (needed by RLS + triggers). Wrap reads in an actor-scoped transaction. Domain services compose through `repo.domain_transaction()`; `repo.transaction()` and inherited Core operations retain the strict outer-transaction guard.
- **Reference flow that works end-to-end**: `tests/integration/test_system_persistence.py::test_real_persistence_hcp_schedule_reminder_doses...` — copy its call order.
- **Schema/rules**: `db/migrations/003_system_domains.sql`, `004_domain_access_and_audit.sql` (guard function `msa.system_domain_guard`, `msa.can_access_case`).
- **RBAC** (`src/shared/auth/rbac.py`): patient → `patient.workspace`; hcp → `clinical.case_review`.
- **Route pattern**: `apps/backend/api/routes/intake.py` (`require_permission`, `core_owner(session['account']['id'])`, `psycopg.connect(core_database_dsn(), autocommit=True)`, 403/404/409/503 mapping, `audit(...)`). Register routers in `apps/backend/api/app.py`.
- Auth account `user_id` == Core `identity.users.id` (same UUID). HCP list: query Auth DB (`shared.auth.models` User/UserRole/Role where role_code='hcp', not revoked) and keep only ids present in `identity.users`.

## 2. DB rules you must respect (enforced by triggers)
- Evidence JSON: `{'schema': 'consent.v1' | 'review-evidence.v1', 'sources': [{'locator': '<non-empty>', 'sha256': '<64 hex>'}]}` → build locator like `msa://consent/<case_id>` and sha256 of the consent/review text.
- Schedule details: `{'schema':'schedule.v1','times':['HH:MM',...],'dose_raw':'1 viên'}`; timezone must be IANA (`Asia/Ho_Chi_Minh`). Entry version must be **confirmed** and the **latest** version of its item.
- Case: `case_type` 'SAFETY' (needs `assessment`, no schedule) or 'SCHEDULE' (needs `schedule`, may also pass `assessment`). Status flow `PENDING_CONSENT` → (grant + assign) `OPEN` → HCP review allowed only when OPEN/IN_REVIEW and actor == assigned HCP.
- HCP can read a case/messages only via `msa.can_access_case(id, user_id)` (assigned + active grant + permission).
- Dose: only on verified schedule; status `TAKEN|MISSED|SKIPPED`; changing a recorded dose requires `supersedes=<previous record id>`.
- Reminder enable: schedule verified & current (not superseded) + a COMPLETED assessment whose snapshot contains that entry. If DDI/duplicate coverage ≠ ASSESSED or MAJOR/SEVERE finding → needs `HCP_VERIFIED` schedule approved in a case linked to that same assessment (DB raises "…needs HCP approval…"). Preferences: `{'schema':'notification-preferences.v1','channel':'IN_APP'}`.
- An already-confirmed schedule cannot be re-confirmed: to get HCP approval create a **new revision** `save_schedule(..., origin='PROPOSED_CHANGE', supersedes=<old id>)`, open a SCHEDULE case on it, after APPROVED call `confirm_schedule(new_id, digest, uuid4(), explicit_confirmation=True, review_outcome=<outcome id>)`, then `set_reminder`.

## 3. To build
### Module 4 — `src/module4_hcp/service.py` + `apps/backend/api/routes/hcp.py` (prefix `/api/v1/hcp`)
| Method | Path | Perm | Does |
|---|---|---|---|
| GET | `/providers` | patient.workspace | list HCPs (id, full_name) |
| POST | `/cases` | patient.workspace | body `{kind, assessment_id?, schedule_id?, hcp_id, consent: true}` → create_case + grant + assign (for SCHEDULE: create PROPOSED_CHANGE revision first, see §2) |
| GET | `/cases/mine` | patient.workspace | own cases + status + latest outcome |
| GET | `/cases` | clinical.case_review | queue: cases assigned to me & accessible |
| GET | `/cases/{id}` | either | case + medication name/schedule + messages + outcomes (403 if not accessible) |
| POST | `/cases/{id}/messages` | either | `{text}` → case_message |
| POST | `/cases/{id}/review` | clinical.case_review | `{decision: APPROVED|CHANGES_REQUESTED|REJECTED, notes}` → record_review only; case remains open until patient activation |

### Module 5 — `src/module5_reminders/service.py` + `apps/backend/api/routes/reminders.py` (prefix `/api/v1/reminders`, patient.workspace)
| Method | Path | Does |
|---|---|---|
| GET | `/entries` | confirmed latest medication entry versions (id, `medication_fields->>'name_raw'`) to pick from |
| POST | `/schedules` | `{entry_version_id, times[], dose_raw, timezone, confirm: true}` → save + confirm (PATIENT_CONFIRMED) |
| GET | `/schedules` | current (non-superseded) schedules + verification + reminder setting |
| PUT | `/schedules/{id}/reminder` | `{enabled}` → set_reminder with latest COMPLETED assessment containing the entry; on "HCP approval" DB error return 409 `{code:'HCP_REVIEW_REQUIRED'}` |
| POST | `/schedules/{id}/activate` | find APPROVED outcome for a PROPOSED_CHANGE revision → confirm_schedule(review_outcome) → set_reminder → close the reviewed case as patient, atomically |
| GET | `/today` | expand `times` of verified current schedules for today in schedule timezone; merge latest dose record per occurrence → `[{schedule_id, name, time, scheduled_for, status: PENDING|TAKEN|SKIPPED|MISSED}]` |
| POST | `/doses` | `{schedule_id, scheduled_for, status, supersedes?}` → record_dose |
| GET | `/adherence?days=7` | `taken / total_due` over the window |
Keep `today`/`adherence` math as **pure functions** (unit-testable without DB).
In-app notification only (banner when a dose is due); real push/scheduler = future work.

### Frontend (`apps/frontend/src`)
- Add API helpers to `api.ts`.
- HCP: `pages/Hcp.tsx` → `HcpQueue` (uses `state.cases`) and `HcpCase` (`/hcp/case/:id`): load from API when logged in; keep `useDemo()` data as fallback for preview mode.
- Reminders: `pages/Patient.tsx` `Reminders` (uses `state.doses`), `pages/Flows.tsx` `DoseHistory`, `ReminderEditor` → use API.
- Patient "send to HCP" button on a case/assessment or schedule (choose HCP from `/providers`, consent checkbox).
- NOTE: `ProfileReminder.tsx` is the profile-completion popup — unrelated, don't touch.

## 4. Tests
- `tests/unit/module5/test_adherence.py` (pure functions).
- `tests/integration/test_module4_5_api.py` modeled on `test_system_persistence.py` (needs `MODULE2_TEST_DSN`, skips otherwise).
- Playwright: `apps/frontend/tests/hcp-case.spec.ts`, `reminders.spec.ts` (follow `intake-fixture.ts` / `rbac.spec.ts`).

## 5. Baseline (must not regress)
- `venv/Scripts/python -m pytest tests/backend tests/unit -q` → 558 pass / 8 fail / 85 error (failures = missing local data `data/DDInter/`, `data/reference/`; known).
- `cd apps/frontend && npm run build && npx playwright test` → 34 pass / 1 skip.

## 6. Done when
Demo: patient logs in → has confirmed meds + assessment → creates schedule → enable reminder (or 409 → send SCHEDULE case to HCP) → HCP sees `/hcp/queue`, messages, APPROVES → patient activates → `/reminders` shows today's doses → mark TAKEN → adherence updates. Commit on the feature branch; PR to `dev`.
