param(
    [ValidateSet('Start','Stop','Status')][string]$Action = 'Start',
    [string]$PgBin,
    [string]$RuntimeDirectory,
    [int]$Port = 55432,
    [switch]$ClusterOnly,
    [switch]$Initialize,
    [ValidatePattern('^msa_core_test(?:_[a-z0-9]+)?$')][string]$DatabaseName = 'msa_core_test'
)
$ErrorActionPreference = 'Stop'
if (-not $RuntimeDirectory) {
    # Reuse this workstation's existing cluster before considering a new runtime.
    $workspaceRuntime = Join-Path $PSScriptRoot '../../../artifacts/core_db_phase2'
    $repositoryRuntime = Join-Path $PSScriptRoot '../../artifacts/core_db'
    $RuntimeDirectory = if (Test-Path -LiteralPath (Join-Path $workspaceRuntime 'pgdata/PG_VERSION')) {
        $workspaceRuntime
    } else { $repositoryRuntime }
}
# PowerShell Set-Location does not necessarily update .NET's current directory.
$runtime = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($RuntimeDirectory)
$cluster = Join-Path $runtime 'pgdata'
$bin = if ($PgBin) {
    $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($PgBin)
} else { Join-Path $runtime 'runtime/pgsql/bin' }
foreach ($program in @('pg_ctl.exe', 'postgres.exe', 'psql.exe', 'pg_isready.exe')) {
    if (-not (Test-Path -LiteralPath (Join-Path $bin $program))) {
        throw "PostgreSQL binary missing: $bin/$program. Specify the existing -RuntimeDirectory/-PgBin; no runtime was created."
    }
}
if ($Initialize -and $Action -ne 'Start') { throw '-Initialize is only valid with -Action Start.' }
if ($Initialize -and (Test-Path -LiteralPath "$cluster/PG_VERSION")) {
    throw 'Cluster already initialized; omit -Initialize. Existing cluster data will not be reset.'
}
if (-not (Test-Path -LiteralPath "$cluster/PG_VERSION") -and -not $Initialize) {
    throw "Existing cluster not found at $cluster. Check -RuntimeDirectory. Initialization requires explicit -Initialize."
}
if ((Test-Path -LiteralPath "$cluster/PG_VERSION") -and (Get-Content -LiteralPath "$cluster/PG_VERSION" -Raw).Trim() -ne '18') {
    throw 'This script requires the existing PostgreSQL 18 cluster.'
}
if ((& "$bin/postgres.exe" --version) -notmatch '^postgres \(PostgreSQL\) 18\.') {
    throw 'PostgreSQL 18 binaries are required.'
}
if ($Action -eq 'Stop') {
    & "$bin/pg_ctl.exe" -D $cluster -m fast -w stop
    if ($LASTEXITCODE -ne 0) { throw 'PostgreSQL stop failed' }
    exit
}
if ($Action -eq 'Status') { & "$bin/pg_ctl.exe" -D $cluster status; exit $LASTEXITCODE }
if ($Initialize) {
    if (-not (Test-Path -LiteralPath "$bin/initdb.exe")) { throw 'initdb.exe is missing.' }
    New-Item -ItemType Directory -Force $runtime | Out-Null
    & "$bin/initdb.exe" -D $cluster -U core_fixture_admin --encoding=UTF8 --locale=C --auth=trust
    if ($LASTEXITCODE -ne 0) { throw 'initdb failed' }
    # Trust is restricted to loopback for this isolated synthetic test cluster.
    @'
host all all 127.0.0.1/32 trust
host all all ::1/128 trust
'@ | Set-Content -LiteralPath "$cluster/pg_hba.conf" -Encoding ASCII
    @"
listen_addresses = '127.0.0.1'
port = $Port
timezone = 'UTC'
"@ | Add-Content -LiteralPath "$cluster/postgresql.conf" -Encoding ASCII
}
& "$bin/pg_ctl.exe" -D $cluster status *> $null
$controlStatus = $LASTEXITCODE
if ($controlStatus -ne 0) {
    if ($controlStatus -ne 3) { throw 'Could not inspect PostgreSQL status. Use the Windows account that owns the cluster.' }
    & "$bin/pg_isready.exe" -h 127.0.0.1 -p $Port *> $null
    if ($LASTEXITCODE -eq 0) {
        throw "Port $Port is already accepting connections but pg_ctl cannot confirm this cluster. Check ownership and the runtime path; no second server was started."
    }
    & "$bin/pg_ctl.exe" -D $cluster -l "$runtime/postgres.log" -w start
    if ($LASTEXITCODE -ne 0) { throw 'PostgreSQL startup failed' }
}
# Validate the endpoint against the requested cluster instead of reporting an
# arbitrary server on the same port as a successful startup.
$endpoint = & "$bin/psql.exe" -X -w -h 127.0.0.1 -p $Port -U core_fixture_admin -d postgres -At -F '|' -v ON_ERROR_STOP=1 -c "SELECT current_setting('data_directory'),inet_server_port()"
if ($LASTEXITCODE -ne 0) { throw 'Cluster endpoint check failed. Verify the configured port and local fixture role.' }
$endpointParts = ([string]$endpoint).Trim().Split('|')
if ($endpointParts.Count -ne 2 -or [int]$endpointParts[1] -ne $Port -or
    [IO.Path]::GetFullPath($endpointParts[0]).TrimEnd('\','/') -ine $cluster.TrimEnd('\','/')) {
    throw 'The connected server does not match the requested data directory and port.'
}
if ($ClusterOnly) {
    Write-Output "PostgreSQL 18 test cluster ready on 127.0.0.1:$Port; data=$cluster; no database created."
    exit
}
$found = & "$bin/psql.exe" -X -w -h 127.0.0.1 -p $Port -U core_fixture_admin -d postgres -At -v ON_ERROR_STOP=1 -c "SELECT 1 FROM pg_database WHERE datname='$DatabaseName'"
if ($LASTEXITCODE -ne 0) { throw 'Could not check the existing database.' }
if ($found -ne '1') {
    throw "Database $DatabaseName does not exist. Startup never creates databases; select an existing -DatabaseName."
}
Write-Output "CORE_DB_DSN=host=127.0.0.1 port=$Port dbname=$DatabaseName user=core_fixture_admin"
