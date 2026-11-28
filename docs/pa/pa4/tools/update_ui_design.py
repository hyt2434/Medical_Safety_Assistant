"""Turn the PA3 UI Design main.tex into the PA4 final UI design (blue = changed in PA4).

Run from repo root: python docs/pa/pa4/tools/update_ui_design.py
"""
from pathlib import Path

P = Path('docs/pa/pa4/UI Design/main.tex')
s = P.read_text(encoding='utf-8')


def rep(old, new, count=1):
    global s
    assert s.count(old) >= count, old[:70]
    s = s.replace(old, new)


rep('% UI Design - Medication Safety Assistant (PA3, Group 02)',
    '% UI Design - Medication Safety Assistant (PA4 final design, Group 02)\n% PA4: text added or changed in PA4 is blue (\\upd{...} / updated environment).')
rep('\\usepackage{graphicx,fancyhdr,lastpage}',
    '\\usepackage{graphicx,fancyhdr,lastpage,xcolor,array,tabularx}\n'
    '\\definecolor{pafourblue}{RGB}{0,82,204}\n'
    '\\newcommand{\\upd}[1]{{\\color{pafourblue}#1}}\n'
    '\\newenvironment{updated}{\\par\\color{pafourblue}}{\\par}\n'
    '\\newcolumntype{L}[1]{>{\\raggedright\\arraybackslash}p{#1}}')
rep('pdfsubject={PA3 - Design User Interface}', 'pdfsubject={PA4 - Final User Interface Design}')
rep('UI Design\\enspace(PA3-Group02-UI)', 'UI Design\\enspace(PA4-Group02-UI)')
rep(' Version 3.0\\\\[-1pt]', ' Version 2.0\\\\[-1pt]{\\fontsize{9}{11}\\selectfont 28 November 2026}')
rep('PA3 -- Design User Interface\\par', '\\upd{PA4 -- Final User Interface Design}\\par')
rep('{\\fontsize{12}{15}\\selectfont Version 1.0\\par}', '{\\fontsize{12}{15}\\selectfont \\upd{Version 2.0}\\par}')
rep('\\textbf{Document identifier:} & PA3-Group02-UI', '\\textbf{Document identifier:} & \\upd{PA4-Group02-UI}')
rep('\\textbf{Date:} & 15 November 2026', '\\textbf{Date:} & \\upd{28 November 2026}')
rep(' Medication intake Option A uses two views of the same long screen. All screenshots use illustrative data and 2x pixel density.',
    ' Medication intake Option A uses two views of the same long screen. All screenshots use illustrative data and 2x pixel density.\\par\\smallskip\n'
    ' \\upd{\\textbf{PA4 decision:} the team selected Option A for every screen as the final design. Option B screens are kept as the PA3 alternatives that were evaluated and not selected. New screens for HCP review and medication reminders (Modules 4 and 5) are added in Section 6.}')

# Mark Option B captions as not-selected alternatives.
for old in ('Option B (proposed design)}', 'Option B -- Proposed design}'):
    s = s.replace(old, 'Option B \\upd{(PA3 alternative -- not selected)}}')

# Revision history + decision section after the cover page.
rep('\\clearpage\n\\tableofcontents', r'''\clearpage
\begin{center}{\bfseries\fontsize{16}{20}\selectfont Revision History\par}\end{center}
\vspace{6pt}
\begin{tabularx}{\textwidth}{|L{3cm}|L{2cm}|X|L{4cm}|}
\hline
\textbf{Date} & \textbf{Version} & \textbf{Description} & \textbf{Author}\\ \hline
15 Nov 2026 & 1.0 & PA3: two UI design options (A and B) for eleven screens across five roles. & Group 02\\ \hline
\upd{28 Nov 2026} & \upd{2.0} & \upd{PA4: final design selected (Option A for all screens, with rationale); Option B kept as not-selected alternatives; new screens for HCP case review and medication reminders implemented in release v0.4.0 (Section 6).} & \upd{Group 02}\\ \hline
\end{tabularx}

\medskip
\upd{\textit{Convention: text written in blue was added or changed in PA4.}}
\clearpage
\tableofcontents''')

rep('\\rolesection{Patient}', r'''\clearpage
\section{\upd{Final Design Decision}}
\begin{updated}
After discussing the PA3 options, the team chose \textbf{Option A} for all eleven screens. Option A is the implemented frontend, it was exercised by the PA4 system tests, and it keeps one consistent layout (top navigation, breadcrumb, cards) across all roles and on mobile widths. The Option B ideas that remain useful are recorded as future improvements.

\medskip
\begin{tabularx}{\textwidth}{|L{5.2cm}|L{2.2cm}|X|}
\hline
\textbf{Screen} & \textbf{Final choice} & \textbf{Rationale}\\ \hline
Patient home & Option A & Balanced overview of the next dose, today's progress and medicines; works without a sidebar on mobile.\\ \hline
Medication intake & Option A & Shows all draft medicines next to the source for comparison; supports image, voice and manual input already tested.\\ \hline
Medication confirmation & Option A & Table with per-medicine and confirm-all actions is faster; explicit confirmation is still required.\\ \hline
HCP workspace and queue & Option A & Metric-led overview and table scale to many cases; the live queue now loads real assigned cases (Section 6).\\ \hline
Medical Reviewer workspace and queue & Option A & Table editing matches the catalog workflow; the Option B save-draft boundary is a future improvement.\\ \hline
Admin workspace and account management & Option A & Immediate role changes are protected by server authorization and audit; a review wizard (Option B) is a future improvement.\\ \hline
Technical Support workspace and queue & Option A & Simple list with filters is sufficient for the current ticket volume.\\ \hline
\end{tabularx}
\end{updated}
\rolesection{Patient}''')

new_section = r'''
\rolesection{\upd{New Screens for Modules 4 and 5 (Release v0.4.0)}}
\designfigure{09-reminders-today.png}
 {\upd{Figure 24. Medication reminders -- today's doses (final design)}}
 {\color{pafourblue}\screendetails{Let the patient see the doses due today and record each one (UC-06, UC-08).}
 {The page shows the 7-day adherence summary, today's doses with time and status, and buttons to record Taken, Skipped or Missed. Tabs lead to schedule creation and dose history. Data comes from the live reminders API.}
 {Select Taken, Skipped or Missed for a due dose; a recorded dose can be corrected later. Future doses cannot be recorded. Use "Tạo lịch dùng thuốc" to create a schedule from a confirmed medicine. Reminders are shown in the application only.}}
\designfigure{11-schedule-pending-review.png}
 {\upd{Figure 25. Schedule with a pending HCP proposal (final design)}}
 {\color{pafourblue}\screendetails{Show the current schedule, its verification status and any proposal waiting for HCP review (UC-04, UC-06, UC-07).}
 {Each schedule card shows dose, time, time zone and status (PATIENT\_CONFIRMED, HCP\_VERIFIED). A pending proposal is listed under it with status UNVERIFIED and the review state; the list of submitted cases follows.}
 {Turn reminders on or off for an eligible schedule. If the system answers that HCP review is required, choose an HCP, give consent and send the schedule. While a proposal is undecided, enabling is blocked but disabling stays available. After approval, use the activation button.}}
\designfigure{10-dose-history.png}
 {\upd{Figure 26. Dose history and 7-day adherence (final design)}}
 {\color{pafourblue}\screendetails{Let the patient review recorded doses and adherence over the last seven days (UC-09).}
 {The adherence card shows taken doses over due doses and a percentage. The list shows each dose with medicine, time, date and recorded status, with correction buttons.}
 {Review the history and correct a wrong status when needed. A dose is counted as missed only one hour after its time; days follow the schedule's time zone.}}
\designfigure{12-hcp-live-queue.png}
 {\upd{Figure 27. HCP live case queue (final design)}}
 {\color{pafourblue}\screendetails{Show the HCP only the cases assigned to them with valid patient consent (UC-05).}
 {Each card shows the case type, status and time, with an action to open the case. The assessment view lists SAFETY cases only. If access is denied, no demonstration data is shown.}
 {Open a case to review it. Cases disappear from the queue when the patient revokes consent.}}
\designfigure{13-hcp-case-review.png}
 {\upd{Figure 28. HCP case detail with conversation and outcome (final design)}}
 {\color{pafourblue}\screendetails{Let the HCP review a case, talk with the patient and record one outcome (UC-05).}
 {The case header shows the type and status with the shared schedule (medicine, dose, time, time zone). The conversation area lists messages; the outcome area shows the recorded decision and notes.}
 {Read the shared information, send messages, then record APPROVED, CHANGES\_REQUESTED or REJECTED with notes. Only one outcome can be recorded per case; the form is hidden afterwards. The patient activates an approved schedule from the reminders page.}}
'''
rep('\n\\end{document}', new_section + '\n\\end{document}')
P.write_text(s, encoding='utf-8')
print('ok')
