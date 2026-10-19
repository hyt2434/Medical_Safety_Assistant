param([string]$Python,[switch]$ResearchData)
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'local-env.ps1')
$interpreter=Initialize-SourceEnvironment -Python $Python
$root=Split-Path $PSScriptRoot -Parent
Push-Location $root
try {
    $options=@()
    if ($ResearchData) { $options+='--research-data' }
    & $interpreter -X utf8 -B scripts/run-tests.py @options
    if ($LASTEXITCODE) { throw 'Regressions failed; see failures or missing data above.' }
} finally { Pop-Location }
