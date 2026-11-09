param(
    [Parameter(Mandatory=$true)][guid]$Owner,
    [string]$Dsn = $env:CORE_DB_DSN,
    [string]$Model = 'qwen3.5:9b',
    [ValidateRange(1,3600)][int]$TimeoutSeconds = 60,
    [string]$Workflow,
    [string]$ReferenceBuild,
    [string]$Module2Reference,
    [string]$DdiIndex
)
$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '../../..')).Path
$pythonPath = Join-Path $repoRoot '.venv/Scripts/python.exe'
if (-not $Dsn) { throw 'Provide -Dsn or set CORE_DB_DSN to an existing development database.' }
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Repository Python .venv is required.' }
$names = @('PYTHONPATH','CORE_DB_DSN','NLP_OLLAMA_MODEL','NLP_OLLAMA_TIMEOUT')
$saved = @{}
foreach($name in $names) { $saved[$name] = [Environment]::GetEnvironmentVariable($name,'Process') }
try {
    $env:PYTHONPATH = Join-Path $repoRoot 'src'
    $env:CORE_DB_DSN = $Dsn
    $env:NLP_OLLAMA_MODEL = $Model
    $env:NLP_OLLAMA_TIMEOUT = [string]$TimeoutSeconds
    $cliArgs = @('-X','utf8','-m','module1_intake.nlp','--application','--provider','ollama','--owner',[string]$Owner)
    if($Workflow) { $cliArgs += @('--workflow',$Workflow) }
    if($ReferenceBuild) { $cliArgs += @('--reference-build',$ReferenceBuild) }
    if($Module2Reference) { $cliArgs += @('--module2-reference',$Module2Reference) }
    if($DdiIndex) { $cliArgs += @('--ddi-index',$DdiIndex) }
    & $pythonPath @cliArgs
    if($LASTEXITCODE -ne 0) { throw "Application CLI exited with code $LASTEXITCODE." }
}
finally { foreach($name in $names) { [Environment]::SetEnvironmentVariable($name,$saved[$name],'Process') } }
