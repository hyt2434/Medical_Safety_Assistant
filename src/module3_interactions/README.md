# Module 3 MVP: local DDInter and Core V4

Module 3 uses the existing `OfficialDataset` loader and deterministic pair engine.
Persisted workflows use `shared.db.safety_adapter.run_safety`. They retain original
DDInter levels, every supporting source row, affected entry/component IDs, approved
mapping IDs, index/manifest hashes and mapping-catalog dependency hashes.

## Configure the local collection

Run from the repository root. The sibling research collection is read-only. Copy
the eight CSVs once into `data/DDInter/`, together with its existing index, seals
and required evidence. Do not rebuild or rewrite the research index or manifests.
`/data/DDInter/` is ignored at the repository root; never force-add these files.

Example for this workspace (adjust the two source paths for another workstation):

```powershell
$source = '../Medication-Safety-Assistant/data/reference/ddinter2/official_20261013'
$priorRecord = '../artifacts/team_candidate_copy_20261025_001/backup/data/reference/source_evidence/Medication-Safety-Assistant/module2_api_quicktest/ingredient_ddinter_poc/evidence/ddinter_public_record.json'
$destination = 'data/DDInter'
$files = @('manifest.json','official.sqlite','official.manifest.json',
    'official_synonyms.json','DDInter20.html','download.html','statistics.html','terms.html')
$files += 'ABDHLPRV'.ToCharArray() | ForEach-Object { "ddinter_downloads_code_$_.csv" }
New-Item -ItemType Directory -Path $destination -Force | Out-Null
foreach ($name in $files) {
    $from = Join-Path $source $name
    $to = Join-Path $destination $name
    if (-not (Test-Path -LiteralPath $to)) { Copy-Item -LiteralPath $from -Destination $to }
    if ((Get-FileHash -LiteralPath $from -Algorithm SHA256).Hash -ne
        (Get-FileHash -LiteralPath $to -Algorithm SHA256).Hash) { throw "Hash mismatch: $name" }
}
$to = Join-Path $destination 'ddinter_public_record.json'
if (-not (Test-Path -LiteralPath $to)) { Copy-Item -LiteralPath $priorRecord -Destination $to }
if ((Get-FileHash -LiteralPath $to -Algorithm SHA256).Hash -ne
    'dc25545132a6f9d6c979c7db8c9e2b3f63703db1e720944c38d6be83bdd8bd2f') {
    throw 'Prior official identity transcription hash mismatch'
}
$env:PYTHONPATH = 'src'
$env:MSA_DDINTER_INDEX = (Resolve-Path 'data/DDInter/official.sqlite').Path
& .venv/Scripts/python.exe -X utf8 -m module3_interactions.official_ddinter lookup `
    --index $env:MSA_DDINTER_INDEX DDInter582 DDInter725
git check-ignore data/DDInter/manifest.json data/DDInter/ddinter_downloads_code_A.csv
```

The prior record supplies the sealed acetaminophen/paracetamol identity evidence;
it is a required dependency, not a new synonym or salt/base-equivalence inference.
Obtain the exact retained artifact if it is absent; do not invent a replacement.
All 17 local files preserve their original bytes. Historical paths in the seals
remain provenance; the loader resolves their dependencies within the selected
collection and verifies each SHA-256. SQLite connections use `mode=ro`.

`OfficialDataset()` and the existing `load_ddinter(PROJECT_ROOT, 'official-all')`
select `MSA_DDINTER_INDEX`, or `data/DDInter/official.sqlite` by default. An explicit
index path is also supported. For an index stored separately from its collection,
pass `OfficialDataset(index_path, collection_path=collection_directory)`.
Missing files, mismatched hashes, incomplete real collections and index/source
disagreement raise errors. No exception selects the historical ten-row sample.
Real persisted assessments also reject bounded/sample datasets without the eight
source artifacts and three sealed dependency hashes. Synthetic tests remain
explicitly labeled.

For the existing NLP application CLI, supply `--application`, `--ddi-index` with
this index path, an authenticated development `--owner` and the published
`--reference-build`. The host API can inject `OfficialDataset()` into its existing
`ApplicationService`. Confirmation authorizes transcription only.

## Contracts and coverage

The original `checks.v4` occurrence-pair statuses remain unchanged. Detailed
component combinations are retained in each check's
`scope.component_pair_results`, including unassessed components after a later
lookup fails. Missing source records mean insufficient loaded evidence.

Duplicate findings use an exact, retained local ingredient ID from the same
published reference build, or a shared approved DDInter target. Local IDs allow
duplicate detection even when DDInter mappings are absent. The rule never infers
chemical, salt/base, brand or dose equivalence. Alternative DDInter targets remain
visible and produce partial coverage where applicability is unresolved. No dose
totals or administration decisions are computed.

Core V4 checks concern pairs of medication occurrences. A single occurrence has
`NOT_APPLICABLE` inter-medication checks, including a combination product; this
does not establish its clinical safety or intra-product interaction coverage.
The standalone engine retains its existing within-product component checks.
The existing NLP application still requires two non-negated targets to request
safety and retrieve assessment Q&A; its contract was kept read-only in this task.

Major/contraindicated warnings and conflicts containing those levels remain
immediate. Each durable finding includes `evidence.reminder_hold`; the aggregate
is in `check_results.ddi.scope.reminder_hold` and the runtime result. It identifies
affected entry versions and limits the proposed hold to **new implicated reminder
activations**. Existing reminders are unchanged. No Module 5 gate or activation
policy is implemented. Committed warnings remain available through
`CoreRepository.severe_warnings()` after lookup/composition failures and retries.

## Verification and known limits

The ten persisted Module 3 integration tests require a published real reference
build as well as the existing four-product synthetic engineering fixture. Merely
bootstrapping Core V4 or enabling the NLP tests does not install the real build.

The installed eight-category collection (A/B/D/H/L/P/R/V) contains **222,383 source
rows, 160,235 distinct pairs and 1,939 endpoint identities**. All 62,148 repeated
pair occurrences remain available as source evidence. It contains no observed
severity or identifier-name conflicts; conflict tests use explicit synthetic
engineering evidence. Original levels include 47,182 `Unknown` source rows.

Pinned index SHA-256:
`357c8f48681aeea222f1085a2be87d33099619f7b3403e459330788c799f3a8e`.
Collection-manifest SHA-256:
`dfcc7b75f59e464e28f3b4cc3cf72e075c95dfb7b10341e7dffb914423899bd0`.

The existing real Core fixture has 12,899 components: 12,237 retain local ingredient
IDs; 5,675 have approved DDInter mappings, reaching 481 distinct targets, all present
in the loaded dictionary. **7,224 components lack DDInter targets.** These are
reference-data counts, not clinical sensitivity or coverage guarantees.

Persisted tests reuse existing marked loopback PostgreSQL databases and published
references; they never bootstrap, import, migrate or alter reference data. New
workflow records belong to fresh test owners and use `SYNTHETIC_TEST` snapshots.
Every real-data test verifies reference-table fingerprints and the build ledger
are unchanged.

Verified on 2026-11-11 using the commands below:

- Real-DDInter E2E and related checks: **42 passed, 1 skipped, 7 subtests passed**
  in 102.58 seconds, including the opt-in real-Qwen synthetic CLI case. The sole
  skip is the absent archived research-only reference, not a Core V4 E2E test.
- Complete current NLP launcher: **198 passed**, no skips, in 62.55 seconds.
- The manual CLI sequence below also passed with **real Qwen + approved real
  references + real DDInter**: verified identities, retained Major finding,
  partial coverage, source citations and `QWEN_GROUNDED_SELECTION`.
- Both original databases' table contents and schema/reference ledgers remained
  unchanged. SHA-256 checks preserved all **25** approved CSV, local DDInter and
  migration files inspected before provisioning.

Reports: `artifacts/core_db_v4/real-e2e.xml`,
`artifacts/nlp_mvp_v2/junit.xml`,
`artifacts/core_db_v4/real-qwen-manual.txt`, and
`artifacts/core_db_v4/real-e2e-preservation-after.json`.

## Reproduce the real-data E2E run

Inspection on 2026-11-11 found both original databases correctly owned by
`core_fixture_admin`, marked `Medication Safety Assistant Core V4 isolated test`,
and at the current two V4 migration checksums. Their reference contents were:

| Database | Products / ingredients / components / mappings | Published ledger |
| --- | --- | --- |
| `msa_core_test_v4nlp20261109checks` | 0 / 0 / 0 / 0 | Empty |
| `msa_core_test_v4nlpmvp20261109checks` | 4 / 4 / 4 / 4 | Synthetic only |

Neither can satisfy the real test's 10,670-product, published, explicitly
non-synthetic build requirement. The earlier `resumechecks` DSNs in this guide
were not present on this cluster. Both original databases were preserved.

The dedicated database `msa_core_test_v4nlpe2e20261111checks` was created with
`db/manage.py`'s guarded `bootstrap_test`, the existing approved CSV importer,
and `db/tests/fixtures.py::fixture_sources`. It contains these published builds:

| Build | Products | Ingredients | Components | Mappings |
| --- | ---: | ---: | ---: | ---: |
| Real `463cd6c56dc5476fcabf5ad13405a909f3d0254a0043c3d5509140fb92ba1ab9` | 10,670 | 1,940 | 12,899 | 5,675 |
| Synthetic `969919559b9463877d8f773dc0ac2260f4c1a857dc085283b2943f117aa7bab9` | 4 | 4 | 4 | 4 |

The real import also reconciled 5,614 indications and 6,105 priorities inside
product JSONB: **42,903 original CSV records**, with matching source ID sets.
The database name satisfies both guards: Module 2 requires loopback
`msa_core_test_v4<suffix>checks`; NLP additionally requires the `nlp` prefix.
The database comment must match the marker above. `CORE_DB_DSN` alone does not
configure pytest: set both test DSNs explicitly.

Copy this block into PowerShell for repeat runs. It reuses the provisioned
database and performs no bootstrap/import/migration. The suite writes fresh
test owners and workflow records in this database.

```powershell
Set-Location -LiteralPath 'C:\HCMUS\SE\Tieu Bach\api_quicktests\Medical_Safety_Assistant_Team'
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$env:PYTHONPATH = 'src'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:MODULE2_TEST_DSN = 'host=127.0.0.1 port=55432 dbname=msa_core_test_v4nlpe2e20261111checks user=core_fixture_admin connect_timeout=5'
$env:NLP_TEST_DSN = $env:MODULE2_TEST_DSN
$env:NLP_TEST_BOOTSTRAP = '0'
$env:NLP_RUN_REAL_OLLAMA = '1'
$env:NLP_OLLAMA_MODEL = 'qwen3.5:9b'
$env:NLP_OLLAMA_URL = 'http://127.0.0.1:11434'
$env:NLP_OLLAMA_TIMEOUT = '120'
$env:MSA_DDINTER_INDEX = (Resolve-Path 'data/DDInter/official.sqlite').Path
& .venv/Scripts/python.exe -X utf8 -B -m pytest -q `
    -ra --tb=short -o junit_family=xunit1 `
    --junitxml=artifacts/core_db_v4/real-e2e.xml `
    tests/unit/module3/test_official.py tests/unit/module3/test_local_dataset.py `
    tests/integration/test_module3_real_e2e.py tests/integration/test_nlp_module2_flow_v4.py `
    tests/integration/test_module2_core.py
if ($LASTEXITCODE -ne 0) { throw 'Real-data E2E failed; inspect the pytest output.' }
```

Set `NLP_RUN_REAL_OLLAMA='0'` for deterministic extraction only; this intentionally
skips the live-Qwen CLI test. The live-Qwen CLI test uses the explicitly synthetic
four-product interaction fixture; the ten real-reference/DDInter tests use mock
extraction and template grounding. These are separate evidence claims.
`junit_family=xunit1` retains the selected real product labels in the report
without pytest's `record_property`/xunit2 warning.

For the complete current NLP regressions, use the same environment and run:

```powershell
& .\src\module1_intake\nlp\test_mvp.ps1 `
    -Dsn $env:NLP_TEST_DSN -RealOllama -Model 'qwen3.5:9b'
```

The older `tests/unit/module3/test_engine.py` and portions of
`tests/unit/module2/test_reference.py` depend on absent archived
`data/reference/` research fixtures, including a historical ten-row sample.
They are outside the real-DDInter/Core V4 command above. Do not replace those
fixtures with the full collection or weaken assertions to obtain a green run.
The broad discovery run also exposed a socket mock leaking when the old
`ReferenceTests.setUpClass` failed. Class cleanup now restores the socket even
after setup failure; an injected missing-fixture check verified restoration.

## Real-Qwen manual testing

From the same repository and environment block above, extraction alone needs no
database. Keep `$OutputEncoding` at UTF-8 when piping Vietnamese input from
Windows PowerShell; its ASCII default replaces accented characters with `?`.

```powershell
& .\src\module1_intake\nlp\interactive_ollama.ps1 `
    -Model 'qwen3.5:9b' -TimeoutSeconds 120
```

For persisted dialogue with the approved build and real DDInter, create a fresh
synthetic development identity in the dedicated marked database, then launch the
existing application CLI. This guard runs before inserting the identity:

```powershell
$env:CORE_DB_DSN = $env:MODULE2_TEST_DSN
$owner = @'
import os
from uuid import uuid4
import psycopg
from psycopg.conninfo import conninfo_to_dict
dsn = os.environ['CORE_DB_DSN']
options = conninfo_to_dict(dsn)
assert options.get('host') == '127.0.0.1'
assert options.get('port') == '55432'
assert options.get('dbname') == 'msa_core_test_v4nlpe2e20261111checks'
with psycopg.connect(dsn, autocommit=True) as db:
    marker = db.execute("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()").fetchone()[0]
    assert marker == 'Medication Safety Assistant Core V4 isolated test'
    assert db.execute('SELECT msa.published(%s)', ('463cd6c56dc5476fcabf5ad13405a909f3d0254a0043c3d5509140fb92ba1ab9',)).fetchone()[0]
    owner = uuid4()
    db.execute('INSERT INTO identity.users(id) VALUES (%s)', (owner,))
    print(owner)
'@ | & .venv/Scripts/python.exe -X utf8 -B -
if ($LASTEXITCODE -ne 0) { throw 'Development identity setup failed.' }
& .\src\module1_intake\nlp\application_ollama.ps1 `
    -Dsn $env:CORE_DB_DSN -Owner $owner.Trim() `
    -Model 'qwen3.5:9b' -TimeoutSeconds 120 `
    -ReferenceBuild '463cd6c56dc5476fcabf5ad13405a909f3d0254a0043c3d5509140fb92ba1ab9' `
    -DdiIndex $env:MSA_DDINTER_INDEX
```

Use this authored engineering input (exact labels, strengths and forms from
the approved reference), one line at a time:

```text
Thêm vào danh sách thuốc: Harufen 30mg, dạng miếng dán; Altronel 2,5mg, dạng viên nén bao phim.
/json
xác nhận
/identify
/assess
/safety-answer
/exit
```

Review the draft and answer any clarification from the input only before
confirmation. Use `không rõ` for an unknown field. Do not infer missing values
from a product name or clinical knowledge. The backend retains the Major source
level and partial DDInter coverage for this pair; it does not establish safety.
Keep the printed owner/workflow UUIDs to resume with `-Owner` and `-Workflow`.
Live extraction can require clarification; missing evidence must stay unknown.

Coverage includes confirmed intake → Module 2 → sealed snapshot → real Major DDI
→ durable source-backed findings → attributed NLP response; exact local and
DDInter duplicates, missing mappings, absent pairs, alternative mappings,
component-level partial coverage, Core single-medication applicability,
idempotency, build consistency, sample rejection and warning retention after
lookup/composition failures. NLP extraction is a deterministic test provider;
the grounded template/fallback is exercised. Live model inference is separately
opt-in and is not claimed by this real-data run.

The MVP supports this local engineering workflow. The collection is a partial
published release; exact file release version, exhaustive interactions,
patient-specific risk and clinical safety are unvalidated. Mechanism, management
and clinical references are unavailable in these CSVs and remain null.
`safe_to_take` and `no_interactions` remain null; qualified review is required.
DDInter attribution/license: https://ddinter2.scbdd.com/download/ and
CC BY-NC-SA 4.0, https://ddinter2.scbdd.com/terms/ (retained source metadata).
