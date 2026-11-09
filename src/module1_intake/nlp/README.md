# Module 1 NLP chatbot MVP

Vietnamese medication intake with reviewable raw evidence. Confirmation verifies
the transcription, not product identity or clinical safety. The chatbot never
prescribes, changes/stops treatment, generates first aid, or invents DDI results.

Architecture, persistence contracts, specification mismatches and boundaries are
documented in [CONTRACT_NOTES.md](CONTRACT_NOTES.md).

## Install and run

From the repository root, Python 3.10+ and installed NLP dependencies are required.
Persisted dialogue additionally requires an already provisioned Core V4 database
with the existing identity contract. The CLI never bootstraps a DB, imports
reference data, creates users, or downloads an LLM.

### Interactive real Ollama extraction (no PostgreSQL)

With local Ollama running, `qwen3.5:9b` installed and the repository `.venv` ready:

```powershell
& .\src\module1_intake\nlp\interactive_ollama.ps1
```

Type Vietnamese medication sentences repeatedly, then `/exit` to quit (EOF and
Ctrl+C also exit). For example:

```text
Tôi đang uống Panadol 500mg, mỗi sáng 1 viên. Bác sĩ kê 2 hộp.
Có lẽ tôi đang dùng Vitamin C, không nhớ hàm lượng.
/exit
```

This is **stateless NLP extraction testing**: each sentence receives an empty
context. It does not test dialogue, confirmation, persistence or medication safety.
It requires no owner, `CORE_DB_DSN`, database server or PostgreSQL driver imports.
The existing `OllamaProvider`, current system prompt, Pydantic models and strict
source evidence validation are reused. Output shows validated intent evidence,
medication evidence, every raw slot, administrations, missing/unreported data
slots, uncertain fields and ambiguity. Missing slots are not mandatory-field or
safety judgments. Validated source text is displayed in the local terminal;
prefer synthetic examples. Rejected output is never displayed: errors show safe
categories, attempts and HTTP status, then the next input can be tried.

`ADD_MEDICATION` means an intake candidate, including a patient medication report
or report of an existing prescription. It does not mean permission to save.
`record_request_raw` displays an exact recognized explicit save/add request prefix
when present; neither value authorizes confirmation. Combined timing evidence is
retained (for example `timing_raw="sáng và tối"`) and `timing_slots_raw` exposes
the two literal dayparts without choosing times or duplicating dose instructions.
Alternatives and ranges remain combined. See [contract semantics](CONTRACT_NOTES.md)
and [real Qwen before/after evaluation](INTENT_TIMING_REVIEW.md).

The launcher restores its environment changes and accepts
`-Model 'qwen3.5:9b' -TimeoutSeconds 120`.
Direct CLI equivalent after setting `PYTHONPATH=./src`:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m module1_intake.nlp --nlp-test --model qwen3.5:9b
```

### Persisted chatbot

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r src/module1_intake/nlp/requirements.txt
$env:PYTHONPATH = (Resolve-Path ./src).Path
$env:CORE_DB_DSN = Read-Host 'Existing development Core V4 DSN'
$owner = Read-Host 'Existing development owner UUID'
.\.venv\Scripts\python.exe -X utf8 -m module1_intake.nlp --provider mock --owner $owner
```

Demo sequence (mock grammar deliberately limited; scripted mocks cover wider tests):

```text
Tôi đang uống Panadol
500mg, dạng viên nén
sửa thuốc 1 thành Panadol 250mg
cách xác nhận
xác nhận
/revise
sửa thuốc 1 thành Panadol 500mg
xác nhận
/quit
```

For multiple drugs separate clauses with `;`. Only new explicit fragments are
extracted. Use `--workflow <printed-workflow-uuid>` to resume and `/quit` to exit.
The mock supports simple raw names, strengths, forms, count doses, schedules,
durations and package quantities; it is not a Vietnamese accuracy benchmark.

For Ollama, start your local Ollama server and install a model separately. Then:

```powershell
ollama list
$env:NLP_OLLAMA_MODEL = Read-Host 'Installed model tag from ollama list'
$env:NLP_OLLAMA_URL = 'http://127.0.0.1:11434'
$env:NLP_OLLAMA_TIMEOUT = '60'
.\.venv\Scripts\python.exe -X utf8 -m module1_intake.nlp --provider ollama --owner $owner
```

Ollama uses `/api/chat`, JSON schema `format`, `stream=false`, `think=false`,
temperature zero, no proxy inheritance and no redirects. Only loopback HTTP endpoints are accepted.
See [Ollama structured outputs](https://docs.ollama.com/capabilities/structured-outputs).
Thinking is explicitly disabled for extraction; see [Ollama thinking controls](https://docs.ollama.com/capabilities/thinking).
On local Ollama 0.40.15 with `qwen3.5:9b`, the original request used the default
thinking mode and returned HTTP 200 with `done_reason="length"`, empty content,
and 2,966 generated tokens. Pydantic then rejected the empty content as invalid
JSON. The same Unicode-verified synthetic input and unchanged schema passed
schema and evidence validation with only `think=false` added (45.4s failed vs
3.5s successful on that warm local run). This was neither a connectivity failure
nor a schema incompatibility; no evidence checks were relaxed.

Real uncertainty testing also found that a nonempty model `uncertain_fields`
list could suppress the validator's conservative flags for present core slots.
Validation now unions those backend flags with the model list whenever explicit
uncertainty is present, rather than trusting an incomplete model annotation.

The provider now rejects incomplete envelopes and empty content before parsing.
`understand()` retains bounded retries and raises `InferenceError` with a safe
`.category`, `.http_status` and `.diagnostics` tuple (category, attempt number,
HTTP status only). Categories distinguish connectivity, timeout, HTTP status,
HTTP response/envelope, incomplete response, empty response, response size,
JSON syntax, Pydantic schema, evidence and other provider errors. Warning logs
contain only these allowlisted codes and numbers. Exceptions, response bodies,
thinking, source text, context and Pydantic input/error locations are never
included in diagnostics or logged by this module. The chatbot continues to ask
for clarification/manual input on failure; inference never authorizes medication
changes or confirmation.

## Tests

Offline tests require no DB, model, download, or paid API:

```powershell
$env:PYTHONPATH = (Resolve-Path ./src).Path
.\.venv\Scripts\python.exe -X utf8 -m pytest -q tests/unit/test_nlp.py tests/unit/test_nlp_diagnostics.py tests/unit/test_nlp_interactive.py tests/unit/test_nlp_semantics.py
```

Run real Qwen extraction separately with one PowerShell command from the repository
root (existing `.venv`, dependencies, local Ollama and downloaded model required):

```powershell
& .\src\module1_intake\nlp\test_ollama.ps1
```

This runs `tests/integration/test_nlp_ollama.py` with real local inference on
synthetic text only: Panadol 500mg, both dose/timing orders, prescribed 2 hộp,
two medications, missing fields, uncertainty, negation, a context-only name in a
follow-up, and an actual missing-model HTTP 404. It also checks prescription
reports versus explicit record requests, combined dayparts versus alternatives,
and information questions. It accesses no database and does not install/download
models. Tests require valid JSON, strict Pydantic types,
exact source grounding, separate drug evidence and correct expected slots. The
script restores its environment changes and fails if checks fail. Optional script
parameters are `-Model 'qwen3.5:9b' -TimeoutSeconds 120`. These tests skip by
default unless `NLP_RUN_REAL_OLLAMA=1`; mocked HTTP tests establish no real model
inference or clinical accuracy. Synthetic extraction checks are not a clinical
accuracy benchmark.

Real PostgreSQL tests default to skip. They require a separate loopback, marked
database named `msa_core_test_v4nlp<suffix>checks`; `msa_core_test_v4checks` and
all other names are rejected before any connection/bootstrap. To create a new
isolated synthetic fixture database using the EXISTING V4 bootstrap helper:

```powershell
$env:NLP_TEST_DSN = 'host=127.0.0.1 port=55432 dbname=msa_core_test_v4nlplocalchecks user=core_fixture_admin'
$env:NLP_TEST_BOOTSTRAP = '1'
.\.venv\Scripts\python.exe -X utf8 -m pytest -q tests/unit/test_nlp.py tests/integration/test_nlp_v4.py
Remove-Item Env:NLP_TEST_BOOTSTRAP
```

Bootstrap applies existing immutable V4 migrations to this isolated database and
creates test-only identity fixtures there through the existing helper. There are
no reference imports or writes to an existing identity deployment. Synthetic test
records are retained in the marked database for inspection. Do not use a shared
DSN. For an already bootstrapped NLP fixture DB omit `NLP_TEST_BOOTSTRAP`.

The DB tests exercise actual JSONB/enum/owner guards, raw quantities, displayed
PostgreSQL hashes, immutable confirmed history, corrections, process resume and
partial-confirmation retry. Unit tests use a repository spy solely as a test double.
The PostgreSQL tests use mock inference. Real medication verification, broader
LLM quality and end-to-end Module 2/3 behavior require separate evaluation and
are not claimed.

Known limits: conservative span/regex rules can reject valid unusual phrasing;
an exact source substring is evidence of transcription, not proof of correct
semantic interpretation. Complex abbreviation resolution, clinical interpretation,
automatic retry of a whole turn after arbitrary persistence failures, source-slot
deletion, external reference sources, RAG, fine-tuning, summaries, HCP sharing,
symptom diagnosis and emergency instruction generation are outside this MVP.
