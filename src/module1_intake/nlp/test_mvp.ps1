param(
    [string]$Dsn = $env:NLP_TEST_DSN,
    [switch]$RealOllama,
    [switch]$Bootstrap,
    [string]$Model = 'qwen3.5:9b'
)
$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '../../..')).Path
$pythonPath = Join-Path $repoRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Repository Python .venv is required.' }
if ($Bootstrap -and -not $Dsn) { throw '-Bootstrap requires a dedicated NLP test DSN.' }
$names = @('PYTHONPATH','NLP_TEST_DSN','NLP_TEST_BOOTSTRAP','NLP_RUN_REAL_OLLAMA','NLP_OLLAMA_MODEL','NLP_OLLAMA_TIMEOUT')
$saved = @{}
foreach($name in $names) { $saved[$name] = [Environment]::GetEnvironmentVariable($name,'Process') }
try {
    $env:PYTHONPATH = Join-Path $repoRoot 'src'
    $env:NLP_TEST_DSN = $Dsn
    $env:NLP_TEST_BOOTSTRAP = if($Bootstrap) { '1' } else { '0' }
    $env:NLP_RUN_REAL_OLLAMA = if($RealOllama) { '1' } else { '0' }
    $env:NLP_OLLAMA_MODEL = $Model
    $env:NLP_OLLAMA_TIMEOUT = '120'
    $testPaths = @('tests/unit/test_nlp.py','tests/unit/test_nlp_diagnostics.py','tests/unit/test_nlp_interactive.py',
        'tests/unit/test_nlp_semantics.py','tests/unit/test_nlp_mvp.py','tests/unit/test_nlp_architecture.py','tests/integration/test_nlp_v4.py',
        'tests/integration/test_nlp_mvp_v4.py','tests/integration/test_nlp_ollama.py') | ForEach-Object { Join-Path $repoRoot $_ }
    $report = Join-Path $repoRoot 'artifacts/nlp_mvp_v2/junit.xml'
    & $pythonPath -X utf8 -m pytest -q --tb=short "--junitxml=$report" @testPaths
    if($LASTEXITCODE -ne 0) { throw "NLP MVP tests failed (pytest exit $LASTEXITCODE)." }
}
finally { foreach($name in $names) { [Environment]::SetEnvironmentVariable($name,$saved[$name],'Process') } }
