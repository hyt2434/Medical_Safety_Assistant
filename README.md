# Medication Safety Assistant

## Repository layout

| Folder | Purpose |
| --- | --- |
| `apps/frontend/` | Current TypeScript frontend; PA1 entry retained for comparison. |
| `apps/backend/` | Backend source. |
| `data/` | Data documentation; local datasets in ignored `data/local/`. |
| `docs/design/` | Canonical ERD and PlantUML sources and diagram images. |
| `docs/management/` | Planning and weekly reports. |
| `pa/pa0/project-proposal/` | Initial proposal and LaTeX template. |
| `pa/pa1/` | PA1 deliverables and original UI screenshots. |
| `pa/pa2/` | PA2 use-case, database and UI reports. |
| `scripts/`, `tests/` | Development utilities and tests. |
| `tmp/` | Ignored working files and local recovery backups. |

## Main entry points

- Frontend: [instructions](apps/frontend/README-PA2.md), [design system](apps/frontend/design.md).
- Use-case diagrams: [PlantUML](<docs/design/use-cases/plantuml>).
- Use-case report: [main.tex](pa/pa2/use-case-report/main.tex).
- UI report: [main.tex](pa/pa2/ui-report/main.tex).
- Database report: [main.tex](pa/pa2/database-design/main.tex).
- Cleanup record: [2026-11-02](docs/management/repository-cleanup-2026-11-02.md).

## PA and documentation map

```text
docs/
  design/
    database/
      simplified-35-tables/    Current draft schema
      legacy-64-tables/        Historical schema and images
    use-cases/plantuml/        Diagram sources, SVGs and traceability
  management/weekly-reports/
  requirements/               Reserved
  test/                       Reserved
pa/
  pa0/project-proposal/
  pa1/
    project-plan/
    vision-document/
    templates/                Original assignment templates
    ui-prototype/screenshots/ Original PA1 reference images
  pa2/
    database-design/reports/  Database report documents
    use-case-report/          Selected current specifications
    ui-report/                Current illustrated UI report
    ui-prototype/             Historical standalone HTML prototype
  pa3/ ... pa5/               Reserved
```

The 35-table schema is a draft with unified, module and domain views. The legacy database LaTeX report still describes the 64-table version. Do not treat them as interchangeable.

Compile reports from their own directories using `xelatex main.tex`. The database report requires `enumitem`. For use-case SVG conversion, first install `requirements.txt`, then run `build.ps1`. Report-specific README files are retained only where they contain build or usage instructions; diagram links and alternative-flow guidance remain in `docs/design/use-cases/plantuml/README.md`.

## File ownership

Keep one canonical copy of each source image. Reports reference it using relative paths; compile from the report directory with the complete repository available. Uploading only a report folder to an external LaTeX service requires bundling its referenced images first.

PDFs are deliverables, not duplicate source files. Different PA stages and legacy ERD versions are retained for comparison. Maintain ignore rules only in the root `.gitignore`; do not commit dependencies, local datasets, credentials or temporary build files.
