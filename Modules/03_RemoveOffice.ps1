param([Parameter(Mandatory=$true)][string]$StateFile)
. (Join-Path (Split-Path -Path $PSScriptRoot -Parent) 'Scripts/Common.ps1')
try {
    Send-DeploymentEvent -StateFile $StateFile -Stage '03' -Status running
    $null = Get-HancomKey
    $state = Read-DeploymentState $StateFile
    if ($state.OfficeState -notin @('정상', '설치 필요')) { throw 'STATE_INVALID' }
    if ($state.OfficeState -eq '설치 필요') {
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
