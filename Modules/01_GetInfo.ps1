param([Parameter(Mandatory=$true)][string]$StateFile)
. (Join-Path (Split-Path -Path $PSScriptRoot -Parent) 'Scripts/Common.ps1')
try {
    $null = Get-HancomKey
    Unblock-DeploymentFiles
    $bios = Get-CimInstance -ClassName Win32_BIOS
    $cs = Get-CimInstance -ClassName Win32_ComputerSystem
    $state = [pscustomobject]@{
        ComputerName = $env:COMPUTERNAME
        SerialNumber = $bios.SerialNumber
        Model = $cs.Model
        Manufacturer = $cs.Manufacturer
        OfficeState = '확인 전'
        HancomState = '확인 전'
        Timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
        RebootRequired = $false
    }
    Write-DeploymentState -Path $StateFile -State $state
    Write-DeploymentLog '01: 기기 정보 수집 완료'

    exit 0
} catch {
    Write-DeploymentFailure '01' $_.Exception.Message
    exit 1
}
