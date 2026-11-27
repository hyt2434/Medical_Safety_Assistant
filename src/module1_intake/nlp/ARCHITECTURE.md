# NLP architecture and safety contracts

## Source map

```text
nlp/
  README.md                         Setup, launchers and regression tests
  ARCHITECTURE.md                   Layers, safety contracts and public boundaries
  API.md                           Host/frontend integration
  requirements.txt                 Runtime dependencies
  requirements-dev.txt             Runtime plus test dependencies
  models.py                        Shared raw-evidence, entry-view and handoff DTOs
  __init__.py                      Existing public package exports
  __main__.py                      python -m entry point, delegates to interfaces.cli
  understanding/
    __init__.py
    providers.py                   Qwen/mock extraction and safe bounded retries
    routing.py                     Intent completion and dialogue-act detection
    validation.py                  Source spans, slot roles and timing projection
  dialogue_management/
    __init__.py
    manager.py                     Context, questions, corrections, review, confirmation
    policy.py                      Intent-slot contracts and blocker policy
    fsm.py                         Existing Core V4 state transitions
  qa_pipeline/
    __init__.py
    contracts.py                   Queries, references, facts, retrieval results, answers
    structured.py                  Layer 1: help, Core REF, Module 2/3, owner records
    composition.py                 Layer 2: Qwen fact selection, validation and fallback
    pipeline.py                    Structured-first Q&A orchestration
    rag/
      __init__.py
      interface.py                 Retrieval protocol and explicit disabled fallback
      documents.py                 Manifest-backed corpus ingestion and local BM25
  integration/
    __init__.py
    persistence.py                 Existing Core repository/intake coordination
    handoff.py                     Confirmed Module 2 handoff and explicit Module 3 calls
  interfaces/
    __init__.py
    application.py                 Existing application DTOs and service wiring
    application_cli.py             Persisted terminal client
    interactive.py                 Stateless extraction terminal client
    cli.py                         Command-line argument handling

scripts/nlp/                       At repository root, outside the Python package
  application_ollama.ps1            Persisted application launcher
  interactive_ollama.ps1            Stateless extraction launcher
  test_mvp.ps1                      NLP/RAG/Voice regression launcher
  test_ollama.ps1                   Real-model extraction test launcher
```

Understanding depends on shared models, not dialogue, persistence or application
code. Dialogue coordinates understanding, Q&A and integration. The application
service wires these components. Integration never imports the application layer;
stateless extraction never imports PostgreSQL. The dialogue manager remains one
implementation, with its stateful operations together.

## Q&A layers

1. **Structured authorities:** `structured.py` reads published Core REF candidates,
   existing Module 2 reviewed facts, retained Module 3 assessments/findings, owner
   records/history and application-help templates. These reads create no personal
   exposure records or clinical findings. Missing sources produce
   UNAVAILABLE/UNASSESSED; permission errors propagate.
2. **Qwen:** understanding validates current-message evidence before completing
   intents. Composition selects/orders supplied fact IDs through `GroundedPlan`;
   the backend renders the original facts, references, coverage and limitations.
   Failed or invalid selection uses the deterministic template fallback. Required
   findings and coverage survive the 16-fact selection window. With no facts,
   composition never calls Qwen. Non-clinical messages retain supported help/task
   clarification; there is no unrestricted conversation endpoint.
3. **Document RAG:** `rag/documents.py` implements `LocalDocumentRetriever` over
   `data/rag/sources.csv` and the declared files under `data/rag/raw/`. It ingests
   page-preserving PDF text and English MedlinePlus XML summaries, chunks passages,
   and ranks them with local BM25 plus source/title/topic signals. Qwen can translate
   Vietnamese search terms and select supplied facts; evidence remains the original
   source text with locators, hashes, population limits and coverage. For two fixed
   textless-PDF sources, ingestion may fetch their allowlisted official HTML pages.
   `data/rag/index/corpus.json.gz` caches corpus-derived passages under a source
   signature; questions and model responses are not saved in that cache. There is
   no embedding service or vector database.

   `ApplicationService` supplies this retriever to `HybridQA`. Explicit document
   questions use `RetrievalQuery(kind='document')`; medication identity, interaction
   assessment and owner-record requests keep their structured paths. Failure of a
   structured source does not automatically fall through to document search.
   `rag/interface.py` retains the shared protocol and `DisabledDocumentRetriever`
   for explicitly disabled/default standalone configurations. Missing corpus or
   insufficient evidence returns the existing unavailable/limited answer.

Reference candidates, source medication IDs and DDInter mapping IDs are not
patient identity verification or interaction findings. Only an actual retained
Module 3 assessment can supply assessment-scoped findings. Missing findings or
incomplete coverage never establish safety. Reminders, patient summaries and HCP
sharing remain deferred to their owning services.

## Understanding and dialogue contracts

- `ADD_MEDICATION` is an intake candidate, including reported use and an existing
  prescription report; it does not authorize saving confirmed records.
  `record_request_raw` is an exact affirmative save-request prefix, or null for a
  report. Intent completion runs after schema and source validation, so extraction
  consumers and dialogue use the same routing semantics.
- Raw fields must come from the current source and the correct medication span.
  Strength, dose, frequency, duration and package quantity have distinct roles.
  Numeric strengths and supported Vietnamese number/unit phrases such as
  `năm trăm miligam` retain their original source span; tablet counts alone do
  not supply a strength and no numeric conversion replaces the reviewed words.
  Keep `2 hộp` as raw quantity; never calculate pills, schedules or daily doses.
  Corrections extract only new evidence and retain previous evidence/fields.
- Before strict validation, broad model evidence may be narrowed to a literal
  semicolon/newline clause only when each medication name maps uniquely to a
  distinct clause and every supplied raw field remains in that bounded span.
  No raw value is changed or borrowed, and existing bounded spans are retained.
  Unsupported, invented, duplicate and overlapping evidence still fails the
  unchanged validator. Explicit shared instructions such as `cả hai` or
  `mỗi thuốc` require per-medication restatement under the single-span DTO:
  the full message is retained, but no partial medication list is created.
- Preserve `timing_raw="sáng và tối"` and its raw dose in one administration group;
  the backend derives `timing_slots_raw=["sáng","tối"]`. Alternatives, ranges,
  meal-relative and complex timings stay combined. No clock times or frequency
  are inferred. Duration retains its source text, such as `trong 7 ngày`.
  Missing optional timing lists remain backward compatible. The generation grammar
  excludes derived slots and constrains uncertainty field names; all providers
  still undergo runtime evidence checks.
- Preserve negation and uncertainty. A model-supplied partial uncertainty list
  cannot suppress backend flags for present core slots. Negated entries remain
  visible in the handoff but do not enter current-exposure identification.
- Ask one targeted blocker per turn, initially and at most twice more. Missing
  name, strength or form can require clarification; dose, timing, duration and
  quantity remain optional. `không rõ` accepts unknown details on the current
  candidate only. Another/new drug still needs its own clarification. Stable item
  IDs retain unknown-slot decisions across corrections/resume; legacy global
  waivers are bounded to their existing items. Q&A never requires intake dose
  details just to retrieve a reference candidate.
- Reports outside a selected task may persist an unconfirmed draft, then ask its
  purpose. Side Q&A retains the intake draft and can restore a suspended entry/slot
  question with its retry count. Multi-drug corrections need an unambiguous target,
  such as `sửa thuốc 2 ...`; unresolved targets never become confirmed.

## Core V4 and confirmation

Existing `shared.db.CoreRepository` and `intake_adapter.persist_module1` remain the
only persistence authority. The 20-table Core schema and identity contract are
unchanged. `_owned`/`_all` reuse existing owner-scoped reads. Each repository
operation commits independently; no outer transaction wraps a dialogue turn.
Session advisory locks serialize turns on a workflow while leaving the connection
idle between operations. Use one connection per active request.

Workflows retain existing `MEDICATION_INTAKE`, `SAFETY_REQUEST`, `Q_AND_A` types.
Intake moves through COLLECTING/CLARIFYING, AWAITING_CONFIRMATION, and COMPLETED or
explicit cancellation. Side requests use existing SUSPENDED workflows with a
disposition; they do not imply a completed clinical action. Typed NLP turns use
TEXT inputs with `medication-entry.v4` payloads and the existing raw-field JSONB
extensions. Voice's non-retention policy records original ASR text and reviewed
NLP text as linked TEXT inputs with VOICE provenance. Original audio gets a
separate digest, not a fabricated retained-object locator. Core AUDIO is reserved
for genuinely retained objects. Manual forms use MANUAL inputs and the same
versioned review/confirmation boundary. No Core schema change is required.

## Voice review before the shared message flow

The common `module1_intake.api.transcribe_voice()` returns `raw_transcript` and
`confidence_score`. `ApplicationService.preview_voice()` binds that result to an
owned workflow/revision and persists an editable voice draft without running NLP
or creating a medication entry. The user sees the original transcript, can edit
it, and explicitly agrees to send the displayed draft. `submit_voice()` then
passes exactly that text through the same `send()` routing, grounding, extraction
and correction flow as a typed turn. Medication review/confirmation is a separate
step after extraction.

The message and interpreted TEXT payload retain `input_source=VOICE`, the raw and
edited text, language, confidence, draft ID and original `audio_input_id`. The
adapter retains an audio digest rather than audio bytes; the compatibility field
`audio_input_id` points to the original transcript TEXT input.
Empty/silent audio and ASR failure leave the previous draft, medication entries,
revision and displayed review intact for retry. NLP rejection retains the draft
for editing/resubmission. Owner, revision and draft ID checks reject stale drafts;
pending drafts must be submitted or discarded before medication confirmation.
The existing application CLI provides `/voice WAV`, `/voice-draft`,
`/voice-edit TEXT`, `/voice-send` and `/voice-cancel`. See
[the Voice API contract](API.md#voice-drafts-in-the-same-conversation).

## Medication confirmation

Review pins its display message, revision, exact entry IDs and PostgreSQL content
digests. Only normalized `xác nhận`/`tôi xác nhận` or the explicit confirmation
handler authorizes the latest displayed review. A predicted intent, `đúng rồi`,
stale revision, foreign owner or unreviewed input is insufficient. Per-entry keys
allow partial-confirmation retry; a completed API retry must reuse its request key.
Confirmation verifies transcription only. Corrections append immutable versions
and invalidate the old review; absent patch fields never erase prior fields.
`/revise` starts a new workflow after completion. Resume returns current messages
and state, including completion/cancellation.

The application explicitly calls confirmed Module 2 handoff, exact-target snapshot
creation, Module 3 execution and assessment retrieval through `integration/handoff.py`.
Those paths recheck owner, latest versions, digests, confirmation and exact target
sets. Inference and read-only Q&A cannot trigger clinical execution automatically.

## Canonical imports and public boundaries

The following abbreviate `module1_intake.nlp` as `nlp`:

| Removed root module | Canonical implementation |
| --- | --- |
| `nlp.providers`, `nlp.routing`, `nlp.validation` | Corresponding `nlp.understanding.*` |
| `nlp.dialogue` | `nlp.dialogue_management.manager` |
| `nlp.policy`, `nlp.fsm` | Corresponding `nlp.dialogue_management.*` |
| `nlp.persistence`, `nlp.handoff` | Corresponding `nlp.integration.*` |
| `nlp.qa`, `nlp.retrieval` | `nlp.qa_pipeline.structured`, including legacy contract/protocol exports |
| `nlp.hybrid_qa` | `nlp.qa_pipeline.pipeline`, including composition/answer exports |
| `nlp.application`, `nlp.application_cli`, `nlp.interactive` | Corresponding `nlp.interfaces.*` |
| `nlp.__main__` (retained entry point) | Imports `main` from `nlp.interfaces.cli`, without module aliasing |

The 14 root compatibility modules have been removed. Repository imports, CLI
test patches and checkpoint addresses now target the canonical modules. There
are no `sys.modules` aliases. External callers of a removed import must migrate
using this table. `python -m module1_intake.nlp` remains the supported CLI.

`nlp.interfaces.application` owns the backend/UI service API: `ApplicationService`
and the DTOs listed in its `__all__`. The HTTP adapter in
`apps/backend/api/routes/intake.py` already imports this module directly. UI
transport code should use that API, not the dialogue manager or Core store.

Package exports `Chatbot`, `Module2Handoff`, `MockProvider`, `OllamaProvider` remain
available; `Chatbot` stays lazy so extraction does not import PostgreSQL.
`models.py` owns NLP intents, understanding, reply and `EntryView`; its shared
medication/administration/confirmed-handoff names are the same class objects from
`shared.intake_contracts`. They are retained to preserve model identity and JSON
schemas. `EntryView` is also exposed in the application API. Classes already had
their canonical `__module__` before the alias removal; JSON/pickle contracts do
not require the removed modules.

The logger string `module1_intake.nlp.providers` and evidence locator
`module1_intake.nlp.qa.APP_HELP` deliberately remain stable identifiers. Neither
is a dynamic Python import; renaming them would alter logging configuration or
retained provenance. Internal symbol re-exports covered by the checkpoint still
reference their original classes/functions, without duplicate implementations.

All four PowerShell scripts resolve the repository from `scripts/nlp/`, use the
root `.venv`, set absolute source/repository paths, and restore process environment
variables. They work from other working directories. Tests write results to the
terminal; the launcher does not overwrite historical JUnit evidence.

## Verification and scope

Regression groups cover offline extraction, diagnostics, CLI, semantics,
application/policy, architecture, BM25 document retrieval, Voice review, real
models, and isolated PostgreSQL behavior. Architecture checks protect public
canonical exports, JSON/pickle type identity, schema fingerprints, acyclic
dependencies, evidence-only composition and the explicit disabled retriever.
Active document retrieval has its own RAG tests.
No duplicate test group has been established safe to remove. See
[README.md](README.md#regression-tests) for launchers.

Acceptance records have different scopes: the historical
[198-test NLP run](../../../artifacts/nlp_mvp_v2/junit.xml) includes real Qwen and
PostgreSQL cases; the [three Intake fixes](../../../artifacts/intake_three_fixes/RESULTS.md)
record 243 passed and three RAG opt-in skips without running PostgreSQL or a
Vietnamese WAV. The [Voice integration review](../../../artifacts/voice_manual_input/voice_chatbot_review.md)
also records the later synthetic Vietnamese WAV run, including Whisper's
`Panadol` to `Panadone` error. A newer count does not replace independent coverage.

The consolidated documentation replaces historical intent/timing, checkpoint and
handoff reports. Their current semantics, known provider failure/fix, regression
coverage, safety limits and integration rules are retained in these three docs.
Old test-count/timing narratives are not current acceptance evidence. Generated
reports, local transcripts, caches and environments remain ignored local artifacts.
