param([switch]$ReportOnly,[guid]$JobId)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'JobProgress.ps1')
if ($JobId -ne [guid]::Empty) {$env:DUCT_JOB_ID=$JobId.ToString()}
try {
    Write-JobProgress -Phase starting -Status started
    Write-JobProgress -Phase starting -Status completed
    if (-not $ReportOnly) {
        . (Join-Path $PSScriptRoot 'PrepareAgentMedia.ps1')
        Initialize-AgentMedia -Root (Split-Path $PSScriptRoot -Parent)
    }
    Write-JobProgress -Phase report -Status started
    . (Join-Path $PSScriptRoot 'ReportStatus.ps1')
    $sent = Send-StatusReport -StateFile (Join-Path $env:TEMP 'Tapbook_State.json') -Stage Preflight -Status running -ConfigPath (Join-Path (Split-Path $PSScriptRoot -Parent) 'Config/Monitoring.json')
    if (-not $sent) { Write-JobProgress -Phase report -Status failed;exit 1 }
    Write-JobProgress -Phase report -Status completed
    if ($ReportOnly) { exit 0 }
    & (Join-Path (Split-Path $PSScriptRoot -Parent) 'Main.bat') '--unattended'
    exit $LASTEXITCODE
} catch {Write-JobProgress -Phase error -Status failed;exit 1}
