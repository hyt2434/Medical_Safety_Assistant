param([string]$RunId=('run_'+(Get-Date -Format 'yyyyMMdd_HHmmss_fff')),[string]$Python)
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'local-env.ps1')
$interpreter=Initialize-SourceEnvironment -Python $Python
if ($RunId -notmatch '^[A-Za-z0-9_-]+$') { throw 'Invalid RunId' }
$root=Split-Path $PSScriptRoot -Parent
Push-Location $root
try {
    $env:PYTHONPATH=Join-Path $root 'src'
    & $interpreter -X utf8 -B scripts/verify_runtime.py
    if ($LASTEXITCODE) { throw 'Required local runtime data is unavailable; see scripts/provision-data.ps1 help.' }
    & $interpreter -X utf8 -B -u tests/e2e/unified_medication/run.py --output ('tests/artifacts/e2e/'+$RunId)
    $executionExit=$LASTEXITCODE
    if ($executionExit -notin @(0,1,2)) { throw 'E2E runner crashed' }
    & $interpreter -X utf8 -B scripts/compare_baseline.py ('tests/artifacts/e2e/'+$RunId)
    exit $LASTEXITCODE
} finally { Pop-Location }
