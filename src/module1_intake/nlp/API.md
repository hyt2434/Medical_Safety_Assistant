# Application integration

## Host boundary

Construct `ApplicationService` with the existing authenticated `CoreRepository`
and one connection per active request. The server obtains `authenticated_owner`
from trusted identity, never request JSON or model output. CLI `-Owner` selects an
existing development identity only; the launcher does not create users.

```python
from shared.db import CoreRepository
from module1_intake.nlp.interfaces.application import ApplicationService, TurnRequest
from module1_intake.nlp.understanding.providers import OllamaProvider

repo = CoreRepository(connection, authenticated_owner=authenticated_user_id)
service = ApplicationService(repo, OllamaProvider('qwen3.5:9b'))
response = service.start()
response = service.send(TurnRequest(
    workflow_id=response.workflow_id,
    revision=response.revision,
    text='Vui lòng lưu Panadol 500mg, dạng viên nén.',
))
```

Existing imports from `module1_intake.nlp.application` remain valid. The host
supplies authentication and HTTP/transport handlers, serializes DTOs, and maps
permission/revision/validation errors to safe client responses. No HTTP server or
frontend is provided here. Do not expose DB/provider exception bodies to clients.

## Requests and responses

Strict request DTOs reject extra owner/user fields:

| DTO | Fields |
| --- | --- |
| `TurnRequest` | `workflow_id: UUID`, current `revision >= 1`, `text` of 1–12,000 characters; whitespace-only input is rejected by dialogue |
| `ConfirmationRequest` | `workflow_id: UUID`, current `revision`, UUID `request_key`, `explicit_confirmation: bool`; confirmation requires true and a displayed current review |
| `WorkflowActionRequest` | `workflow_id`, current `revision`, UUID `request_key`, `action: IDENTIFY / ASSESS`, `explicit_request: true`; requires the latest confirmed handoff |

Use `model_validate_json()` for incoming JSON, then `model_dump(mode='json')` or
`model_dump_json()` for responses. In Python DTO construction, use typed UUIDs.
Use the revision returned by each response; do not calculate it on the client.
Reuse the original confirmation request key when retrying an already completed
request. A stale revision requires reloading and reviewing the current workflow.

`ApplicationResponse` fields remain:

```text
assistant_message, workflow_id, revision, state, next_action, dialogue_act,
active_intents, missing_blockers, entries, capability_status, evidence_refs,
qa_results, action_authorized, authorization_scope, error_code
identification_results, assessment_id, snapshot_id, executed_action
```

Each `EntryView` includes `entry_version_id`, `item_id`, `content_digest`,
`confirmed`, `medication`, `slot_status`, and `identity_status=NOT_ASSESSED`.
Slot statuses are MISSING, PRESENT_RAW, AMBIGUOUS or USER_CONFIRMED. A confirmed
entry verifies transcription; it does not establish product identity or safety.
`action_authorized=True` only has TRANSCRIPTION_ONLY scope; otherwise scope is NONE.

For Q&A, inspect `qa_results` as well as `assistant_message`: an active intake may
redisplay its review after a side answer. Answers contain text, status, coverage,
evidence references, candidates, limitations and composition mode. Coverage and
source references are part of the response, not optional UI decoration.

`identification_results` contains the unchanged Module 2
`module2.medication_identity.v1` payloads plus `core_match_id` and
`core_match_status`. Each includes candidates, ingredients, all mapping rows and
targets, source/build identifiers, identity/mapping statuses, readiness and issues.
`VERIFIED` reference identity does not imply safety. A selected product may have
`REVIEW_REQUIRED` mappings, including multiple approved DDInter targets. Singular
IDs remain null for ambiguous mappings. `executed_action` reports actual execution,
independently of transcription authorization; `assessment_id` and `snapshot_id`
identify retained Core evidence.

## Service methods

| Method | Contract |
| --- | --- |
| `start(conversation_id=None, task=None)` | Generic dialogue; `task=Intent.ADD_MEDICATION` explicitly selects intake |
| `send(TurnRequest(...))` | Process the owner/revision-checked turn and return the application DTO |
| `resume(workflow_id)` | Reload owned state, latest message, entries, pending blockers and revision |
| `confirm(ConfirmationRequest(...))` | Confirm the exact current displayed transcription with idempotent request semantics |
| `revise(workflow_id)` | Start a new workflow over completed intake items; corrections append versions and require review |
| `records.list(history=False, limit=100)` | Owner-filtered latest entries or retained versions; limit must be 1–100 |
| `handoff(workflow_id)` | Return confirmed/latest raw entry IDs, digests and requested routes; identity is NOT_ATTEMPTED |
| `identify(workflow_id, dataset_build=...)` | Explicitly invoke existing Module 2 after revalidating confirmed evidence |
| `execute(WorkflowActionRequest(...))` | Explicit, revision-checked identification or optional safety assessment, returning a grounded `ApplicationResponse` |
| `prepare_safety_snapshot(workflow_id, dataset_build=...)` | Create an existing Core snapshot from at least two non-negated confirmed/identified targets |
| `assess_snapshot(workflow_id, snapshot_id, dataset, request_key=...)` | Validate the exact current confirmed target set and run the existing Module 3 adapter |
| `answer_assessment(workflow_id, assessment_id, question)` | Retrieve an owned, current-target retained assessment and compose an attributed answer |

Optional `reference` wraps a published Core build. `medication_retriever` may use
the existing read-only Module 2 reference; `composer` may supply the existing
grounded composer. These options do not create alternate persistence stores.
Handoff DTOs are revalidated against Core rather than trusted as authorization.

The confirmed medication/entry/handoff DTOs are owned by
`shared.intake_contracts`; existing `nlp.models` imports re-export the same
classes with unchanged schemas. The shared
`shared.db.intake_adapter.build_confirmed_handoff(repo, workflow_id)` now builds
the DTO for any Core input source, and the NLP `build_handoff` wrapper delegates
to it. No NLP extraction/dialogue implementation is required by Module 2.
Core intake supports `TEXT`, `IMAGE` and `MANUAL` with the same review and
confirmation requirements. Optional aligned `item_locators` on `persist_module1`
retain caller-supplied page/box/form evidence through existing item origins.

Module 2 results add `input_evidence`, separate from reference provenance: actual
input modality/payload/digest, extraction metadata and original/current source
links are retained. Missing correction provenance stays explicitly unknown.
See the [Module 2 source contract](../../module2_medications/README.md#source-independent-module-1-boundary)
for exact fields, future OCR/manual integration steps and outstanding team
agreements. Those unfinished interfaces are not assumed to exist. Review
adapters must check workflow revision and displayed digests before confirming;
the unchanged handoff itself contains no workflow/revision token.

## Confirmed identification and optional assessment

Configure the trusted service with `dataset_build=<published Core hash>` and,
for safety, `dataset=<existing Module 3 dataset>`. `reference.build` can supply
the default build. The application and legacy NLP handoff now delegate to
`module2_medications.identify_confirmed`, replacing the shared literal matcher.
Module 2 retains owner/intake/latest/digest/confirmation checks and uses the
existing shared Core adapter to persist matches.

```python
from uuid import uuid4
from module1_intake.nlp.interfaces.application import WorkflowActionRequest

# response is the result of explicit owner confirmation, with the current revision.
response = service.execute(WorkflowActionRequest(
    workflow_id=response.workflow_id, revision=response.revision,
    request_key=uuid4(), action='IDENTIFY', explicit_request=True))

# A SEPARATE explicit request; confirmation and identification do not assess safety.
response = service.execute(WorkflowActionRequest(
    workflow_id=response.workflow_id, revision=response.revision,
    request_key=uuid4(), action='ASSESS', explicit_request=True))
```

Safety uses existing Core snapshots and the Module 3 adapter for at least two
non-negated, confirmed targets. It retains unresolved products and every approved
mapping alternative, with loaded coverage and applicability limitations. Missing
findings never establish safety. The trusted host may configure
`data_context='SYNTHETIC_TEST'` for the existing marked synthetic fixture; the
default is `PATIENT`. This is not a client DTO field or model-controlled value.

Completed workflows remain immutable. Responses are retained on existing
owner-scoped conversation messages; matches/snapshots/findings use existing Core
tables. Reusing an action request key returns its retained response; changing the
action, build, data context or assessment dataset coverage under that key is
rejected. Actions do not change the completed-workflow revision. Resume rechecks
current confirmed entry versions before displaying retained results. Corrections
create a new intake workflow/version and invalidate stale evidence.

After confirmation, `send(TurnRequest(...))` accepts bounded explicit requests
such as `Nhận diện các thuốc đã xác nhận` and
`Kiểm tra tương tác các thuốc đã xác nhận`. Qwen performs intent understanding;
model intent alone cannot authorize execution. Negations, hypothetical questions,
quoted commands and independently named drug targets do not trigger assessment.
Use the explicit DTO or CLI commands for other wordings. Pre-confirmation requests
remain in the existing clarification workflow and are never automatically
executed after confirmation.

Unresolved identities return `REVISE_AND_RECONFIRM` and targeted blockers. A raw
answer to an identity blocker or `sửa thuốc 1 ...` enters the existing revision,
slot-filling and review workflow. Corrected details require fresh confirmation
and a new explicit identification request. Multiple mapping targets remain an
applicability limitation, without a guessed ID. Follow-up questions about the
confirmed list use retained identity or assessment facts without rerunning them.

Identity/candidate/component statuses and safety coverage/findings are required
facts in the existing grounded composer. Qwen selects/orders fact IDs; it cannot
author identities, DDInter IDs, clinical findings or safety claims. Inference
failure retains the existing deterministic fallback.

## Capability limits

| Capability | Available behavior |
| --- | --- |
| Extraction/dialogue | WORKING within synthetic acceptance coverage; strict evidence can conservatively reject unusual wording |
| Application Help | WORKING from supported templates, including when extraction inference is unavailable |
| Owner records/history | WORKING owner-scoped reads; Q&A shows up to 16 of the latest 100 items/versions, with a bounded-display limitation |
| Medication reference/identification | PARTIAL capability; explicit confirmed identification uses Module 2's published Core product/component/ingredient/mapping evidence. Before identification, Core retrieval remains candidate-only. Legacy historical facts retain their independent review/hash/locator guards |
| Safety | PARTIAL capability; only explicit existing Module 2/3 execution and retained assessment evidence. Missing sources or targets yield UNAVAILABLE/UNASSESSED; incomplete results never imply safety |
| Reminders, patient summaries, HCP sharing | DEFERRED; no connected Module 4/5 execution or invented schedule |
| Document RAG | UNAVAILABLE; the future retrieval interface is inactive |
| Production authentication/transport | Host responsibility |

Capability status describes the configured service; individual Q&A results may be
UNAVAILABLE or PARTIAL. Clinical recommendations, prescribing, dose changes,
treatment cessation and emergency procedure generation are outside this MVP.
The existing synthetic Module 3 fixture proves orchestration and attribution,
not production catalog coverage or clinical validity.

## Development clients

`application_ollama.ps1` uses this service/DTO contract. Commands are `/new`,
`/resume UUID`, `/revise`, `/handoff`, `/identify`, `/assess`, `/safety-answer`,
`/json`, `/exit` and `/quit`. `interactive_ollama.ps1` is a separate stateless
extraction client with no DB imports; it does not test this application contract.
`/identify` and `/assess` display grounded source-backed results and update
`/json`; `/resume` restores retained results. `/assess` remains a separate explicit
request; `/safety-answer` only reads an existing applicable assessment.
See [README.md](README.md#run) for launch and verification commands, and
[ARCHITECTURE.md](ARCHITECTURE.md) for source/safety boundaries.
