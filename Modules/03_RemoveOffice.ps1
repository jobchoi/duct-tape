param([Parameter(Mandatory=$true)][string]$StateFile)
. (Join-Path (Split-Path -Path $PSScriptRoot -Parent) 'Scripts/Common.ps1')
try {
    Send-DeploymentEvent -StateFile $StateFile -Stage '03' -Status running
    $state = Read-DeploymentState $StateFile
    if ($state.OfficeState -notin @('정상', '설치 필요')) { throw 'STATE_INVALID' }
    if ($state.OfficeState -eq '설치 필요') {
        # Installation need does not imply an existing product needs removal.
        # Read only machine-wide inventory; Win32_Product can trigger MSI repairs.
        $paths = @('HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*',
            'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*')
        $existingPaths = @($paths | Where-Object { Test-Path -LiteralPath ($_ -replace '\\\*$', '') })
        $entries = @($(foreach ($path in $existingPaths) { Get-ItemProperty -Path $path -ErrorAction Stop }) |
            Where-Object { $_.DisplayName -match '(?i)^(Microsoft (Office|365|Visio|Project)\b|Office (16|15) Click-to-Run)' })
        $configurationPaths = @('HKLM:\SOFTWARE\Microsoft\Office\ClickToRun\Configuration',
            'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Office\ClickToRun\Configuration')
        $hasConfiguration = $false
        foreach ($path in $configurationPaths) {
            if (Test-Path -LiteralPath $path) { $hasConfiguration = $true }
        }
        $service = Get-Service -Name 'ClickToRunSvc' -ErrorAction SilentlyContinue
        if ($entries.Count -eq 0 -and -not $hasConfiguration -and $null -eq $service) {
            Write-DeploymentLog '03: OFFICE_REMOVE_SKIPPED_NO_PRODUCT: 기존 Office 없음, 제거 건너뜀'
            Send-DeploymentEvent -StateFile $StateFile -Stage '03' -Status completed
            exit 0
        }
        # Click-to-Run registers MSI helper components (Licensing/Extensibility/Localization).
        # They belong to C2R and are removed with it, so they are not a standalone MSI Office.
        if (@($entries | Where-Object { $_.WindowsInstaller -eq 1 -and $_.DisplayName -notmatch '(?i)Click-to-Run' }).Count -gt 0) {
            throw 'OFFICE_MSI_REMOVAL_REQUIRED'
        }
        if ($null -eq $service) { throw 'OFFICE_C2R_SERVICE_MISSING' }
        if ($service.Status -ne 'Running') { throw 'OFFICE_C2R_SERVICE_NOT_RUNNING' }

        $setup = Join-Path $OfficeDir 'setup.exe'
        $xml = Join-Path $OfficeDir 'remove.xml'
        Assert-DeploymentFile $setup
        Assert-DeploymentFile $xml
        Assert-DeploymentFile (Join-Path $OfficeDir 'install.xml')
        $code = Invoke-DeploymentProcess $setup "/configure `"$xml`""
        Set-RebootRequired $state $code
        Write-DeploymentState $StateFile $state
        Write-DeploymentLog '03: Office 제거 완료'
    } else { Write-DeploymentLog '03: Office 제거 건너뜀' }

    Send-DeploymentEvent -StateFile $StateFile -Stage '03' -Status completed
    exit 0
} catch {
    Write-DeploymentFailure '03' $_.Exception.Message
    exit 1
}
