<#
.SYNOPSIS
Prepare a source checkout without changing any root configuration.
.DESCRIPTION
Run .\scripts\setup.ps1, then .\scripts\test.ps1.
Use -Offline to reuse already installed dependencies without downloading.
Python environment: scripts/.venv. OCR packages/models: src/module1_intake/ocr/node/ocr.
Cloud OCR reads GEMINI_API_KEY from the environment; never add credentials to Git.
Runtime reference data is optional; see scripts/provision-data.ps1 -Detailed help.
#>
param([switch]$Offline)
$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
Push-Location $root
try {
    if (-not (Test-Path 'scripts/.venv/Scripts/python.exe')) {
        py -3 -m venv scripts/.venv
        if ($LASTEXITCODE) { throw 'Python environment creation failed' }
    }
    if ($Offline) {
        & ./scripts/.venv/Scripts/python.exe -B -c "import pydantic, httpx, dotenv; from google import genai"
    } else {
        & ./scripts/.venv/Scripts/python.exe -m pip install -r scripts/requirements.txt
    }
    if ($LASTEXITCODE) { throw 'Python dependency setup failed' }
    if (-not $Offline) {
        Push-Location src/module1_intake/ocr/node/ocr
        try { npm ci; if ($LASTEXITCODE) { throw 'OCR dependency setup failed' } } finally { Pop-Location }
    }
    & ./scripts/.venv/Scripts/python.exe -B scripts/cli.py --help
    if ($LASTEXITCODE) { throw 'Package import failed' }
} finally { Pop-Location }
