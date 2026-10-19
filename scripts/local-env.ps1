# Dot-source this file from development scripts. All generated files stay under
# the allowed trees. The root project does not need an editable installation.
function Initialize-SourceEnvironment {
    param([string]$Python)
    $root=Split-Path $PSScriptRoot -Parent
    $env:PYTHONPATH=Join-Path $root 'src'
    $env:PYTHONDONTWRITEBYTECODE='1'
    if ($Python) { return $Python }
    $interpreter=Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
    if (-not (Test-Path -LiteralPath $interpreter)) {
        throw 'Run scripts/setup.ps1 first, or pass -Python with an existing interpreter.'
    }
    return $interpreter
}
