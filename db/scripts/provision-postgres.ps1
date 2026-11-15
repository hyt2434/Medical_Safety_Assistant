param(
    [string]$Archive,
    [string]$RuntimeDirectory = (Join-Path $PSScriptRoot '../../artifacts/core_db')
)
$ErrorActionPreference='Stop'
$runtime=[IO.Path]::GetFullPath($RuntimeDirectory)
New-Item -ItemType Directory -Force $runtime | Out-Null
if (-not $Archive) {
    $Archive=Join-Path $runtime 'postgresql.zip'
    if (-not (Test-Path -LiteralPath $Archive)) {
        Invoke-WebRequest 'https://get.enterprisedb.com/postgresql/postgresql-18.6-5-windows-x64-binaries.zip' -OutFile $Archive
    }
}
# Pin the exact archive exercised in Phase 2. This is a reproducibility hash,
# not a claim that the publisher independently supplied a signature/checksum.
$expected='E2246BA91D22345BC3D017586C09EDE52D9DF180B1EEB480F050445F1CAD84E2'
if ((Get-FileHash -LiteralPath $Archive -Algorithm SHA256).Hash -ne $expected) { throw 'Unexpected PostgreSQL archive hash' }
$bin=Join-Path $runtime 'runtime/pgsql/bin'
if ((Test-Path "$bin/postgres.exe") -and (Test-Path "$bin/pg_ctl.exe") -and (Test-Path "$bin/initdb.exe") -and (Test-Path "$bin/psql.exe")) {
    $version=& "$bin/postgres.exe" --version
    if ($version -ne 'postgres (PostgreSQL) 18.6') { throw 'Unexpected installed PostgreSQL version' }
    Write-Output $bin
    exit
}
Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip=[IO.Compression.ZipFile]::OpenRead([IO.Path]::GetFullPath($Archive))
try {
    foreach ($entry in $zip.Entries) {
        if ($entry.FullName -match '^pgsql/(bin|lib|share)/' -and $entry.Name) {
            $target=[IO.Path]::GetFullPath((Join-Path $runtime ('runtime/'+$entry.FullName)))
            if (-not $target.StartsWith(($runtime+[IO.Path]::DirectorySeparatorChar),[StringComparison]::OrdinalIgnoreCase)) { throw 'Unsafe archive path' }
            [IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($target)) | Out-Null
            [IO.Compression.ZipFileExtensions]::ExtractToFile($entry,$target,$true)
        }
    }
} finally { $zip.Dispose() }
Write-Output (Join-Path $runtime 'runtime/pgsql/bin')
