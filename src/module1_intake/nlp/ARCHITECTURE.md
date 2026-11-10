# NLP architecture and safety contracts

## Source map

```text
nlp/
  README.md                         Setup, launchers and regression tests
  ARCHITECTURE.md                   Layers, safety contracts and compatibility
  API.md                           Host/frontend integration
  requirements.txt                 Runtime dependencies
  requirements-dev.txt             Runtime plus test dependencies
  models.py                        Shared raw-evidence, entry-view and handoff DTOs
  __init__.py                      Existing public package exports
  __main__.py                      Existing python -m entry point
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
      interface.py                 Layer 3: retrieval protocol and disabled adapter
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
  application_ollama.ps1            Persisted application launcher
  interactive_ollama.ps1            Stateless extraction launcher
  test_mvp.ps1                      Full regression launcher
  test_ollama.ps1                   Real-model extraction test launcher
  application.py, application_cli.py, dialogue.py, fsm.py, handoff.py,
  hybrid_qa.py, interactive.py, persistence.py, policy.py, providers.py,
  qa.py, retrieval.py, routing.py, validation.py
                                   Compatibility forwards only
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
3. **Future RAG:** `rag/interface.py` defines `DocumentRetriever.retrieve(query)`
   returning the shared `RetrievalResult`. `DisabledDocumentRetriever` returns
   UNAVAILABLE without facts. Phase A never searches documents, even after a
   structured-source failure. No embeddings, vector database, corpus, ingestion or
   model download is implemented. Future adapters must independently verify their
   sources and preserve attribution, coverage and limitations.

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
  Keep `2 hộp` as raw quantity; never calculate pills, schedules or daily doses.
  Corrections extract only new evidence and retain previous evidence/fields.
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
disposition; they do not imply a completed clinical action. Inputs remain TEXT,
with `medication-entry.v4` payloads and the existing raw-field JSONB extensions.

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

## Compatibility

The following abbreviate `module1_intake.nlp` as `nlp`:

| Existing path | Canonical implementation |
| --- | --- |
| `nlp.providers`, `nlp.routing`, `nlp.validation` | Corresponding `nlp.understanding.*` |
| `nlp.dialogue` | `nlp.dialogue_management.manager` |
| `nlp.policy`, `nlp.fsm` | Corresponding `nlp.dialogue_management.*` |
| `nlp.persistence`, `nlp.handoff` | Corresponding `nlp.integration.*` |
| `nlp.qa`, `nlp.retrieval` | `nlp.qa_pipeline.structured`, including legacy contract/protocol exports |
| `nlp.hybrid_qa` | `nlp.qa_pipeline.pipeline`, including composition/answer exports |
| `nlp.application`, `nlp.application_cli`, `nlp.interactive` | Corresponding `nlp.interfaces.*` |
| `nlp.__main__` | `nlp.interfaces.cli`; the existing `python -m` command still dispatches `main()` |

These tiny files alias the canonical module through `sys.modules`, preserving
class/exception identity and monkeypatches without duplicating implementations.
They remain required by public import contracts, existing base/CLI tests and the
checkpoint export/schema checks. An internal search alone cannot establish that
external frontend/backend callers have stopped using a public path.

Package exports `Chatbot`, `Module2Handoff`, `MockProvider`, `OllamaProvider`, the
provider logger name and source locators remain stable. Shared `EntryView` lives
in `models.py` to avoid a retrieval-to-application dependency and is still exported
from `application`. New code should import each canonical owner directly.

## Verification and scope

All 169 meaningful tests remain: offline extraction, diagnostics, CLI, semantics,
application/policy, architecture, real model, and isolated PostgreSQL cases.
These groups test different boundaries; no equivalent duplicate test was proven
safe to remove. Five architecture checks protect aliases/exports, fingerprints of
46 public schema exports, acyclic dependencies, evidence-only composition and
disabled RAG. See [README.md](README.md#regression-tests) for commands and reports.

The consolidated documentation replaces historical intent/timing, checkpoint and
handoff reports. Their current semantics, known provider failure/fix, regression
coverage, safety limits and integration rules are retained in these three docs.
Old test-count/timing narratives are not current acceptance evidence. Generated
reports, local transcripts, caches and environments remain ignored local artifacts.
