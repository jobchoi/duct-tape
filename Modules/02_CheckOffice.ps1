param([Parameter(Mandatory=$true)][string]$StateFile)
. (Join-Path (Split-Path -Path $PSScriptRoot -Parent) 'Scripts/Common.ps1')
try {
    $state = Read-DeploymentState $StateFile
    $paths = @('HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*',
        'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*')
    $installed = @(Get-ItemProperty $paths -ErrorAction SilentlyContinue |
        Where-Object { $_.DisplayName -match 'Microsoft Office' -and $_.DisplayName -match 'LTSC Professional Plus 2024' })
    $state.OfficeState = if ($installed.Count -gt 0) { '정상' } else { '설치 필요' }
    Write-DeploymentState $StateFile $state
    Write-DeploymentLog ('02: Office {0}' -f $state.OfficeState)

    exit 0
} catch {
    Write-DeploymentFailure '02' $_.Exception.Message
    exit 1
}
