# Repository cleanup and submission verification — 10 November 2026

Cleanup is applied on `NLP-ChatBot` without committing, pushing, switching
branches, changing Git refs/index, or manipulating the existing stash. The latest
NLP V2 code recovered from local `db` commit `aaf76f3` remains intact. Core DB V4
and NLP V2 have zero regressions in their required suites. One pre-existing OCR
test collection error still prevents claiming that the whole repository is green.

## Final structure and ownership

```text
Medical_Safety_Assistant_Team/
|-- apps/
|   `-- frontend/                    Canonical TypeScript/Vite PA2 app
|       |-- src/, tests/
|       `-- package.json, package-lock.json, index.html, pa1.html, configuration
|-- data/                            Approved medication sources; unchanged
|-- db/                              Canonical Core Database V4
|   `-- migrations/, scripts/, tests/, docs/, schema_contract.json, CLI
|-- docs/
|   |-- design/, requirements/, management/, analysis and design/
|   `-- pa/
|       |-- pa0/
|       |-- pa1/react-prototype/     Original React app, assets, lockfile, tests
|       `-- pa2/                     Reports and historical standalone prototype
|-- src/                             Reusable Python business modules only
|   |-- module1_intake/
|   |   |-- manual_input/
|   |   |-- nlp/
|   |   |   |-- understanding/
|   |   |   |-- dialogue_management/
|   |   |   |-- qa_pipeline/rag/
|   |   |   |-- integration/
|   |   |   `-- interfaces/, models.py, API/architecture/README, launchers
|   |   |-- ocr/
|   |   `-- voice/                   Retained existing Python package contract
|   |-- module2_medications/
|   |-- module3_interactions/
|   |-- module4_hcp/
|   |-- module5_reminders/
|   `-- shared/                     Core DB adapters and DAV staging/import
|-- tests/                          Unit, integration and end-to-end tests
|-- scripts/                        Shared CLI/setup/utilities
|-- artifacts/                      Ignored runtime, caches and test evidence
`-- .gitattributes, .gitignore, pytest.ini, README.md
```

Root `src/` contains only the Python module packages. `db/` owns Core V4
migrations, management, schema contracts and DB tests; `src/shared/db/` is its
application adapter layer. `src/shared/schema.sql` is the separate DAV SQLite
import staging schema. No backend API application exists in this checkout, so
no empty `apps/backend/` was created. Existing package markers are retained.

## Frontend investigation and decision

| Implementation | History / owner | Scope and dependencies | Final location |
| --- | --- | --- | --- |
| Current PA2 app | Hoang Yen Trang; latest frontend changes `6746aea`, 2 Nov 2026 | TypeScript, Vite 7, Puppeteer; five roles, review/support/reviewer/admin flows, versioned summaries and reminders; localStorage | Canonical `apps/frontend/` |
| Original PA1 React app | Hoang Yen Trang, `53ef20b`, 18 Oct 2026 | React 19, React Router 7, Lucide, Vite 6, Playwright; unique Web Speech/spoken replies, chat history/mascot and workflow state; sessionStorage | `docs/pa/pa1/react-prototype/` |

These are different implementations with different state models, not identical
copies. The current PA2 entry point was preserved. All 24 original React files
were relocated together; only its README and redundant ignore file were changed.
All React code, asset, configuration and lockfile bytes match the pre-move hashes.
Its public assets and imports remain relative to its own project root. Both
frontends build and their browser regressions pass. Neither currently calls an
API. No source was merged blindly, no Python modules were copied into an app,
and no new compatibility wrappers were introduced.

## Removed, moved and retained files

- Recovered 128 clean/missing committed source and contract files from `aaf76f3`
  in the earlier pass; Python business logic and all Core migration bytes are
  unchanged in this final pass. Retained the six NLP layers, public DTOs, four
  launchers and 14 necessary compatibility forwards; their alias/schema tests pass.
- Moved PA deliverables and report sources under `docs/pa/`, updating report,
  screenshot, vector-conversion and documentation paths.
- Removed 52 SHA-256-identical PA1 screenshot copies. Retained canonical
  screenshots, unique project assets, PDFs and original submission ZIPs.
- Kept distinct generated website captures, archives and design-tool logs in
  ignored local `artifacts/`; no active PostgreSQL data directory was moved,
  deleted or reinitialized. Existing runtime/manifest locations remain in place.
- Removed the obsolete capture utility whose PA1 HTML inputs no longer exist,
  unused empty PA-stage placeholders, and redundant ignore files. Consolidated
  the older NLP contract/timing documents into the existing V2 README/API/architecture.
- Moved the historical React PA1 app to its submission directory intact and
  documented the canonical frontend. Centralized its generated-output ignore
  rules. `pytest.ini` now resolves root Python modules and keeps the pytest cache
  under ignored `artifacts/`; the existing cache was retained there.
- Preserved all 13 existing data files at their original paths with matching
  SHA-256 hashes. No approved dataset contents were edited or replaced.

The exact per-file actions/reasons and retained-file hashes are in ignored local
`artifacts/repository_cleanup_20261110.json`. No additional audit/backup directory
or worktree was created. Existing tooling metadata is retained.

## Verification results

| Check | Result |
| --- | --- |
| NLP MVP V2, real Qwen + isolated PostgreSQL | **169 passed**, no failures/errors/skips; 65.09 s |
| Core Database V4 | **46 passed**, no failures/blocked cases |
| Existing medication parser / interaction conflict / mocked Vision retry checks | **25 passed**, plus 4 passing subtests |
| Existing `tests/unit/test_source_integration.py` | **Collection error**, unchanged pre-existing missing OCR import |
| Canonical PA2 frontend | Locked dependencies installed; TypeScript + production build and cross-role browser smoke passed |
| Retained `/pa1.html` comparison | 26 routes, patient/HCP flow, persistence, escaping, search and five responsive widths passed |
| Relocated React PA1 app | Locked dependencies installed; TypeScript + production build; **7 Playwright tests passed** |
| NLP application launchers | Stateless extraction exit, persisted application startup, `/json` frontend DTO and normal exit passed |
| Source syntax and paths | 129 Python files parsed; source/data hashes and ignore rules verified |

DB tests used only existing marked loopback fixture databases
`msa_core_test_v4nlpresumechecks` and `msa_core_test_v4cleanupteam20261109checks`.
No bootstrap or schema redesign was performed. The existing tests create
synthetic records in these dedicated databases. Frontend dependencies, npm cache,
temporary browser profiles and reports remain local and ignored.

NLP evidence: `artifacts/nlp_mvp_v2/junit.xml`; Core DB evidence:
`artifacts/submission_db_results.json`; module evidence:
`artifacts/submission_modules.xml`; launcher evidence:
`artifacts/submission_launchers.json`. The Vision retry tests used dependencies
already present in `artifacts/nlp_python_deps`; no cloud inference was called.

## Remaining issues

`tests/unit/test_source_integration.py` imports `find_numbered_row_starters`,
which is absent from the existing committed OCR implementation. Both that source
and the test are byte-for-byte unchanged by this final cleanup. No test was
deleted or weakened to hide this mismatch. That legacy test file requires its
matching OCR implementation before it can collect.

Additional historical research/E2E suites require local `data/reference/`
provenance/index files and `data/samples/synthetic_pipeline.json` that are absent
from this checkout; they were not reconstructed, substituted or downloaded.
The passing Core/NLP suites exercise the existing Module 2/3 adapters separately.
LaTeX report binaries were retained and their moved source paths checked; no
report redesign/rebuild was attempted.

## Safe commit and push instructions

All changes remain unstaged. The exact list of changed paths for this cleanup is
`artifacts/submission_commit_paths.txt`, generated from the final Git status.
It includes the recovered Core/NLP prerequisites and tracked deletions, and
excludes datasets, runtime binaries, node_modules, caches, secrets and test output.
Review the remaining OCR issue before describing the complete submission as green.
Run the following from the repository root when ready; these commands were not executed:

```powershell
if ((git branch --show-current).Trim() -ne 'NLP-ChatBot') { throw 'Wrong branch' }
git status --short
git diff --check
if ($LASTEXITCODE -ne 0) { throw 'Working-tree validation failed' }
git --literal-pathspecs add --dry-run -A --pathspec-from-file=artifacts/submission_commit_paths.txt
if ($LASTEXITCODE -ne 0) { throw 'Staging preview failed' }
git --literal-pathspecs add -A --pathspec-from-file=artifacts/submission_commit_paths.txt
if ($LASTEXITCODE -ne 0) { throw 'Staging failed' }
git diff --cached --check
if ($LASTEXITCODE -ne 0) { throw 'Staged validation failed' }
git diff --cached --stat
git diff --cached
git commit -m "chore: standardize repository for project submission"
if ($LASTEXITCODE -ne 0) { throw 'Commit failed' }
git push --dry-run origin HEAD:NLP-ChatBot
if ($LASTEXITCODE -ne 0) { throw 'Push preview failed; do not force-push' }
git push origin HEAD:NLP-ChatBot
```

Stop if a command fails. A normal push will reject remote divergence; do not
force-push. No stash operation or destructive Git command is needed.
