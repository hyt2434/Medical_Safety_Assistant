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
$names = @('PYTHONPATH', 'NLP_OLLAMA_MODEL', 'NLP_OLLAMA_TIMEOUT')
$saved = @{}
foreach ($name in $names) { $saved[$name] = [Environment]::GetEnvironmentVariable($name, 'Process') }
try {
    $env:PYTHONPATH = Join-Path $repoRoot 'src'
    $env:NLP_OLLAMA_MODEL = $Model
    $env:NLP_OLLAMA_TIMEOUT = [string]$TimeoutSeconds
    & $pythonPath -X utf8 -m module1_intake.nlp --nlp-test --provider ollama
    if ($LASTEXITCODE -ne 0) { throw "NLP extraction test exited with code $LASTEXITCODE." }
}
finally {
    foreach ($name in $names) { [Environment]::SetEnvironmentVariable($name, $saved[$name], 'Process') }
}
