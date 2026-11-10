# Medication Safety Assistant

Vietnamese medication intake, reference lookup and interaction assessment. Intake
confirmation verifies transcription; it does not establish medication identity or
clinical safety.

| Path | Responsibility |
| --- | --- |
| `apps/frontend/` | Canonical TypeScript/Vite PA2 application; PA1 comparison entry retained. |
| `src/module1_intake/` | Intake adapters, OCR and the layered NLP MVP V2. |
| `src/module2_medications/` | Medication identification and reference services. |
| `src/module3_interactions/` | Interaction assessment and official-source adapters. |
| `src/module4_hcp/`, `src/module5_reminders/` | Existing package contracts for future HCP/reminder services. |
| `src/shared/` | Shared intake contracts, import utilities and Core V4 application adapters. |
| `db/` | Canonical Core Database V4 migrations, management tools, contracts and DB tests. |
| `data/` | Approved original/processed medication data and documentation; preserve source bytes. |
| `docs/` | Project requirements, design and management; `docs/pa/` holds submission sources and deliverables. |
| `tests/` | Unit, integration and end-to-end coverage; DB-specific tests remain in `db/tests/`. |
| `scripts/` | Shared setup, data provisioning, CLI and test utilities. |
| `artifacts/` | Ignored local runtimes, databases, caches, manifests and development evidence. |

Start with the [NLP setup and launchers](src/module1_intake/nlp/README.md),
[frontend DTO/API contract](src/module1_intake/nlp/API.md), and
[Core V4 setup](db/README.md). The NLP implementation keeps Hybrid Q&A Phase A
and an inactive RAG Phase B interface. Compatibility modules forward to the
layered implementation.

Run the [canonical PA2 frontend](apps/frontend/README-PA2.md) with `npm ci` and
`npm run dev` from `apps/frontend/`. The original team-authored
[React PA1 prototype](docs/pa/pa1/react-prototype/README.md) remains independently
runnable with its unique speech/chat behavior, assets and tests. Historical UI
implementations under `docs/pa/` belong to their submissions. No backend API
application exists in this branch; reusable Python business modules live only in
root `src/`. Reports build from their own directories
and use canonical assets under `docs/design/` and `docs/pa/pa1/ui-prototype/screenshots/`.
Historical 35/64-table database diagrams describe earlier designs; Core V4 lives in `db/`.
`src/shared/schema.sql` is the separate SQLite DAV import staging schema.

Offline NLP regression command, from the repository root with `.venv` ready:

```powershell
& ./src/module1_intake/nlp/test_mvp.ps1 -Dsn ''
```

Persisted tests require an explicitly marked isolated database. Keep local DSNs,
credentials, environments and runtime evidence out of Git. Existing CSVs under
`data/datasets/` stay local; already tracked approved CSVs remain tracked.
See the [cleanup verification and known blockers](docs/management/repository-cleanup-2026-11-10.md).
