# Project Tracking — Medication Safety Assistant

> Source of truth for project scheduling: **Software Development Plan v1.0** and **Vision Document v1.0**, Group 02. This board guide reflects **planned** work, not evidence that features are implemented.

## Roadmap (5 sprints, 3 phases)

| Phase | Sprint | Period (Vietnam local) | Goal | Major output |
|---|---|---|---|---|
| Inception | Sprint 1 | 05–18 Oct 2026 | Scope, planning, risk tracking and wireframes | PA1 package; 3–6 UI sketches; 2 weekly reports |
| Elaboration | Sprint 2 | 19 Oct–01 Nov 2026 | Requirements and architecture baseline | Prioritized PF/NFR backlog, data feasibility, interfaces |
| Elaboration | Sprint 3 | 02–15 Nov 2026 | Verify highest-risk inputs and data mapping | **Build 0.1** technical proof of concept |
| Construction | Sprint 4 | 16–29 Nov 2026 | Integrate medication safety core | **Build 0.2** integrated test build |
| Construction | Sprint 5 | 30 Nov–13 Dec 2026 | Reminders, follow-up, testing and release | **Build 1.0** final prototype |

**UI Prototype:** due 18 Oct 2026. Planned releases: Build 0.1 on 15 Nov; Build 0.2 on 29 Nov; Build 1.0 on 13 Dec.

## How work is represented on GitHub

- **Feature Issues:** [PF-01…PF-10](https://github.com/hyt2434/Medical_Safety_Assistant/issues?q=is%3Aissue+label%3Atype%3Afeature) map to product requirements in Vision §5.
- **Sprint Task Issues:** [Sprint 1](https://github.com/hyt2434/Medical_Safety_Assistant/issues?q=is%3Aissue+label%3Asprint%3A1) · [Sprint 2](https://github.com/hyt2434/Medical_Safety_Assistant/issues?q=is%3Aissue+label%3Asprint%3A2) · [Sprint 3](https://github.com/hyt2434/Medical_Safety_Assistant/issues?q=is%3Aissue+label%3Asprint%3A3) · [Sprint 4](https://github.com/hyt2434/Medical_Safety_Assistant/issues?q=is%3Aissue+label%3Asprint%3A4) · [Sprint 5](https://github.com/hyt2434/Medical_Safety_Assistant/issues?q=is%3Aissue+label%3Asprint%3A5).
- **Non-functional requirements:** [#31](https://github.com/hyt2434/Medical_Safety_Assistant/issues/31) for NFR-01…NFR-21; [#33](https://github.com/hyt2434/Medical_Safety_Assistant/issues/33) for testing.
- **Risk register:** [#32](https://github.com/hyt2434/Medical_Safety_Assistant/issues/32) for R-01…R-11.
- Work remains open until acceptance evidence is attached and reviewed. Do not use closed/open as an invented progress history.

## Recommended GitHub Projects v2 board configuration

Because the GitHub connector can manage repository Issues but **cannot manage GitHub Projects boards or custom fields**, an authorized team member should do this once in the GitHub web UI:

1. Open `https://github.com/hyt2434/Medical_Safety_Assistant/projects` or the owner's **Projects** page; select **New project → Board** (if no board exists).
2. Name it **Medication Safety Assistant — Course Project**. Add repository issues via **Add item → Add from repository**, choosing this repository and all open issues.
3. Use built-in **Status** field with columns `Todo → In Progress → In Review → Done`. Do not mark any item Done unless verified.
4. Add **Sprint** (single select: Sprint 1…Sprint 5), **Priority** (High, Medium, Low), **Area** (OCR, Voice, NLP, Data, Safety, UX, Documentation, QA) and **Target date** (date) if useful. Existing `sprint:1` … `sprint:5` labels are usable for filtering immediately even before custom fields are populated.
5. Create a **Board** view grouped by **Status**; a **Sprint** table view grouped by **Sprint**; and a **Roadmap** view with date/iteration field if enabled. Filters like `label:sprint:2` select that sprint's tasks.
6. Invite team collaborators using their verified GitHub usernames and set Assignee after they accept access. Owners listed in descriptions are **planned** only.

## Responsibilities (from Project Plan §3.2)

| Member | Planned areas |
|---|---|
| **Hoàng Yến Trang** | Team lead/project management; OCR, UI/UX, evidence/build coordination |
| **Cao Hoàng Long** | NLP; DAV medicine data normalization; DDInter mapping and risk checks |
| **Lỗ Chí Thành** | Voice capture/speech-to-text; transcript correction, reminder work |
| **Whole team** | Safety and quality review; integration, test and documentation |

## Issue workflow and completion evidence

- **Todo:** planned in a sprint; clear description and acceptance criteria.
- **In Progress:** member has started; commits/prototype/doc revisions linked.
- **In Review:** implementation/docs/test evidence submitted for peer review, especially safety-critical decisions.
- **Done:** acceptance criteria met, tests passed, limitations documented, evidence linked. Update weekly report only from actual status.

Every weekly report should summarize completed, in-progress and blocked issues (with issue links), actual changes, risks and next-week commitments. Do not claim the project is clinically safe or production-ready.

## Clinical-safety guardrails

All OCR/STT output must be edited/confirmed before medication assessment; changes invalidate prior results. DAV identity mapping precedes reviewed DDInter lookup. Missing, ambiguous, unavailable or unassessed data **must not** appear as safe. NLP explains structured findings only. Severe or emergency results should give conservative escalation guidance, not autonomous medication instructions. Professional review is **simulated** in the course prototype. Only synthetic/de-identified data should be used for demonstrations.

## Scope exclusions

No handwritten prescription recognition, pill identification, drug-food timing checks, real healthcare integration, production deployment or autonomous clinical decision-making in the initial release.
