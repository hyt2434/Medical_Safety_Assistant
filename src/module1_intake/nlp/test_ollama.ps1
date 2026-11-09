param(
    [string]$Model = 'qwen3.5:9b',
    [ValidateRange(1, 3600)][int]$TimeoutSeconds = 60
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '../../..')).Path
$pythonPath = Join-Path $repoRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw 'Repository .venv/Scripts/python.exe is required; install NLP dependencies first.'
}

# Set only this process environment and restore it even if a real check fails.
$names = @('PYTHONPATH', 'NLP_RUN_REAL_OLLAMA', 'NLP_OLLAMA_MODEL', 'NLP_OLLAMA_TIMEOUT')
$saved = @{}
foreach ($name in $names) { $saved[$name] = [Environment]::GetEnvironmentVariable($name, 'Process') }
try {
    $env:PYTHONPATH = Join-Path $repoRoot 'src'
    $env:NLP_RUN_REAL_OLLAMA = '1'
    $env:NLP_OLLAMA_MODEL = $Model
    $env:NLP_OLLAMA_TIMEOUT = [string]$TimeoutSeconds
    Write-Host "Real local Ollama tests: model=$Model timeout=${TimeoutSeconds}s (synthetic data; no DB)"
    & $pythonPath -X utf8 -m pytest -q --tb=short (Join-Path $repoRoot 'tests/integration/test_nlp_ollama.py')
    if ($LASTEXITCODE -ne 0) { throw "Real Ollama tests failed (pytest exit $LASTEXITCODE)." }
}
finally {
    foreach ($name in $names) { [Environment]::SetEnvironmentVariable($name, $saved[$name], 'Process') }
}
