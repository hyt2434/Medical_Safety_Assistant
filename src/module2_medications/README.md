# Module 2 — Medication Identification & Normalization

Module 2 resolves medication identities against source evidence and returns the
existing `module2.medication_identity.v1` contract. It does not determine whether
medications are safe to take. Transcription confirmation, product identity,
ingredient mapping and loaded interaction coverage are separate facts.

## Audit and ownership

The initial checkout contained no Module 2 README at this path. The audit found:

| Area | Initial state | Current implementation |
| --- | --- | --- |
| Vietnamese Unicode, ingredient grammar, units and source declarations | Implemented | `text.py`, `ingredients.py`; conservative parsing retained |
| DAV, curated and research references | Implemented; depend on local evidence | Existing `reference.py`, `curated.py`, `research.py`, `unified.py` retained |
| Shared Core identification adapter | Partial: exact case-insensitive brand and literal qualifiers | `core.py` extends its published-build guard and reuses its match persistence |
| Core relational ingredient/DDInter projection into the v1 result | Missing | `CoreMedicationReference.mapped_ingredients` preserves every source row |
| Confirmed NLP DTO → normalized Core matching | Missing Module 2 entry point | `core.identify_confirmed` validates the unchanged DTO before identification |
| Multiple approved DDInter targets | Supported by Core snapshots/Module 3; absent from Module 2 projection | All mapping rows retained; multiple targets require applicability review |
| Isolated Core/Module 2 regressions and approved-data projection checks | Missing | `tests/unit/module2/test_core.py`, `tests/integration/test_module2_core.py` |

All Module 2 runtime code and helpers belong to `src/module2_medications/`. Changes
also extend `service.py`, share normalization helpers between `text.py` and
`unified.py`, and expose lazy Core imports from `__init__.py`. Shared services,
Module 3, schemas, migrations, frontend and approved datasets are unchanged. NLP
orchestration now integrates this adapter as described below.

## Architecture

1. The confirmed Module 1 handoff supplies `Module2Handoff` / `ConfirmedEntry`
   objects with entry-version UUIDs, exact content digests and `Medication` fields.
2. `core.identify_confirmed` re-reads owner, conversation, intake membership,
   latest entry version, confirmation, digest and fields. It validates the entire
   handoff before matching any entry, rejects duplicate entries and skips negated
   exposures. Confirmation verifies transcription only.
3. `core.CoreMedicationReference` extends the shared Core adapter. Its constructor
   requires a published, explicitly pinned `dataset_build`. A build-scoped,
   in-memory product cache supports normalized exact matching. It creates no
   database, schema, persistent index or alternative reference dataset.
4. `service.identify` retains the existing v1 envelope. Core references supply
   relational components; legacy references retain the existing ingredient
   parser and `DirectDDInter` terminology path.
5. The existing `shared.db.identification_adapter.run_identification` stores the
   match using explicit, source-backed Core UUIDs. The wrapper returns the
   existing list of `(match, result)` tuples, with the v1 identity as `result`.
6. Existing Core snapshots pin all components and mapping UUIDs/builds. Existing
   Module 3 adapters perform interaction lookup and assessment independently.

The NLP `integration.handoff.identify_confirmed` compatibility function and
application `service.identify` now delegate to this Module 2 entry point with the
same confirmed DTO. The duplicated NLP matcher boundary has been removed.
Application `/identify` and a separate `/assess` request display grounded results;
existing Core/Module 3 adapters retain safety logic. See the
[NLP application API](../module1_intake/nlp/API.md) for the complete flow.

## Source-independent Module 1 boundary

The source audit found two NLP couplings: confirmed DTO definitions lived in
`nlp/models.py`, and Module 2 imported NLP's `CoreStore`/medication reader to check
confirmed versions. The unchanged DTOs now live in
`shared/intake_contracts.py`; NLP re-exports the **same class objects**, preserving
its imports and JSON schemas. Core row conversion, latest-version checking and
`build_confirmed_handoff` live in the existing `shared/db/intake_adapter.py` owner.
Module 2 imports no NLP inference, dialogue, model or store implementation.

The older `shared/intake.py` extraction models are unchanged. They describe an
unconfirmed extractor response, with nullable evidence and fewer fields, and
are **not** an alternative confirmed handoff. Future OCR/manual adapters must
map their actual output to the shared canonical fields before review. No
unfinished OCR/manual interface is called, changed or assumed to exist here.

### Exact confirmed input

Import `Medication`, `Administration`, `ConfirmedEntry`, and `Module2Handoff`
from `shared.intake_contracts`. These Pydantic models are strict, reject extra
fields and can be deserialized with `Module2Handoff.model_validate_json(...)`.

| Object | Existing fields |
| --- | --- |
| `Medication` | Nullable strings: `name_raw`, `strength_raw`, `dosage_form_raw`, `dose_raw`, `route_raw`, `frequency_raw`, `duration_raw`, `quantity_raw`, `instructions_raw`, `negation_raw`, `uncertainty_raw`. Required nonempty string: `evidence_text`. Arrays defaulting to empty: `administrations`, `uncertain_fields` |
| `Administration` | Nullable `timing_raw`, `dose_raw`; `timing_slots_raw: list[str]` defaults to empty |
| `ConfirmedEntry` | `entry_version_id: UUID`, `content_digest: str` from Core, `medication: Medication`, `identity_status='NOT_ATTEMPTED'` |
| `Module2Handoff` | `conversation_id: UUID`, `intake_id: UUID`, nonempty `entries: list[ConfirmedEntry]`, `requested_workflows: list[str]`, existing default `limitations: list[str]` |

Unknown raw values stay null. Preserve uncertainty and negation. An OCR confidence
score, a manual submit button, `requires_user_review`, an extractor assertion or
a caller-supplied transcription flag is not confirmation. Routing labels in
`requested_workflows` do not authorize identification or safety execution.
The shared DTO contains no workflow/revision field: the **review adapter** must
enforce the current workflow revision and exact displayed digest before Core
confirmation. Module 2 rechecks owner, conversation/intake membership, current
entry version, confirmation, digest, fields and source-extraction membership.

### Core intake and provenance

Use the existing `shared.db.intake_adapter.persist_module1` for initial intake:

```python
saved = persist_module1(
    repo, intake_id, original_bytes, {"medications": [medication.model_dump()]},
    modality=actual_modality, input_payload=actual_input_payload,
    extractor_name=actual_extractor_name, extractor_version=actual_version,
    content_type=actual_content_type, item_locators=[actual_item_locator])
# saved["entries"] are UNCONFIRMED; this call never confirms them.
```

`item_locators` is optional and backwards compatible. When supplied, it must be a
dictionary array aligned one-to-one with medications; it is validated before
writing and retained through the existing `create_item(..., locator=...)` API.
Do not put page boxes, confidence, object URIs or form metadata into strict
medication fields. Keep them in existing input payloads, extraction results and
item-origin locators. Module 2 preserves them without manufacturing source labels.

| Source | Core modality | Existing `input.v4` payload and byte contract |
| --- | --- | --- |
| Chatbot | `TEXT` | Actual submitted UTF-8 bytes, `text`, `digest_basis='ORIGINAL_BYTES'` |
| OCR over an image | `IMAGE` | Actual image bytes and content type; retained `object_locator` with a nonempty `uri`; preserve supplied object version/hash and page/region metadata |
| Manual form | `MANUAL` | Actual submitted bytes and `manual_fields` object; preserve supplied form version, field paths and row references |

Core accepts `ORIGINAL_BYTES` or `CANONICAL_JSON` as the declared digest basis.
`CoreRepository.record_input` always hashes the **bytes actually passed**. If a
host uses canonical JSON, its agreed canonical serialization must be those exact
bytes; Module 2 does not invent a serializer or reinterpret an image digest as a
transcription digest. The source-kind labels in tests are illustrative metadata,
not new Core enum values. Do not relabel a correction as OCR if it came from a
manual edit.

### Integration sequence for future developers

1. Obtain an authenticated owner on the server and use the existing Core
   conversation, intake and `MEDICATION_INTAKE` workflow. Persist original input,
   extraction identity/version, raw canonical medications and source locators.
2. Display the actual Core entry versions and content digests for review.
   Persist the review message and existing `draft`/`pending_confirmation` context,
   including `draft_revision`, `display_message_id`, exact entry ID/digest list
   and its Core-generated `payload_digest`. Do not calculate PostgreSQL JSONB
   digests with a client JSON hash.
3. Clarify missing/unreadable details without choosing identities. A correction
   appends an input/extraction and `repo.correct_entry(..., source_extraction=...)`
   in the same intake. Preserve the original item origin. Redisplay the new,
   unconfirmed version; earlier confirmation is not transferable.
4. On an actual explicit authenticated-owner confirmation, validate the current
   workflow revision, exact displayed entry set/digests and latest versions.
   Call the existing `repo.confirm_entry` with the displayed digest, a stable
   request UUID and the real explicit action. Complete the workflow using its
   checked revision. Core independently rejects nonexplicit actions, stale
   version/digest confirmations and cross-owner records.
5. Call `build_confirmed_handoff(repo, workflow_id)`, then explicitly call
   `module2_medications.identify_confirmed(repo, handoff, dataset_build=build)`.
   The builder never confirms entries. Module 2 validates the entire batch
   before matching and returns the existing `(Core match, v1 identity)` tuples.
6. Render identities, alternatives, missing mappings and limitations. An optional
   safety request must separately use the existing Core snapshot/Module 3 guards.

The existing chatbot uses this same builder and DTO. OCR/manual review transports
are **future integration work**; the test review driver is not a production UI,
new review service or replacement confirmation engine. Do not use the legacy
`from_module1(..., confirmed=True)` convenience flag as runtime authorization.

### Source evidence in the v1 result

The existing identity fields are unchanged. The additive `input_evidence` object
contains `item_id`, exact `origin_evidence`, actual nullable
`source_extraction_id`, unique `inputs` and `extractions`, and provenance `issues`.
It retains input IDs/modalities/content types/digests/payloads and available
extraction IDs/names/versions/status/results/errors. Original and correction
sources remain distinct; all records are re-read through owner-scoped Core calls.
Missing current extraction provenance is reported as
`CURRENT_SOURCE_EXTRACTION_NOT_RECORDED`; the original image is not falsely
attributed as the source of corrected fields. This input provenance is distinct
from product/ingredient/DDInter reference `source_evidence` and build identifiers.

### Agreements still needed with the team

- OCR retained-object URI/version lifecycle, page numbering, box coordinate space
  and confidence/uncertainty conventions. Existing Core JSON fields can retain
  these; no fixed OCR transport or locator schema is assumed.
- Manual form serialization and faithful `evidence_text`/field-path representation,
  including explicit null/unreadable values. A form transcription must not be
  presented as a quotation from a document that does not exist.
- Registration/manufacturer qualifiers: the existing shared confirmed medication
  DTO has no registration/manufacturer fields, although direct reference lookup
  accepts them. Any addition for OCR/manual disambiguation needs a coordinated
  reviewed-field/DTO agreement. Until then, preserve these as source metadata;
  do not silently turn metadata into confirmed identity qualifiers.
- OCR/manual review transport, authentication binding, revision/display-digest
  exchange and idempotency/correction UX. The current handoff has no revision
  token; adding one would require a coordinated contract change, not fabricated
  fields or an exception to confirmation checks.

Synthetic three-source tests use the same matcher/DTO and existing marked Core
database, including real confirmation/digest/revision/owner guards. They validate
normalization, combinations, ambiguous candidates/targets, missing attributes,
corrections and source evidence; they do not measure OCR accuracy or claim a
finished manual form. Run them with the existing `MODULE2_TEST_DSN` configuration:

```powershell
./.venv/Scripts/python.exe -X utf8 -m pytest tests/unit/module2/test_input_contract.py tests/integration/test_module2_input_sources.py -q --basetemp artifacts/test_tmp/module2_sources
```

Verified on 2026-11-10: **34 new three-source contract/provenance checks** passed.
The combined existing chatbot, real-Qwen, Module 2, approved-data and PostgreSQL
regression run passed **281 tests**. Existing NLP public schema fingerprints stay
unchanged; a standalone import test blocks every NLP module while loading the
shared handoff and Module 2. No OCR/manual runtime, database, migration, dataset
or frontend was created or modified for this work.

## Matching and normalization

- Unicode NFKC, case and whitespace normalization retain Vietnamese accents,
  names, salt forms, release labels, devices and formulation numbers. The
  existing conservative brand punctuation normalization is reused.
- Strength comparison reuses the existing dose grammar and explicit component
  separators. For example, `0,5 g`, `500 mg` and `500000 µg` compare equally.
  Exact rational arithmetic compares `500mg/5mL` with `100mg/mL` without rounding;
  `1mg/3mL` never becomes a rounded decimal concentration. Explicit `w/v` / `kl/tt`,
  `w/w` / `kl/kl` and `v/v` / `tt/tt` percentages retain their different dimensions.
  Bare percentages require review. `20mg/mL (2% w/v)` is accepted only when both
  assertions agree. Unit scaling preserves every supplied decimal digit.
- Fully labelled combinations retain ingredient-to-dose associations, including
  chemical/form labels; only their display order may differ. Unlabelled vectors
  retain order. A single label is removed for comparison with a plain dose only
  when the approved single-component ingredient declaration agrees literally.
  Named profiles must quantify every declared component. Mixed/duplicate labels,
  equivalence prose, unquantified ingredients and ambiguous separators require review.
- `IU`/`UI`, explicit uppercase `MIU`/`triệu IU` and repeated uniform thousands
  groups such as `1.000.000 IU` normalize conservatively. Single separator groups
  (`100.000 IU`, `1,578 g`), lowercase `mIU` and unspecified potency conversions
  remain unsupported. No dose, route, salt equivalence or missing value is inferred.
- Dosage forms reuse Vietnamese registry forms and existing research aliases,
  including `Viên nén`/`tablet` and film-coated/extended-release distinctions.
- Name, strength, form, route, registration and manufacturer aliases are
  constraints when supplied. Contradictory input aliases require review; a
  conflicting reference value eliminates a candidate. A supplied qualifier that
  is absent from the reference prevents verification. Missing input qualifiers
  stay missing; a unique approved reference identity can still be selected.
- No fuzzy selection, accent stripping, inferred brand/generic substitution or
  removal of embedded strength/release text establishes an identity. Ambiguous
  products remain candidates. When an exact name is absent, a build-local index
  proposes one-edit/transposition or optical `0/o`, `1/l`, `5/s`, `rn/m`, `vv/w`
  candidates for review. Numeric product variants and release labels remain
  constraints. At most five name groups are proposed, retaining every product in
  each group and reporting truncation. These proposals can never be `VERIFIED`.
- A missing name/registration requires both parsed strength and dosage form to
  offer attribute-only review candidates. More than 20 compatible products are
  withheld with a count and a request for a name. A unique attribute-only result
  still requires review. Known strength/form conflicts eliminate candidates;
  unsupported strength semantics retain anchored candidates for review.

Candidate `match_kind` distinguishes `EXACT`, `SIMILAR_NAME_REVIEW_ONLY` and
`ATTRIBUTES_REVIEW_ONLY`; `unresolved_qualifiers` records unsupported constraints.
`establishes_identity` is false for every review proposal. Ingredient/DDInter
evidence for a unique proposal describes that candidate, not a confirmed patient
identity. Core persists it as `AMBIGUOUS`, without selecting a product. Correct
the medication through the existing review workflow and confirm the new version
before identifying again. No candidate choice bypasses revision/digest guards.

## Inputs and outputs

Core lookup accepts `name_raw`/`brand_name`, `strength_raw`/`strength`,
`dosage_form_raw`/`dosage_form`, `route_raw`/`route`,
`registration_token`/`registration_number`, `manufacturer`/`manufacturer_raw`,
and Module 1 uncertainty fields. Identity fields must be strings or null.

`identify(medication, reference, terminology=None)` returns:

| Field | Meaning |
| --- | --- |
| `schema_version` | Unchanged `module2.medication_identity.v1` |
| `original_medication` | Deep copy of submitted fields |
| `identification_status` | `VERIFIED`, `REVIEW_REQUIRED` or `UNRESOLVED` product/transcription identity |
| `candidates`, `identified_candidate` | Every matching product; a single candidate can still need review |
| `normalized_input`, `issues` | Compared Core keys and explicit review/unresolved reasons |
| `dataset_build`, `reference_build_metadata` | Pinned Core build and retained ledger metadata |
| `ingredients` | Ordered relational components, ingredient records, raw strength/equivalence/form declarations and all DDInter mapping rows |
| `mapping_status` | Independent aggregate ingredient/DDInter mapping status |
| `verified_ddinter_ids` | Only unambiguous verified component targets; never a chosen target from an ambiguous set |
| `approved_ddinter_ids` | All valid retained target IDs, including alternatives requiring review |
| `ready_for_identifier_handoff` | Confirmed, verified identity, complete component coverage and verified unambiguous mappings |
| `interaction_assessment` | Always `NOT_PERFORMED` by identification |

Each Core ingredient retains `component_record`, nullable `ingredient_record`,
`ddinter_mappings`, `candidate_ddinter_ids`, component/build identifiers and
source evidence. Every mapping retains its UUID, source mapping ID, mapping-set
ID, target ID, catalog hash, retrieval evidence and source locator. Repeated rows
for one target remain distinct evidence. Historical review flags remain source
provenance; they do not override approval of a published Core build.

Multiple targets on one component produce `REVIEW_REQUIRED` and a null singular
`ddinter_id`. Missing/invalid targets stay visible in their original mapping rows.
`approved_ddinter_ids` is not a claim that all targets apply to the patient.
Product selection may be verified while mappings require review: the existing
Core snapshot/Module 3 path retains and checks all approved combinations with
limitations. The direct `module3_input` path preserves alternatives and leaves
ambiguous components unassessed.

## Usage

Run from the repository root with `src` on `PYTHONPATH`, using the existing
Python environment and Core dependencies.

```python
from module2_medications import CoreMedicationReference, identify, identify_confirmed
from module1_intake.nlp.integration.handoff import assess_confirmed_snapshot

# repo is an existing authenticated CoreRepository; build is a pinned published hash.
reference = CoreMedicationReference(repo, build)
result = identify({"name_raw": "EXACT SOURCE BRAND", "strength_raw": "0,5 g",
                   "transcription_status": "USER_CONFIRMED_TRANSCRIPTION"}, reference)

# Runtime authorization comes from re-reading Core, not from the string above.
handoff = application_service.handoff(workflow_id)
matches = identify_confirmed(repo, handoff, dataset_build=build)
snapshot = repo.create_snapshot([(m["entry_version_id"], m["id"]) for m, r in matches])
assessment, output = assess_confirmed_snapshot(
    repo, handoff, snapshot["id"], existing_module3_dataset, request_key=request_uuid)
```

Core restricts synthetic reference builds to snapshots with
`data_context="SYNTHETIC_TEST"`. Use existing Module 1/3 snapshot guards for the
exact confirmed targets. Direct offline/OCR callers can continue to use
`from_module1(extraction, reference, terminology, confirmed=True)` and
`module3_input`; that convenience flag is not Core authorization. The existing
`assess_prescriptions` convenience function delegates safety work to Module 3.

## Verification and limitations

### Original real Core REF evaluation — 2026-11-10 (frozen baseline)

The evaluation used the existing published, non-synthetic Core build
`463cd6c56dc5476fcabf5ad13405a909f3d0254a0043c3d5509140fb92ba1ab9`
in `msa_core_test_v4cleanupteam20261109checks`. Its **10,670 medications, 1,940
ingredients, 12,899 components and 5,675 DDInter mappings** were read directly
from PostgreSQL. The four-product synthetic build was excluded. Connections
force `default_transaction_read_only=on`; before/after reference fingerprints
were identical. No reference import, schema change or new database was used.

The catalog sweep executed **88,420 lookup queries**. Positive queries are
constructed from known source rows, with controlled unit/form variants and
missing attributes; negative controls omit the name or introduce an absent
similar spelling. These measure **source-row recovery and matching policy**,
not independently adjudicated patient/product identity accuracy. Clinical
identification accuracy remains unmeasured because no independent gold set is
available. Database consistency is assessed separately below.

| Category | Queries | VERIFIED | REVIEW_REQUIRED | UNRESOLVED | Multiple-candidate ambiguity |
| --- | ---: | ---: | ---: | ---: | ---: |
| Exact name | 10,670 | 93.61% | 6.39% | 0% | 6.39% |
| Name + available strength/form/route | 10,670 | 83.38% | 16.62% | 0% | 2.45% |
| All available qualifiers, including registration/manufacturer | 10,670 | 85.65% | 14.34% | 0.01% | 0% |
| Unambiguous equivalent strength expressions | 7,138 | 97.59% | 2.41% | 0% | 2.41% |
| Equivalent dosage forms | 6,590 | 87.16% | 12.84% | 0% | 3.40% |
| Input strength omitted | 10,670 | 94.71% | 5.29% | 0% | 5.29% |
| Input form omitted | 10,670 | 82.65% | 17.35% | 0% | 3.26% |
| Name omitted, no registration anchor | 10,670 | 0% | 0% | 100% | 0% |
| Similar but absent name | 10,670 | 0% | 0% | 100% | 0% |
| Locale-ambiguous generated strengths | 2 | 0% | 0% | 100% | 0% |
| Multi-ingredient source rows (subset) | 1,561 | 81.23% | 18.77% | 0% | 2.56% |
| Source rows missing strength/form (subset) | 1,937 | 96.33% | 3.67% | 0% | 3.67% |
| Duplicate normalized names (subset) | 682 | 0% | 100% | 0% | 100% |

Subset rows overlap the main categories and are not additional queries.
`REVIEW_REQUIRED` includes unsupported strength semantics as well as ambiguity;
these must not be counted as the same outcome. For example, 1,530 full-qualifier
queries require strength review, with no multiple-candidate ambiguity. Omitting
an unsupported strength removes that constraint, so a higher verification rate
after omission is not evidence of improved accuracy.

Expected-source candidate retention was **100%** for exact names, supported
equivalent strengths/forms and the name/strength/form categories; all-qualifier
retention was **99.9906%** because one malformed numeric registration remains
rejected. There were **zero incorrect VERIFIED source selections** in this
source-derived sweep and zero verified results for 21,340 absent-name/missing-name
controls. These figures do not establish clinical false-positive rates.

**Reference consistency and mapping coverage, independently measured:**

- All **31,184 reference rows** retained their source IDs, build IDs, manifest
  links and declared artifact hashes. All 12,899 product/component links and
  nullable ingredient links were consistent; 662 components legitimately lack a
  canonical ingredient ID. All component sets and every mapping row survived the
  Module 2 projection unchanged. These are consistency results, not accuracy labels.
- **5,675 / 12,899 components (44.00%)** have an approved DDInter mapping; **7,224
  (56.00%)** have none. All retained targets are syntactically valid, with catalog
  hashes/retrieval evidence. There are **481 distinct target IDs**. This real
  build has no components with multiple targets; synthetic regressions continue
  to cover that contract.
- **4,690 / 10,670 products (43.96%)** have unambiguous target mappings for every
  component. This measures mapping availability independently of product
  identification and loaded interaction coverage. Missing mappings are not filled
  through guessed salt/base equivalences or name similarity.

**Confirmed handoff and Module 3:** Twenty representative real-catalog inputs
covered mapped endpoints, combinations, missing/unsupported strengths and
duplicate names. They used actual persisted review, revision/digest checks and
explicit Core confirmation in the existing isolated intake database. Reference
reads stayed on the read-only real catalog; the final match-persistence boundary
was captured in memory because the intake database has no copy of that build.
No real-build Core match/snapshot persistence across databases is claimed.

The existing Module 3 engine received the normal `module3_input` objects and
retained all 190 medication-pair contexts. With ten retained real category-A
interaction rows and the existing sealed index's identity evidence, it checked
105 unique ingredient pairs, found one source interaction and retained 13
unresolved components. Its assessment remained incomplete, with
`safe_to_take=None`; partial evidence was never converted into a safety claim.
The local JSON report also distinguishes target membership in loaded identity
evidence from clinical mapping correctness and interaction coverage.

**Demonstrated weaknesses and fixes:**

- The original adapter scanned 10,670 products per query: 20 cold-start name
  lookups took 2.59 seconds. A build-local exact name/registration index now
  shortlists the same candidates and applies every original qualifier. The same
  20-query measurement took 0.84 seconds including catalog loading/indexing; the
  full 88,420-query sweep took about five seconds, with relational projection
  measured separately. No alternate matcher or persistent index was added.
- Twelve readable retained registration tokens were incorrectly rejected.
  Literal `VD3-…`, `SP3-…`, `GC-…` and `QLSP-H03-…` formats now normalize without
  completing digits or asserting current regulatory authorization. Full-qualifier
  unresolved results fell from **13 to 1**. Regression tests also ensure indexed
  anchors cannot override conflicting names, registrations or strengths.
- `Prednisolone 20 mg` has retained token `89311087026` (11 digits); it remains
  unresolved when that registration qualifier is supplied. `Danaroxime 1500mg`
  (`1578mg` in the source) and `Tecentriq` (`1875mg/15ml`) are not matched from
  generated `1,578 g` / `1,875 g/15 mL`, whose separators are locale-ambiguous.
  These were separated from the unambiguous-equivalence denominator, not relaxed.
- `Gynax-US` has a named combination/locale-dependent IU strength expression;
  `Api-pred` has `0,2% (w/v)`, unsupported at this baseline (now supported below).
  Unsupported source strength semantics continue to require review. Examples
  such as `Naproxen Cap DWP 220mg` have no approved Core
  mapping for their retained component; this is a mapping-data gap, not permission
  to invent a DDInter ID.

All **481 distinct Core targets** were present in the existing sealed Module 3
identity evidence, with **zero source-name versus target-name/synonym mismatches**
across the 5,675 mapping rows. This checks catalog membership and retained names;
it does not independently establish chemical equivalence or clinical coverage.

Real-data evaluation lives in `tests/integration/test_module2_real_reference.py`;
fix regressions live in `tests/unit/module2/test_core.py`. The complete combined
regression run passed **289 tests**, including existing chatbot/real-Qwen,
synthetic three-source and Core/Module 3 tests. The detailed category counts,
examples, fingerprints and scope limitations are local only in
`artifacts/module2_real_reference.json`.

### Conservative matching improvement — identical-query comparison

The frozen baseline is `artifacts/module2_matching_before.json`; the rerun and
machine-checked comparison are in `artifacts/module2_matching_after.json`.
Both used the same build and **88,420 queries**, with query-manifest SHA256
`6f33e142171445b54324bf710c0c9a30302f18c9d6c48d9b748e7d31548a5e91`.
Reference fingerprints, component projection, source evidence and mapping
coverage were identical. No reference records were changed.

Root causes were unsupported percentage bases, labelled component strengths,
unreduced concentration ratios and IU notation; duplicate product names; absent
identity anchors; and strict rejection without review proposals for absent
spellings. The 1,530 baseline full-qualifier reviews all included unsupported
strength semantics. Those reviews fell to 502 after conservative parsing; one
malformed registration remains unresolved. No ambiguity rule was relaxed.

| Query category | Queries | VERIFIED before → after | REVIEW_REQUIRED before → after | UNRESOLVED before → after |
| --- | ---: | ---: | ---: | ---: |
| Exact name | 10,670 | 9,988 → 9,988 | 682 → 682 | 0 → 0 |
| Name + source strength/form/route | 10,670 | 8,897 → 9,889 | 1,773 → 781 | 0 → 0 |
| All available qualifiers | 10,670 | 9,139 → 10,167 | 1,530 → 502 | 1 → 1 |
| Strength omitted | 10,670 | 10,106 → 10,106 | 564 → 564 | 0 → 0 |
| Form omitted | 10,670 | 8,819 → 9,806 | 1,851 → 864 | 0 → 0 |
| Equivalent strength | 7,138 | 6,966 → 6,942 | 172 → 196 | 0 → 0 |
| Equivalent form | 6,590 | 5,744 → 6,181 | 846 → 409 | 0 → 0 |
| Missing name | 10,670 | 0 → 0 | 0 → 4,060 | 10,670 → 6,610 |
| Absent similar spelling | 10,670 | 0 → 0 | 0 → 7,056 | 10,670 → 3,614 |
| Locale-ambiguous strengths | 2 | 0 → 0 | 0 → 2 | 2 → 0 |
| **All queries** | **88,420** | **59,659 → 63,079** | **7,418 → 15,116** | **21,343 → 10,225** |

Aggregate rates changed from **67.47% / 8.39% / 24.14%** to
**71.34% / 17.10% / 11.56%** (verified / review / unresolved). These totals mix
positive source recovery with deliberate absent-name controls and are not
clinical accuracy. Incorrect verified selections remained **0 → 0**. All
positive source rows remained candidates except the same malformed registration.
Source-derived multi-ingredient verification rose **1,268/1,561 → 1,441/1,561**;
this subset is excluded from the aggregate to avoid double counting.

Equivalent-strength verification decreases for 24 queries because newly
comparable/retained rows expose additional plausible products. Every such case
requires review; the matcher never chooses one by ranking. Missing-name and
absent-spelling queries produced **11,116** review-only results, all checked to
have `complete_identity=False` and `establishes_identity=False`. Candidate
retrieval recall is not evaluated against an independently labelled OCR set.

Examples now supported include `Api-pred` (`0,2% w/v`), explicitly labelled
paracetamol/ibuprofen combinations and `minoxidil 20mg/mL`. `Gynax-US`
(`100.000iu` / `65.000iu`), `Skin Guard` (`mg/g` without an amount), `Phytomycin`
(`0,01` without a unit), and complex equivalence/range/reconstitution prose
still require review. No salt/base, potency or missing-unit inference is made.

DDInter availability remains **5,675/12,899 components (44.00%)** and
**4,690/10,670 fully mapped products (43.96%)**. Better product normalization
does not fill the 7,224 missing component mappings. All 481 existing target IDs
and every mapping/source/build record are retained.

The representative real-catalog handoff still uses genuine Core confirmation
and captured final match persistence as documented above: 20 inputs, 190
medication pairs, 136 unique ingredient pairs, one retained source interaction,
11 unresolved components, `safe_to_take=None`. A separate isolated PostgreSQL
regression checks actual Core snapshot/assessment persistence. New three-source
regressions show a confirmed typo persists as `AMBIGUOUS`, and selection requires
a corrected version plus fresh explicit confirmation. Runtime changes are
limited to Module 2 `core.py`, `text.py`, and its existing `unified.py` formatter;
regressions live under `tests/unit/module2/` and `tests/integration/`.

Validation: **345 combined regressions passed in 131.39 seconds**, covering
existing NLP, real Qwen, Core persistence, synthetic chatbot/OCR/manual inputs,
real references and Module 3. The final focused matching run passed **54 tests**
(53 overlap the combined run; one additional duplicate-concentration regression),
for **346 distinct passing tests**. `git diff --check` passed. The benchmark's
lookup and projection timings were 11.735 and 5.961 seconds on this run; timing
varies with local service load. Broader legacy evidence limitations below remain.

To reproduce with **existing** databases/artifacts (never bootstrap or import):

```powershell
$env:PYTHONPATH='src'
$env:PYTHONDONTWRITEBYTECODE='1'
$env:MODULE2_REAL_DSN='<existing real Core V4 DSN>'
$env:MODULE2_REAL_BUILD='463cd6c56dc5476fcabf5ad13405a909f3d0254a0043c3d5509140fb92ba1ab9'
$env:MODULE2_REAL_REPORT='artifacts/module2_matching_after.json'
# Optional: compare with a frozen baseline from the SAME query manifest/build.
$env:MODULE2_REAL_BASELINE='artifacts/module2_matching_before.json'
# Required only for the optional representative handoff/interface test:
$env:MODULE2_TEST_DSN='<existing marked isolated fixture DB DSN>'
$env:MODULE2_DDINTER_CSV='<existing approved ddinter_downloads_code_A.csv>'
$env:MODULE2_DDINTER_INDEX='<existing sealed official.sqlite>'
./.venv/Scripts/python.exe -B -X utf8 -m pytest tests/integration/test_module2_real_reference.py -q --basetemp artifacts/test_tmp/module2_real
```

The real-catalog test rejects synthetic builds and verifies read-only reference
fingerprints. Without a real DSN it skips explicitly; it never substitutes a CSV
projection or synthetic database for live Core REF testing. The interface test
separately skips if its existing intake DB or approved DDInter artifacts are not
configured. Generated outcomes alone are not an independent clinical gold set.

```powershell
# Optional: an EXISTING, marked, loopback Core V4 test database with the published
# four-product synthetic fixture. Tests never bootstrap, import into, or create a DB.
$env:MODULE2_TEST_DSN='host=127.0.0.1 port=55432 dbname=<existing-test-name-ending-checks> user=<test-user>'
$env:PYTHONDONTWRITEBYTECODE='1'
./.venv/Scripts/python.exe -X utf8 -m pytest tests/unit/module2/test_core.py tests/unit/module2/test_reference.py::ParserTests tests/integration/test_module2_core.py -q --basetemp artifacts/test_tmp/module2
```

The focused suite passed **49 tests** on 2026-11-10. Tests cover exact Vietnamese
matches, equivalent units/forms, ambiguity, unmatched names, conflicting/missing
attributes, components without canonical ingredient records, multiple/partial
targets, build isolation, complete source evidence and confirmed DTO guards.
The real PostgreSQL flow runs Module 1 confirmation → Module 2 selection → Core
snapshot → existing Module 3 assessment, retaining both alternative targets.

Approved-data tests run the **existing importer** against all six available CSVs
and capture its COPY projection in memory. They check all 5,675 mappings across
12,899 components, preserve source rows and verify file hashes remain unchanged.
This validates approved data without importing it into or changing a database.
It does not establish live deployment coverage or clinical correctness.

The broader legacy suite could not pass in this checkout: `data/reference/`
official/research evidence is absent (the initial run had 12 passes, 2 failures
and 52 setup errors). The separate existing source-boundary suite also cannot
collect because the read-only OCR module lacks `find_numbered_row_starters`.
No substitute reference artifacts or edits to those dependencies were made.

Core mapping availability does not establish loaded Module 3 identity/interaction
coverage. Unknown attributes, missing components, multiple mapping targets,
unconfirmed/uncertain inputs and absent interaction records retain limitations.
Current marketing authorization and physical-product/clinical verification are
outside this reference identity scope. No autonomous safety conclusion, dose
recommendation or medication change is generated by Module 2.
