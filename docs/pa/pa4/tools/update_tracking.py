"""Build PA4 Project Execution and Tracking from the PA3 report (blue = PA4 additions).

Run from repo root: python docs/pa/pa4/tools/update_tracking.py
"""
import shutil
from pathlib import Path

SRC = Path('docs/pa/pa3/Project Execution and Tracking')
DST = Path('docs/pa/pa4/Project Execution and Tracking')
DST.mkdir(parents=True, exist_ok=True)
if not (DST / 'images').exists():
    shutil.copytree(SRC / 'images', DST / 'images')
s = (SRC / 'main.tex').read_text(encoding='utf-8')


def rep(old, new):
    global s
    assert old in s, old[:70]
    s = s.replace(old, new, 1)


rep('\\usepackage{graphicx,tabularx,array,booktabs,fancyhdr,lastpage}',
    '\\usepackage{graphicx,tabularx,array,booktabs,fancyhdr,lastpage,xcolor}\n'
    '\\definecolor{pafourblue}{RGB}{0,82,204}\n'
    '\\newcommand{\\upd}[1]{{\\color{pafourblue}#1}}')
rep('pdftitle={Project Execution and Tracking - PA3}', 'pdftitle={Project Execution and Tracking - PA4}')
rep('Project Execution and Tracking (PA3-Group02-Execution)}', 'Project Execution and Tracking (PA4-Group02-Execution)}')
rep('\\fancyhead[R]{\\small Version 2.0}', '\\fancyhead[R]{\\small Version 3.0\\\\28 November 2026}')
rep('\\vspace{5mm}PA3 -- Section f\\par', '\\vspace{5mm}\\upd{PA4 -- Section f}\\par')
rep('PA3: 02--14 November 2026; PA4 W7--W8 plan: 09--22 November 2026\\par',
    'PA3: 02--14 November 2026; \\upd{PA4: 16--28 November 2026}\\par')
rep('Execution, collaboration, delivery and verification evidence. PA4 is summarized as the next iteration. Online status checked on 15 November 2026.',
    'Execution, collaboration, delivery and verification evidence. \\upd{Part A (blue) records the PA4 iteration, checked on 28 November 2026. Part B keeps the PA3 record unchanged so progress across iterations stays traceable.}')

PART_A = r'''
\reportpage{\upd{Part A -- PA4 iteration (16--28 November 2026)}}
\color{pafourblue}
\textbf{A1. Execution summary.} The PA4 goal was a working release with at least two main use-case groups and system testing. All feature branches were integrated into \texttt{dev} and \texttt{main}; Modules 4 and 5 were implemented and merged; a full system test run was executed on 28 November.

\begin{tabularx}{\linewidth}{@{}p{55mm}X@{}}\toprule
\textbf{Area} & \textbf{Verified result as of 28 November 2026}\\\midrule
Integration of all branches & \pr{79}, \pr{81}, \pr{82} and \pr{83} merged on 27 November; \texttt{dev} and \texttt{main} synchronised by \pr{84}. Only \texttt{dev} and \texttt{main} remain on GitHub.\\
Module 4 and Module 5 & Implemented on a feature branch and merged by \pr{86} on 28 November (draft \pr{85} was closed and superseded).\\
Intake, chatbot, database & Long integrated voice/manual input, RAG chatbot, OCR/RBAC and the complete system schema (commits 19--23 November).\\
System testing & 644 backend/unit tests, 43 end-to-end UI tests and the Module 4/5 flow on real PostgreSQL passed; 114 functional test cases written for UC-01--UC-20.\\
Release & Release v0.4.0 prepared from \texttt{main} for PA4 submission.\\\bottomrule
\end{tabularx}

\reportpage{\upd{A2. Task allocation and status (PA4 board, issues \#72--\#77)}}
\color{pafourblue}
\begin{tabularx}{\linewidth}{@{}p{16mm}p{24mm}X p{60mm}@{}}\toprule
\textbf{Issue} & \textbf{Owner} & \textbf{Planned work} & \textbf{Status on 28 Nov (evidence)}\\\midrule
\href{https://github.com/hyt2434/Medical_Safety_Assistant/issues/73}{\#73} & Trang & Module 4 -- HCP review and communication & Implemented and merged (\pr{86}); issue still open for reviewer sign-off.\\
\href{https://github.com/hyt2434/Medical_Safety_Assistant/issues/72}{\#72} & Thanh & Module 5 -- reminders and adherence & Implemented by Trang in \pr{86} together with Module 4 because the two share one review flow; issue open for Thanh's review and manual tests.\\
\href{https://github.com/hyt2434/Medical_Safety_Assistant/issues/74}{\#74} & Long & Module 3 safety assessment & Open; system schema and access controls delivered (commit \commitref{6de2ce9a}).\\
\href{https://github.com/hyt2434/Medical_Safety_Assistant/issues/75}{\#75}, \href{https://github.com/hyt2434/Medical_Safety_Assistant/issues/76}{\#76} & Long & Health summary, health profile & Open; UI prototypes exist, server APIs planned (defect B014).\\
\href{https://github.com/hyt2434/Medical_Safety_Assistant/issues/77}{\#77} & Long & Medication cabinet & Open; UC-19 kept as future development.\\\bottomrule
\end{tabularx}

\textbf{Weekly goals (week of 22 November).} Trang: begin Module 4 and review/test User Management and OCR. Long: RAG chatbot, Module 3 improvements, database completion and end-to-end tests of Modules 1--3. Thanh: begin Module 5 and review/test Voice/STT and Manual Input. Source: \weekly.

\reportpage{\upd{A3. Delivery timeline (pull requests and commits)}}
\color{pafourblue}
{\fontsize{12}{14}\selectfont
\begin{tabularx}{\linewidth}{@{}p{26mm}p{30mm}X@{}}\toprule
\textbf{Date} & \textbf{Who} & \textbf{Delivery}\\\midrule
19 Nov & Long & RAG chatbot with source citations (\commitref{174014e7}); voice/manual input integrated with intake validation (\commitref{faa18726}).\\
20--21 Nov & Long & Intake E2E fixes and Module 2 tests; OCR UI + RBAC integration and NLP refactor (\commitref{6d1be2fe}).\\
22--23 Nov & Long & Complete system schema, access controls and audit API (\commitref{6de2ce9a}); CSV datasets consolidated (\commitref{451be27c}).\\
24 Nov & Trang & \pr{78}: \texttt{dev} merged into \texttt{main}.\\
27 Nov & Trang & Repository cleanup; unified DB setup and intake chat UI; \pr{79}, \pr{81}, \pr{82}, \pr{83}, \pr{84} merged -- all branches integrated, conflicts in Module 1 resolved in favour of the restructured version.\\
27--28 Nov & Trang & Module 4/5 implementation in goals G1--G11 on a feature branch, merged by \pr{86}.\\
28 Nov & Trang & Full system test run, test cases and report, SAD v2.0, final UI design.\\\bottomrule
\end{tabularx}}

\reportpage{\upd{A4. Collaboration and quality control -- review cycle}}
\color{pafourblue}
\textbf{How the work was controlled.} Modules 4 and 5 were split into small goals (G1--G7) with a verifiable ``done'' check each, recorded in \texttt{docs/management/codex-handoff-module4-5.md}. After each group of goals the branch went through an automated code review; every finding was either fixed in a new goal or recorded as a known defect. An AI coding assistant was used for parts of the implementation and review; all results were verified by running the test suites.

{\fontsize{12}{14}\selectfont
\begin{tabularx}{\linewidth}{@{}p{30mm}X p{55mm}@{}}\toprule
\textbf{Review round} & \textbf{Main finding} & \textbf{Action}\\\midrule
After G7 & HCP review was rolled back by the database guard (only the patient may update a case). & Fixed in G4-fix: closure moved to patient activation (B008).\\
Real-DB run & Integration test had never run (no test DSN); single-medicine assessment rule violated. & Isolated marked test DB created; test fixed and passing.\\
Round 3 & Activation of superseded schedules; data and dose-bound issues. & Fixed in G8-A/B/C.\\
Round 4 & Reminder toggle locked after any proposal (regression); duplicate outcomes. & Fixed in G9--G10 (B009, B013).\\
Round 5 & Proposals cannot carry new timing (root cause: \texttt{one\_schedule\_root} index). & G11-B/C/D fixed; G11-A deferred -- needs migration 006 with the DB owner (B005, B006).\\\bottomrule
\end{tabularx}}

\reportpage{\upd{A5. Testing results and problem resolution}}
\color{pafourblue}
\begin{tabularx}{\linewidth}{@{}p{80mm}p{38mm}X@{}}\toprule
\textbf{Suite (28 Nov, branch dev)} & \textbf{Result} & \textbf{Baseline 27 Nov}\\\midrule
Backend + unit (pytest) & 644 pass / 8 fail / 85 error & 558 / 8 / 85\\
Integration (pytest, opt-in suites skipped) & 2 pass / 33 error / 73 skip & 2 / 33 / 71\\
Module 4/5 flow on real PostgreSQL & 2 pass & --\\
End-to-end UI (Playwright) & 43 pass / 1 skip & 34 / 1\\
Functional test cases (UC-01--UC-20) & 114 written: 68 pass, 46 not run & --\\\bottomrule
\end{tabularx}

\textbf{Interpretation.} No regression was introduced. The remaining failures and errors are caused by local reference data missing on the test machine (B001), not by new code. Not-run cases are listed with reasons in the test-case workbook. Open defects: B001--B003, B005--B007, B014; fixed during PA4: B004, B008--B013.

\reportpage{\upd{A6. Next iteration}}
\color{pafourblue}
\begin{tabularx}{\linewidth}{@{}p{60mm}p{28mm}X@{}}\toprule
\textbf{Work} & \textbf{Owner} & \textbf{Approach}\\\midrule
Migration 006 for standalone schedule proposals (B005--B007) & Trang, Long & Relax \texttt{one\_schedule\_root} for proposals; re-run the Module 4/5 DB test.\\
Reference data package for testers (B001) & Long & Share \texttt{data/DDInter} and \texttt{data/reference}; re-run Module 2/3 suites.\\
Manual execution of the 46 not-run cases & All & Record actual results in the test-case workbook.\\
Server APIs for UC-12--UC-18, UC-20 (B014) & Long, Thanh & Use the existing tables of migration 003.\\
Review of Modules 4/5 by the issue owners & Thanh & Close \#72/\#73 after review and manual tests.\\\bottomrule
\end{tabularx}
\color{black}

\reportpage{Part B -- PA3 record (unchanged from the PA3 submission)}
The following pages are the PA3 tracking report, kept unchanged so that the progress between PA3 and PA4 remains traceable.
'''
rep('\\reportpage{1. Execution summary}', PART_A + '\n\\reportpage{1. Execution summary}')
(DST / 'main.tex').write_text(s, encoding='utf-8')
print('ok')
