# Real Qwen intent and timing review

Evaluation date: 2026-11-09. Local Ollama 0.40.15, `qwen3.5:9b`, temperature 0,
thinking disabled, one inference attempt per case. All examples are synthetic.
No PostgreSQL connections or dataset changes were made.

## Prescription report versus record request

Input: `Tôi được kê 2 hộp Panadol 500mg.`

Before, `understand()` returned `intents=[]`, although `routing.detect()` returned
`ADD_MEDICATION`. Medication extraction was correct: `Panadol`, `500mg`, quantity
`2 hộp`, no dose. The CLI displayed the incomplete model intent list while the
chatbot used a later routing fallback. The prompt did not define report versus
record-request semantics.

After, observed `understand()` output includes:

```json
{
  "intents": [{
    "intent": "ADD_MEDICATION",
    "evidence_text": "Tôi được kê 2 hộp Panadol 500mg.",
    "record_request_raw": null
  }]
}
```

Name, strength and quantity remain unchanged; dose remains null. `ADD_MEDICATION`
means an intake candidate and does not claim current use or permission to save.
The prompt now defines that meaning, prescribed-report routing cues are explicit,
and validated extraction exposes the existing routing cue/fallback semantics.
Invalid model evidence is rejected before any intent completion.

For the separate synthetic input `Vui lòng lưu Panadol 500mg vào hồ sơ thuốc của tôi.`:

| Output | Before | After |
| --- | --- | --- |
| Intent | `ADD_MEDICATION` | `ADD_MEDICATION` |
| Explicit record-request evidence | No field | `record_request_raw="Vui lòng lưu"` |
| Authorization to confirm | None | None |

Both reports and explicit requests still follow the existing draft/clarification,
review and explicit-confirmation workflow. No inference result replaces the
owner, revision, digest or confirmation guards. Recognition of record-request
prefixes is conservative; an absent marker confers no authorization.

## Combined administration timing

Input: `Bác sĩ kê Augmentin 625mg, uống 1 viên sáng và tối trong 7 ngày.`

Before, the model/schema preserved the raw phrase but provided no separate slots:

```json
{
  "dose_raw": "1 viên",
  "duration_raw": null,
  "administrations": [{"timing_raw": "sáng và tối", "dose_raw": "1 viên"}]
}
```

After, observed validated output:

```json
{
  "dose_raw": "1 viên",
  "duration_raw": "trong 7 ngày",
  "frequency_raw": null,
  "administrations": [{
    "timing_raw": "sáng và tối",
    "dose_raw": "1 viên",
    "timing_slots_raw": ["sáng", "tối"]
  }]
}
```

The parent raw phrase and dose remain intact. Slots are a backend-derived source
projection within the same administration group, not two newly invented dose
instructions. No clock time, calculated daily dose or inferred frequency is added.
The prompt's complete example also recovers the explicitly stated seven-day
duration that this before-run omitted.

Only conjunctions of bare dayparts are split. `sáng hoặc tối`, `sáng đến tối`,
meal-relative and other complex timing phrases remain combined. Derived values
are checked against their own parent timing evidence. Partial/reordered slots,
invented times, other-drug slots and loss of grouped evidence are rejected.
Old administration objects without the new optional list still parse.

## Generation schema and regression results

The first expanded real run passed 11 cases and rejected three: Qwen emitted the
invalid uncertainty alias `strength`, shortened the single phrase `Mỗi sáng`, and
incorrectly split `sáng hoặc tối` in the new list. Validation rejected these;
no invalid extraction was accepted. The final Ollama grammar excludes the derived
slot list and constrains uncertainty names to the validator's existing allowlist.
The runtime evidence checks remain strict for every provider.

Final results:

- **Offline/mock: 111 passed in 0.62s.** Includes missing-intent completion,
  reports versus record requests, non-report routes, unchanged confirmation
  gates, exact Unicode spans, alternatives/ranges and invalid/cross-drug slots.
- **Real Ollama: 14 passed in 39.67s.** The previous eight cases plus report/use/save
  semantics, the Augmentin schedule, an alternative schedule and an information
  question. Each successful result passes JSON, Pydantic and source validation.
- Final before/after capture independently repeated the same three synthetic
  inputs with the final code and succeeded. Full captures are available locally
  in [before](../../../artifacts/nlp_semantics_before.json) and
  [after](../../../artifacts/nlp_semantics_after.json).

From the repository root:

```powershell
$env:PYTHONPATH = (Resolve-Path ./src).Path
.\.venv\Scripts\python.exe -X utf8 -m pytest -q tests/unit/test_nlp.py tests/unit/test_nlp_diagnostics.py tests/unit/test_nlp_interactive.py tests/unit/test_nlp_semantics.py
& .\src\module1_intake\nlp\test_ollama.ps1
```

Changed files are `models.py`, `providers.py`, `routing.py`, `validation.py`,
`interactive.py`, the three NLP documentation files, `tests/unit/test_nlp_semantics.py`,
`tests/unit/test_nlp_diagnostics.py` and `tests/integration/test_nlp_ollama.py`.
FSM, dialogue, persistence, Core DB V4, other modules and datasets are unchanged.
Core administration-extension compatibility was inspected statically; no database
integration test is claimed. These synthetic checks are not a clinical benchmark.
