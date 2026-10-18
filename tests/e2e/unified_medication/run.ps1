param([string]$RunId=('run_'+(Get-Date -Format 'yyyyMMdd_HHmmss_fff')))
& (Join-Path $PSScriptRoot '../../../scripts/run-e2e.ps1') -RunId $RunId
exit $LASTEXITCODE
