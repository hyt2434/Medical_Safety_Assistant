# Repository cleanup - 2 November 2026

## Folder organization and README consolidation

- Standardized design paths to `docs/design/database/` and `docs/design/use-cases/`.
- Moved the initial proposal from `docs/latex/` to `pa/pa0/project-proposal/`.
- PA1 report folders are `project-plan/` and `vision-document/`; original templates live in `templates/`, original screenshots in `ui-prototype/screenshots/`.
- PA2 folders are `database-design/`, `use-case-report/`, `ui-report/` and the historical `ui-prototype/`.
- Database Word reports live in `database-design/reports/`; unused PA1 recaptures live in `ui-report/archive/pa1-recaptures/`.
- Removed three redundant README files; consolidated their navigation and version context in the root README. Kept actual build instructions and the PlantUML traceability index.
- Updated source paths, frontend screenshot destination and root ignore rules. Frontend build and both UI/use-case LaTeX builds passed; existing use-case layout warnings remain.
- Removed the obsolete PA1 weekly-report folder containing only generated LaTeX auxiliary files.

- Selected the newly supplied root-level Use Case files as the authoritative version, as requested.
- Consolidated them into `docs/design/use-cases/` and `pa/pa2/use-case-report/`.
- Verified a local backup of all 213 files from both versions before replacement: `tmp/repo-cleanup-2026-11-02/use-cases-before-cleanup.zip`. This backup is ignored by Git; the previously tracked versions remain in Git history.
- Removed 178 verified duplicate copies, including the redundant root folders, copied PA1 screenshots, copied ERD images and unused embedded UI screenshots.
- Removed four redundant `.gitkeep` files from populated directories; kept placeholders for empty future PA stages.
- UI report now references original PA1 screenshots in `pa/pa1/ui-prototype/screenshots/`.
- Database report now references canonical legacy ERD images in `docs/design/database/legacy-64-tables/`.
- Use-case SVG sources live in the canonical PlantUML directory. `prepare_figures.py` reads them there and writes report PDFs into `sections/images/`.
- Moved `Weekly_Report_Week4_Reviewed.docx` into `docs/management/weekly-reports/`.
- Kept PA1/PA2 historical implementations, different ERD versions and non-identical documents. These are not interchangeable duplicates.

Reports now depend on shared repository assets. Build from each report directory; a standalone external upload must include the referenced images.

## Verification

- `git diff --check` passes; external image references resolve.
- UI report rebuilt (38 pages); original PA1 image rendering checked.
- Selected Use Case report rebuilt using the supplied vector PDFs (27 pages). Its existing table layout produces overfull-box/glue warnings; the cleanup does not redesign those tables.
- SVG regeneration needs the packages in `requirements.txt (repository root)`; this environment currently lacks `reportlab`.
- Database report rebuild is blocked by missing LaTeX package `enumitem`; existing PDF retained.
