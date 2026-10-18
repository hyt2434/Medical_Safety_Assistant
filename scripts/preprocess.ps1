param([Parameter(Mandatory=$true)][string]$Database,[Parameter(Mandatory=$true)][string]$Config,[string]$Python)
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'local-env.ps1')
$interpreter=Initialize-SourceEnvironment -Python $Python
$root=Split-Path $PSScriptRoot -Parent
Push-Location $root
try {
    foreach ($target in @($Database,$Config)) {
        $resolved=[IO.Path]::GetFullPath((Join-Path $root $target))
        if (-not $resolved.StartsWith((Join-Path $root 'data')+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)) { throw 'Preprocessing outputs must be inside data/.' }
    }
    & $interpreter -X utf8 -B -m module2_medications preprocess --db $Database --config $Config
    exit $LASTEXITCODE
} finally { Pop-Location }
