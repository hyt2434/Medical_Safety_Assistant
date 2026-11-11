# NLP Chatbot MVP V2

Vietnamese medication intake and structured-first Q&A using local Ollama/Qwen and
the existing Core V4 repository. Confirmation verifies transcription only, never
product identity or clinical safety. Missing evidence never becomes a model-authored
medical answer.

| Document | Purpose |
| --- | --- |
| [Architecture](ARCHITECTURE.md) | Folder map, responsibilities, compatibility and safety contracts |
| [Application API](API.md) | Frontend DTOs, host integration, service methods and capability limits |
| [V2 design input](../../../docs/requirements/NLP_CHATBOT_MVP_DESIGN_V2.txt) | Original requirements; the implemented Core V4 contract takes precedence |

## Setup

Run commands from the repository root. Python 3.10+, local Ollama with an installed
`qwen3.5:9b`, and an existing development Core V4 deployment are needed for the
persisted application. Stateless extraction and offline tests need no database.

```powershell
# New checkout: create the environment, then install development requirements.
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r .\src\module1_intake\nlp\requirements-dev.txt
$env:NLP_OLLAMA_URL = 'http://127.0.0.1:11434'
```

`requirements.txt` contains the three runtime packages: Pydantic, HTTPX and psycopg.
`requirements-dev.txt` adds pytest. No embeddings, paid APIs or extra model packages
are required. Application/extraction launchers reuse `.venv`; they never install
packages, download models, bootstrap a database, create users or import reference
data. Test-only bootstrap is an explicit option described below.

## Run

Stateless real-Qwen extraction:

```powershell
& .\src\module1_intake\nlp\interactive_ollama.ps1 -Model 'qwen3.5:9b' -TimeoutSeconds 120
```

Each input has an empty context. This tests extraction/validation only, without
dialogue, confirmation or persistence. Enter `/exit`, EOF or Ctrl+C to finish.

Persisted application:

```powershell
$nlpDsn = Read-Host 'Existing isolated development Core V4 DSN'
$nlpOwner = Read-Host 'Existing synthetic identity.users UUID in that database'
& .\src\module1_intake\nlp\application_ollama.ps1 `
    -Dsn $nlpDsn -Owner $nlpOwner -Model 'qwen3.5:9b' -TimeoutSeconds 120
```

`-Owner` must identify an existing development user; generating an arbitrary UUID
does not create that user. In the marked NLP test database, existing synthetic
identities can be inspected with `SELECT id FROM identity.users ORDER BY id;`.
Production hosts supply their authenticated owner as described in [API.md](API.md).

At `app>`, enter one line at a time:

```text
Tôi được kê 2 hộp Panadol 500mg.
Thêm vào danh sách; dạng viên nén.
Sửa thuốc 1 thành Panadol 250mg.
cách xác nhận
/json
xác nhận
/handoff
/exit
```

Separate multiple drug clauses with `;`. Review every raw field before confirming.
Use `/new` for another workflow, `/resume UUID` to restore an owned workflow, and
`/revise` after completion to open corrections without changing confirmed history.
`/json` shows the current frontend DTO. `-Workflow UUID` resumes at launcher startup.

Optional launcher arguments `-ReferenceBuild`, `-Module2Reference`, and `-DdiIndex`
connect existing published Core REF, read-only Module 2 reference and Module 3 index
respectively. `/identify`, `/assess`, and `/safety-answer` explicitly use those
services after the required guards. Without the needed sources they report
UNAVAILABLE; they never infer safety from a mapping ID or absent findings.

The application now invokes `module2_medications.identify_confirmed` with the
unchanged confirmed Module 1 DTO. A completed conversation can continue with:

```text
Nhận diện các thuốc đã xác nhận
/json
Kiểm tra tương tác các thuốc đã xác nhận
/safety-answer
```

`/identify` and `/assess` provide the same explicit actions. Identification shows
product candidates, components, mapping coverage and source/build evidence with
`VERIFIED`, `REVIEW_REQUIRED` or `UNRESOLVED` statuses. Confirmation and
identification never start safety automatically. Assessment creates the existing
Core snapshot and invokes the existing Module 3 adapter only on explicit request.
Partial coverage and multiple targets remain limitations, without a safety claim.

For ambiguous or unmatched identities, provide the requested label detail or use
`sửa thuốc 1 ...`; the existing revision/slot-filling workflow creates a corrected
version and requires confirmation again. Results are retained on existing
owner-scoped conversation messages; completed workflows remain immutable. Qwen
understands requests and selects backend fact IDs for responses. Identities and
findings are never taken from model knowledge.

The confirmed medication DTOs are now owned by `shared.intake_contracts`, with
unchanged NLP aliases/schemas. Chatbot, future OCR and manual adapters share
`build_confirmed_handoff` and the same Core verification boundary; Module 2 no
longer imports NLP's store/models. See the
[three-source integration contract](../../module2_medications/README.md#source-independent-module-1-boundary)
for source metadata, corrections, review requirements and team agreements still
needed for the unfinished OCR/manual interfaces.

The original development CLI remains available with `PYTHONPATH=./src`:
`python -m module1_intake.nlp --provider mock --owner <existing-uuid>` and
`python -m module1_intake.nlp --nlp-test`. Persisted mode also needs `CORE_DB_DSN`.
The mock grammar is intentionally limited; it is not an NLP accuracy benchmark.

## Regression tests

```powershell
# Offline: no database, real model, download or paid API.
& .\src\module1_intake\nlp\test_mvp.ps1 -Dsn ''

# Real Qwen extraction only; no PostgreSQL.
& .\src\module1_intake\nlp\test_ollama.ps1 -Model 'qwen3.5:9b' -TimeoutSeconds 120

# Complete suite, using the already provisioned isolated NLP fixture database.
$nlpTestDsn = 'host=127.0.0.1 port=55432 dbname=msa_core_test_v4nlpe2e20261111checks user=core_fixture_admin connect_timeout=5'
& .\src\module1_intake\nlp\test_mvp.ps1 `
    -Dsn $nlpTestDsn -RealOllama -Model 'qwen3.5:9b'
```

The full suite requires the existing local PostgreSQL server and installed model.
For the provisioned real-reference database, exact E2E commands and a verified
real-Qwen manual conversation, see the
[Module 1–3 real-data test guide](../../module3_interactions/README.md#reproduce-the-real-data-e2e-run).
Only loopback, marked databases named `msa_core_test_v4nlp<suffix>checks` are
accepted. The marker is `Medication Safety Assistant Core V4 isolated test`.
`msa_core_test_v4checks` and all shared/production databases are excluded by the
test guard before connection/bootstrap. For a new synthetic fixture only, the
same launcher accepts `-Bootstrap` and reuses the existing Core test helper.
Omit `-Bootstrap` for an already provisioned database. Test fixture users and
records stay in the dedicated NLP database.

`-Dsn` enables PostgreSQL tests; `-RealOllama` sets `NLP_RUN_REAL_OLLAMA=1` for real
inference, including combined Qwen/DB cases. Launchers restore their environment
changes. Reports go to ignored `artifacts/nlp_mvp_v2/junit.xml`:

```powershell
[xml]$nlpReport = Get-Content -Raw .\artifacts\nlp_mvp_v2\junit.xml
$nlpReport.testsuites.testsuite | Select-Object tests,failures,errors,skipped,time
```

Original V2 acceptance coverage: **142 offline**, **11 PostgreSQL with mock extraction**,
**2 combined real-Qwen/PostgreSQL**, and **14 real-Qwen extraction** tests: **169**
in total. Offline-only runs intentionally skip the other 27. Tests cover raw
evidence, source timing, safe errors, owner/revision/digest gates, immutable
corrections, side questions, resume, idempotent confirmation, grounded Q&A and the
existing explicit Module 2/3 adapters. Five architecture checks protect aliases,
46 captured public schema exports, dependency boundaries and inactive RAG.
Synthetic engineering tests do not establish clinical validity or model accuracy.

Focused application/Module 2 tests (existing published four-product Core fixture;
no database creation or reference import):

```powershell
$env:PYTHONPATH='src'
$env:PYTHONDONTWRITEBYTECODE='1'
$env:NLP_TEST_DSN='host=127.0.0.1 port=55432 dbname=<existing-marked-NLP-test-db> user=<test-user>'
$env:NLP_RUN_REAL_OLLAMA='1'
$env:NLP_OLLAMA_TIMEOUT='120'
$env:NLP_SAVE_CLI_TRANSCRIPT='1' # Optional, synthetic acceptance artifact only.
./.venv/Scripts/python.exe -X utf8 -m pytest tests/unit/test_nlp_module2_flow.py tests/integration/test_nlp_module2_flow_v4.py -q
```

The real-Qwen CLI test exercises extraction → clarification → confirmation →
explicit identification → explicit assessment → grounded response through
`run_application`, PostgreSQL and the existing Module 3 adapter. The optional
transcript is `artifacts/nlp_module2/cli_conversation.txt`. Its invented products
and interaction rows validate orchestration, not clinical truth. See
[API.md](API.md#confirmed-identification-and-optional-assessment) for action DTOs,
retry behavior, coverage and exact-target guards.

The integration adds action/clarification/grounding regressions and preserves all
original V2 schema properties; the application response gains additive result
fields. A real-Qwen regression also exposed an omitted explicit duration. The
existing source validator now preserves one unambiguous `trong N ngày`/`liên tục
N ngày` span from that medication's evidence when omitted, while missing,
alternative and ranged durations remain unknown. This is raw transcription, not
a treatment recommendation.

Verified on 2026-11-10: **166 offline NLP tests**, **15 PostgreSQL tests with mock
extraction**, and **17 real-Qwen tests** passed. Together with **49 Module 2
unit/approved-data/PostgreSQL checks**, the combined run passed **247 tests**.
The real CLI transcript shows source-backed identities, both retained DDInter
alternatives, an explicit assessment, original synthetic findings and partial
coverage. Missing legacy `data/reference/` evidence still limits the separate
historical research suites; the approved CSV projection checks remain independent.

## Diagnostics and limits

Ollama uses loopback HTTP `/api/chat`, JSON schema output, `think=false`,
`stream=false`, temperature zero, no proxy inheritance and no redirects. Thinking
must stay disabled: earlier Qwen runs exhausted generation on thinking and returned
empty content. Incomplete envelopes, truncated output, invalid schemas and
ungrounded spans remain rejected.

`InferenceError` exposes safe category, attempt and HTTP status metadata only.
Categories distinguish connectivity, timeout, HTTP status/envelope, incomplete or
empty response, excessive size, JSON, schema, evidence and provider failures.
Logs never include patient text, context, thinking, raw responses or exception
bodies. On failure, use clarification or the host's manual-entry route; inference
does not authorize writes or medication changes.

Span/regex rules can conservatively reject unusual phrasing. Source-slot deletion,
whole-turn recovery after arbitrary partial persistence failure, production HTTP
authentication, candidate-resolution UI, clinical advice, reminders/HCP/summary
execution and Phase B document retrieval remain outside this MVP.

Keep local environments, secrets, caches, reports and test artifacts out of Git.
All canonical modules, compatibility forwards, tests, contract fingerprints and
four PowerShell launchers are maintained source.
