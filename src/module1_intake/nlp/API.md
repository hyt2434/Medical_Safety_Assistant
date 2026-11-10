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
| `prepare_safety_snapshot(workflow_id, dataset_build=...)` | Create an existing Core snapshot from at least two non-negated confirmed/identified targets |
| `assess_snapshot(workflow_id, snapshot_id, dataset, request_key=...)` | Validate the exact current confirmed target set and run the existing Module 3 adapter |
| `answer_assessment(workflow_id, assessment_id, question)` | Retrieve an owned, current-target retained assessment and compose an attributed answer |

Optional `reference` wraps a published Core build. `medication_retriever` may use
the existing read-only Module 2 reference; `composer` may supply the existing
grounded composer. These options do not create alternate persistence stores.
Handoff DTOs are revalidated against Core rather than trusted as authorization.

## Capability limits

| Capability | Available behavior |
| --- | --- |
| Extraction/dialogue | WORKING within synthetic acceptance coverage; strict evidence can conservatively reject unusual wording |
| Application Help | WORKING from supported templates, including when extraction inference is unavailable |
| Owner records/history | WORKING owner-scoped reads; Q&A shows up to 16 of the latest 100 items/versions, with a bounded-display limitation |
| Medication reference | PARTIAL capability; Core REF provides candidates/provenance, not ingredient/strength/form facts. An existing Module 2 adapter supplies historical facts only for independently VERIFIED identity with retained hashes/locators and no quarantine/conflict |
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
See [README.md](README.md#run) for launch and verification commands, and
[ARCHITECTURE.md](ARCHITECTURE.md) for source/safety boundaries.
