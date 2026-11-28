<#
.SYNOPSIS
Run the live acceptance suites against the app that is ALREADY running locally.
.DESCRIPTION
Start the app first (python scripts/preview-ui.py). This writes real, append-only
records to the configured database, so use it only on a test database.

  .\scripts\run-acceptance.ps1            # API + UI, including slow model/dose-time tests (~15 min)
  .\scripts\run-acceptance.ps1 -Fast      # skip Qwen/Whisper/OCR and the dose-time wait (~3 min)
  .\scripts\run-acceptance.ps1 -ApiOnly   # pytest only
  .\scripts\run-acceptance.ps1 -UiOnly -Headed   # watch the browser

Reports: artifacts/acceptance/api-report.html (+ .xml), artifacts/acceptance/ui-report/index.html,
screenshots in artifacts/acceptance/screens/. Test IDs map to docs/testing/manual-test-plan.md.
#>
param([switch]$Fast, [switch]$ApiOnly, [switch]$UiOnly, [switch]$Headed)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$python = Join-Path $root '.venv/Scripts/python.exe'
$failed = $false
New-Item -ItemType Directory -Force (Join-Path $root 'artifacts/acceptance') | Out-Null
Push-Location $root
try {
    try { Invoke-WebRequest -UseBasicParsing -TimeoutSec 5 http://127.0.0.1:8000/health | Out-Null }
    catch { throw 'Backend is not running on 127.0.0.1:8000. Start it with: python scripts/preview-ui.py' }
    if (-not $UiOnly) {
        $env:ACCEPTANCE_LIVE = '1'
        $env:ACCEPTANCE_SLOW = if ($Fast) { '0' } else { '1' }
        $html = @()
        & $python -c "import pytest_html" 2>$null
        if ($LASTEXITCODE -eq 0) { $html = @('--html', 'artifacts/acceptance/api-report.html', '--self-contained-html') }
        else { Write-Output 'Tip: pip install pytest-html for artifacts/acceptance/api-report.html' }
        & $python -X utf8 -m pytest tests/acceptance -v -p no:cacheprovider -rfxX `
            --junitxml artifacts/acceptance/api-report.xml @html
        if ($LASTEXITCODE) { $failed = $true }
    }
    if (-not $ApiOnly) {
        Push-Location apps/frontend
        try {
            if ($Headed) { $env:HEADED = '1' }
            # npm prints version warnings on stderr; they must not abort the run.
            $ErrorActionPreference = 'Continue'
            npx.cmd playwright test -c playwright.live.config.ts 2>&1 | ForEach-Object { "$_" }
            if ($LASTEXITCODE) { $failed = $true }
        } finally { Pop-Location }
    }
} finally { Pop-Location }
if ($failed) { Write-Output 'Some acceptance tests failed; see the reports above.'; exit 1 }
Write-Output 'All acceptance tests passed.'
