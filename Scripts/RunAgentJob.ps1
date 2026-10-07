param([switch]$ReportOnly)
$ErrorActionPreference = 'Stop'
try {
    . (Join-Path $PSScriptRoot 'ReportStatus.ps1')
    $sent = Send-StatusReport -StateFile (Join-Path $env:TEMP 'Tapbook_State.json') -Stage Preflight -Status running -ConfigPath (Join-Path (Split-Path $PSScriptRoot -Parent) 'Config/Monitoring.json')
    if (-not $sent) { exit 1 }
    if ($ReportOnly) { exit 0 }
    & (Join-Path (Split-Path $PSScriptRoot -Parent) 'Main.bat') '--unattended'
    exit $LASTEXITCODE
} catch { exit 1 }
