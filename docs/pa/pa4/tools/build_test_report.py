"""Build PA4 test report workbook (Group 02) from the instructor's template.

Run from repo root after build_test_cases.py:
    python docs/pa/pa4/tools/build_test_report.py
"""
from copy import copy
from datetime import datetime
from pathlib import Path
import openpyxl
from openpyxl.drawing.image import Image
from openpyxl.styles import Alignment, Font

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / 'test-report template-v1.1.xlsx'
CASES = ROOT / 'PA4-Group02-Test-Cases.xlsx'
OUT = ROOT / 'PA4-Group02-Test-Report.xlsx'
DATE = datetime(2026, 11, 28)
WRAP = Alignment(wrap_text=True, vertical='top')
BOLD = Font(bold=True)

ENVIRONMENT = [
    ('Operating system', 'Windows 11 Home 10.0.26300 (x64)'),
    ('Backend', 'Python 3.14, FastAPI/Uvicorn (apps/backend), pytest 9'),
    ('Database', 'PostgreSQL 18 (local, port 5432); isolated marked test DB msa_core_test_v4m45checks for integration tests'),
    ('Frontend', 'Node.js + Vite production build (apps/frontend)'),
    ('Browsers', 'Chromium (Playwright, desktop 1280px and mobile 375px viewports); manual checks planned on Microsoft Edge and Firefox'),
    ('Source version', 'branch dev @ de32207c (PR #86 merged, 28 Nov 2026)'),
]

SUITES = [
    ('Backend + unit tests (pytest tests/backend tests/unit)', 644, 8, 85, 12, 'Failures/errors are pre-existing: missing local reference data (B001), test environment (B002)'),
    ('Integration tests (pytest tests/integration)', 2, 0, 33, 73, 'Skips are opt-in suites (need NLP_TEST_DSN, MODULE2_TEST_DSN, Ollama, Whisper); errors = B001'),
    ('Module 4/5 API on real PostgreSQL (test_module4_5_api)', 2, 0, 0, 0, 'Full flow: schedule -> HCP review -> activation -> doses -> access rules'),
    ('End-to-end UI tests (Playwright, Chromium)', 43, 0, 0, 1, 'One opt-in real-model test skipped'),
    ('Frontend production build (npm run build)', 1, 0, 0, 0, 'TypeScript + Vite build passed'),
]

# (id, title, description, function, severity, status, comment)
BUGS = [
    ('B001', 'Module 2/3 tests cannot run without local reference data',
     'data/DDInter/ (git-ignored) and data/reference/ (never committed) are missing on the test machine, so 85 unit errors, 8 failures and 33 integration errors occur in Module 2/3 suites.',
     'UC-03', 'Medium', 'Open', 'Environment/data issue; obtain the dataset from the database owner (Cao Hoang Long) and re-run.'),
    ('B002', 'NLP interactive test subprocess misses PYTHONPATH',
     'tests/unit/test_nlp_interactive.py starts a subprocess that cannot import module1_intake because PYTHONPATH=src is not passed.',
     'UC-11', 'Low', 'Open', 'Test harness defect, not a product defect.'),
    ('B003', 'Real voice-decoding test skipped (faster_whisper not installed)',
     'test_voice_real_decode is skipped because faster_whisper is not installed in the test environment.',
     'UC-02', 'Low', 'Open', 'Install voice requirements to execute.'),
    ('B004', 'rapidfuzz missing in the virtual environment',
     'Manual-input suggestion tests failed to import rapidfuzz although it is listed in manual_input/requirements.txt.',
     'UC-02', 'Low', 'Fixed', 'Installed dependency; 52/52 intake unit tests pass.'),
    ('B005', 'Schedule proposal cannot carry new timing',
     'A SCHEDULE review case copies the current schedule details; the patient cannot propose different times/dose, so CHANGES_REQUESTED cannot be satisfied.',
     'UC-07', 'High', 'Open (deferred)', 'Root cause: index one_schedule_root (migration 003) forbids a standalone proposal. Fix planned as migration 006 with the DB owner.'),
    ('B006', 'Current schedule cannot be re-enabled while a proposal is pending',
     'Sending a schedule for review links the proposal as a revision immediately; the DB then rejects enabling the current schedule until the proposal is decided.',
     'UC-07', 'Medium', 'Open (deferred)', 'Same root cause as B005. Disabling remains available.'),
    ('B007', 'Duplicate review request on a pending proposal',
     'Submitting a second SCHEDULE case for the same pending proposal creates a new revision instead of reusing the active request (UC-04 A3).',
     'UC-04', 'Medium', 'Open', 'Found in code review; to be fixed together with B005.'),
    ('B008', 'HCP review outcome rolled back',
     'Recording an outcome also tried to close the case as the HCP; the DB guard allows only the patient to update the case, so the whole review was rolled back.',
     'UC-05', 'High', 'Fixed', 'Closure moved to patient activation (G4-fix).'),
    ('B009', 'Reminder toggle locked after any proposal',
     'After a proposal existed (even rejected) the UI disabled the reminder toggle, so the patient could not turn reminders off.',
     'UC-07', 'High', 'Fixed', 'Only enabling is blocked while undecided; disabling always allowed (G10).'),
    ('B010', 'Two active schedules for one medicine after editing it',
     'A schedule could be created for a new medicine version while the old version still produced doses, doubling reminders and adherence counts.',
     'UC-06', 'High', 'Fixed', 'Newest confirmed version required; one active schedule per medicine (G11-C).'),
    ('B011', 'Approved reminder required re-review after a new assessment',
     'Re-enabling used the latest assessment instead of the reviewed one, so the DB demanded HCP approval again.',
     'UC-07', 'Medium', 'Fixed', 'Uses the exact reviewed assessment (G11-B).'),
    ('B012', 'Invalid timezone caused HTTP 500',
     'Entering "Asia" as timezone raised an OS error and returned 500 instead of a validation error.',
     'UC-06', 'Low', 'Fixed', 'Returns 422 (G9).'),
    ('B013', 'Second HCP outcome allowed on one case',
     'An HCP could record contradicting outcomes on the same case.',
     'UC-05', 'Medium', 'Fixed', 'Second outcome rejected; form hidden (G10).'),
    ('B014', 'Prototype-only features not persisted on the server',
     'Health summary (UC-12/13), support tickets (UC-16/17), dataset review (UC-14), health profile (UC-18) and account updates (UC-20) work on local UI data only; no server API yet.',
     'UC-12..UC-20', 'Medium', 'Open (planned)', 'Database tables exist (migration 003); APIs planned for next iterations.'),
]

SHOTS = [
    ('01-ocr-review.jpeg', 'UC-02: patient enters a prescription (image, voice or manual) and reviews it before confirmation'),
    ('02-hcp-case-review.jpeg', 'UC-05: assigned HCP opens a SCHEDULE case and the case conversation'),
    ('03-reminders-dose.jpeg', "UC-06/UC-08/UC-18: patient dashboard with today's doses (1/3 recorded) and the profile-completion reminder"),
]


def case_stats():
    ws = openpyxl.load_workbook(CASES)['Test cases']
    stats = {}
    for row in ws.iter_rows(min_row=2, values_only=True):
        uid, status = row[0], row[6]
        if not uid or not str(uid).startswith('UC-') or status is None:
            continue
        s = stats.setdefault(uid, {'Pass': 0, 'Fail': 0, 'Not run': 0})
        s[status] += 1
    names = {r[0]: r[1] for r in openpyxl.load_workbook(CASES)['Features'].iter_rows(min_row=6, values_only=True) if r[0]}
    return stats, names


def main():
    wb = openpyxl.load_workbook(TEMPLATE)
    summary, bugs = wb['Test summary report'], wb['Bug report']
    label_style = copy(summary['A1']._style)

    # ---- Test summary report ----
    summary['B1'] = 'HYTrang (Hoang Yen Trang), CHLong (Cao Hoang Long), LCThanh (Lo Chi Thanh)'
    summary['B2'] = DATE
    summary['B2'].number_format = 'yyyy-mm-dd'
    r = 3
    summary.cell(r, 1, 'Project')._style = copy(label_style)
    summary.cell(r, 2, 'Medication Safety Assistant - Group 02 - PA4 system testing')
    r += 2
    summary.cell(r, 1, 'Test environment').font = BOLD
    r += 1
    for k, v in ENVIRONMENT:
        summary.cell(r, 1, k)._style = copy(label_style)
        summary.cell(r, 2, v).alignment = WRAP
        summary.merge_cells(start_row=r, start_column=2, end_row=r, end_column=7)
        r += 1
    r += 1
    summary.cell(r, 1, 'Automated test execution (28 Nov 2026)').font = BOLD
    r += 1
    for c, h in enumerate(('Suite', 'Passed', 'Failed', 'Errors', 'Skipped', 'Note'), 1):
        summary.cell(r, c if c == 1 else c + 1, h).font = BOLD
    summary.merge_cells(start_row=r, start_column=1, end_row=r, end_column=2)
    r += 1
    for name, *nums, note in SUITES:
        summary.cell(r, 1, name).alignment = WRAP
        summary.merge_cells(start_row=r, start_column=1, end_row=r, end_column=2)
        for i, n in enumerate(nums):
            summary.cell(r, 3 + i, n)
        summary.cell(r, 7, note).alignment = WRAP
        r += 1
    r += 1
    summary.cell(r, 1, 'Functional test cases by use case (see PA4-Group02-Test-Cases.xlsx)').font = BOLD
    r += 1
    for c, h in enumerate(('Use case', 'Name', 'Total', 'Pass', 'Fail', 'Not run', 'Pass rate (executed)'), 1):
        summary.cell(r, c, h).font = BOLD
    r += 1
    stats, names = case_stats()
    tot = {'Pass': 0, 'Fail': 0, 'Not run': 0}
    for uid in sorted(stats):
        s = stats[uid]
        executed = s['Pass'] + s['Fail']
        for k in tot:
            tot[k] += s[k]
        vals = (uid, names.get(uid, ''), sum(s.values()), s['Pass'], s['Fail'], s['Not run'],
                f"{s['Pass'] / executed:.0%}" if executed else 'n/a')
        for c, v in enumerate(vals, 1):
            summary.cell(r, c, v).alignment = WRAP
        r += 1
    executed = tot['Pass'] + tot['Fail']
    for c, v in enumerate(('Total', '', sum(tot.values()), tot['Pass'], tot['Fail'], tot['Not run'],
                           f"{tot['Pass'] / executed:.0%}" if executed else 'n/a'), 1):
        summary.cell(r, c, v).font = BOLD
    r += 2
    summary.cell(r, 1, 'Conclusion').font = BOLD
    summary.cell(r, 2, ('The two main use-case groups required for this release are implemented and pass system tests: '
                        'medication intake and confirmation (UC-01..UC-03) and HCP review with medication reminders '
                        '(UC-04..UC-09). No executed test case failed. Not-run cases are listed with reasons; '
                        'open defects are tracked in the Bug report sheet.')).alignment = WRAP
    summary.merge_cells(start_row=r, start_column=2, end_row=r, end_column=7)
    summary.row_dimensions[r].height = 75
    summary.column_dimensions['A'].width = 24
    summary.column_dimensions['B'].width = 36
    summary.column_dimensions['G'].width = 48

    # ---- Bug report ----
    proto = [bugs.cell(2, c) for c in range(1, 10)]
    bugs.delete_rows(2, bugs.max_row)
    for i, (bid, title, desc, func, sev, status, comment) in enumerate(BUGS, 2):
        for c, v in enumerate((bid, title, desc, func, sev, 'HYTrang', DATE, status, comment), 1):
            cell = bugs.cell(i, c, v)
            cell._style = copy(proto[c - 1]._style)
            cell.alignment = WRAP
        bugs.cell(i, 7).number_format = 'yyyy-mm-dd'
    for col, w in zip('ABCDEFGHI', (8, 34, 60, 12, 10, 12, 13, 15, 45)):
        bugs.column_dimensions[col].width = w

    # ---- Screenshots ----
    shots = wb.create_sheet('Screenshots')
    shots['A1'] = 'Screenshots captured from the 28 Nov 2026 Playwright system-test traces (Chromium, 800x450 screencast frames)'
    shots['A1'].font = BOLD
    row = 3
    for fname, caption in SHOTS:
        shots.cell(row, 1, caption).font = BOLD
        img = Image(str(ROOT / 'screenshots' / fname))
        shots.add_image(img, f'A{row + 1}')
        row += 26
    shots.column_dimensions['A'].width = 110
    wb.save(OUT)
    print(f'{OUT.name}: {len(BUGS)} defects, totals {tot}')


if __name__ == '__main__':
    main()
