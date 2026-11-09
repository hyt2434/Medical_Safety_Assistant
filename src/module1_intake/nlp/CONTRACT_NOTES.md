# Core V4 integration decisions

## Architecture and existing interfaces

| File | Responsibility |
| --- | --- |
| `models.py` | Strict Pydantic inference models and typed confirmed Module 2 DTO |
| `providers.py` | Loopback Ollama JSON-schema inference; deterministic/scripted mocks; bounded retries |
| `validation.py` | Exact source spans, medication-local evidence, slot roles, negation/uncertainty |
| `routing.py`, `fsm.py` | Vietnamese intent cues, multi-intent dependency routing, V4 state edges |
| `dialogue.py` | Clarification, context, corrections, displayed review and explicit confirmation |
| `persistence.py` | Coordination of existing Core repository and intake adapter |
| `handoff.py` | Confirmed entry DTO and explicit adapter call to Module 2 |
| `qa.py` | Application help and bounded Core reference candidate retrieval |
| `__main__.py` | Local development CLI, including persisted workflow resume |

All runtime writes use `shared.db.CoreRepository` and `intake_adapter.persist_module1`.
No alternate storage, DB migration, or change to other modules is required.
The existing `_owned`/`_all` read helpers are reused because Core currently has no
public workflow/entry retrieval API. Core remains authoritative for ownership,
transactions, consecutive immutable versions, JSONB validation and hashes.
Each repository operation commits independently, as required by Core; no outer
transaction wraps a turn. Session advisory locks serialize chatbot turns on one
workflow while leaving the connection idle between operations. Revision checks
reject stale clients. Use one connection per active request; do not share it
between concurrent requests. Other writers must continue to honor Core guards.

The model receives the current message and structured draft only. It cannot
confirm, select a product, create an assessment, or generate the user-facing
answer. Malformed/ungrounded inference is retried at most twice by default,
then recorded as a failed extraction with retained input and a safe error code.
Rejected raw model responses and exception bodies are never shown or stored.

## Intent and administration semantics

`ADD_MEDICATION` means a **medication intake candidate**, including reported use,
a report of an existing prescription, and an explicit request to record medication
information. It is not a claim that the medicine is being taken, and is not an
authorization to save or confirm records. A prescribed package quantity alone does
not establish a dose or a current regimen. Negation and uncertainty remain raw
evidence on the medication.

`IntentCandidate.record_request_raw` distinguishes a recognized explicit record
request (for example, `Vui lòng lưu`) from a report (`null`). It must be an exact
source span from an affirmative request prefix. Questions, negation and reported
prescribing cannot supply this marker. Detection is deliberately conservative;
an absent marker confers no authorization. Schema/evidence validation runs before
`routing.complete_intents` exposes the same cue/fallback semantics to both
`understand()` consumers and the chatbot. Information questions and requests for
new prescriptions retain their separate routes.

Full chatbot intake may persist **unconfirmed drafts**, as before. Neither an
intake intent nor a save-request marker bypasses missing-field clarification,
displayed review, owner/revision/digest guards, or explicit confirmation. No new
FSM state, command, workflow type, or persistence action is introduced.

An `Administration` retains `timing_raw` and `dose_raw` and adds the optional,
backward-compatible `timing_slots_raw` list. For `1 viên sáng và tối`, one group
retains `timing_raw="sáng và tối"`, `dose_raw="1 viên"` and source slots
`["sáng", "tối"]`. This does not create two dose records, calculate a daily dose,
infer a frequency, choose clock times or rewrite the instructions. Only explicit
conjunctions of bare dayparts are projected into separate slots. Alternatives,
ranges, meal-relative timings and other complex phrases retain one raw slot.
Model-supplied slots must equal that conservative source projection; omission is
filled from validated timing evidence. Slots from other medication evidence,
partial/reordered slots, invented times and loss of a grouped timing phrase are
rejected. Case and decomposed Unicode source spans are preserved.

`timing_slots_raw` is excluded from Ollama's generation grammar so the model
cannot guess a projection; validation computes it after checking the raw parent.
The generation grammar also constrains `uncertain_fields` to the validator's
existing field-name allowlist. Runtime validation remains mandatory for all
providers; neither adaptation relaxes evidence or slot-role checks.

The existing Core V4 JSON medication contract and intake adapter were inspected:
they retain the required raw timing/dose fields and permit extension fields in
administration objects. No Core file, schema, migration, dataset or historical
record is changed; old objects without the new list still parse with its default.
Database integration was reviewed statically, not exercised against a database.

## Contract decisions and specification differences

The attached implementation proposal is design input. PostgreSQL Core V4 is the
implemented contract, including exactly 20 tables and the existing identity owner.

- Workflows use only `MEDICATION_INTAKE`, `SAFETY_REQUEST`, `Q_AND_A`; patient
  summary integration is deferred despite V4 supporting `PATIENT_SUMMARY`.
  Proposed reconciliation, consultation, reminder, HCP and health-guidance workflow
  names/states are not added. The application FSM uses the V4 states directly.
- The main intake starts `COLLECTING`, can move to `CLARIFYING`, then
  `AWAITING_CONFIRMATION`, then `COMPLETED`. Cancellation is explicit. Corrections
  invalidate the old review and require a fresh display/confirmation. `/revise`
  starts a new workflow on the same items after completion, preserving confirmed
  history. Side Q&A/deferred requests are recorded as `SUSPENDED` workflows with a
  disposition; they do not imply a completed clinical action. The active intake
  and its draft are retained across side questions and process restarts.
- Intake modality is `TEXT`, never a new `CHAT` enum. Medication payloads keep
  `medication-entry.v4`, and timing uses `administrations` with raw dose/timing.
  `quantity_raw` retains the full supplied package expression; no package-count
  structure or arithmetic is introduced.
- The V4 JSONB validator permits extra medication fields; the existing Module 2
  Core adapter already reads `dosage_form_raw`. This package also retains
  `negation_raw` and `uncertainty_raw` as raw-text extension fields, validated
  against evidence. Existing required raw fields, schema tags and uncertainty
  arrays remain intact. No SQL contract is changed. Negated entries remain in
  the DTO and are excluded by the explicit identification wrapper from current
  exposure processing. Uncertainty is preserved conservatively across corrections.
- Each correction records the current source fragment as a new extraction,
  appends an entry version linked to that extraction, and retains earlier fields
  and evidence. Missing patch fields never erase old fields. To avoid accidental
  deletion this MVP does not support clearing a previously supplied slot.
- Missing name, strength and dosage form trigger clarification. `không rõ` permits
  review with null fields; dose/frequency/duration are optional and never filled
  with defaults. Ambiguous multi-drug corrections require `sửa thuốc 2 ...`.
  Product-name ambiguity is retained for Module 2; no fuzzy/CSV lookup verifies it.
- Review includes exact fields; workflow context pins entry IDs, database content
  digests, display message and revision. Only exact `xác nhận`/`tôi xác nhận` or
  `confirm(..., explicit_confirmation=True)` authorizes confirmation. `đúng rồi`,
  model-predicted intent, and unreviewed input do not. Confirmation has stable
  per-entry idempotency keys so a partial failure can be retried. A completed API
  retry must reuse its original request key. Clients must supply current revision.
- `build_handoff` returns latest confirmed entry UUIDs/digests, raw fields, and
  requested routes. `identify_confirmed(repo, dto, dataset_build=...)` explicitly
  invokes the existing Core Module 2 adapter after revalidation. It is never
  called automatically by the CLI. Module 3 assessment, snapshot orchestration,
  identity candidate resolution UI and downstream safety gates remain application
  integration work. No absence of findings is presented as evidence of safety.
- Application help uses fixed supported instructions. Optional
  `CoreMedicationReference(repo, published_build)` retrieves candidates and
  provenance. Ambiguous/missing candidates request clarification. That interface
  does not expose ingredient/strength/form facts for Q&A; those answers are
  explicitly deferred instead of adding SQL/CSV lookup or model medical knowledge.
- No HTTP API/authentication server is supplied. Production must derive the owner
  from trusted identity and protect confirmation handlers. CLI `--owner` is only
  for a trusted local development operator and an existing development identity.

