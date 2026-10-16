param([Parameter(Mandatory=$true)][string]$StateFile)
. (Join-Path (Split-Path -Path $PSScriptRoot -Parent) 'Scripts/Common.ps1')
try {
    Send-DeploymentEvent -StateFile $StateFile -Stage '01' -Status running
    $null = Get-HancomKey
    Unblock-DeploymentFiles
    $bios = Get-CimInstance -ClassName Win32_BIOS
    $cs = Get-CimInstance -ClassName Win32_ComputerSystem
    $mac = ''
    try {
        $adapter = Get-CimInstance Win32_NetworkAdapterConfiguration -Filter 'IPEnabled=True' |
            Where-Object { $_.MACAddress } | Sort-Object MACAddress | Select-Object -First 1
        $mac = [string]$adapter.MACAddress
    } catch { }
    $state = [pscustomobject]@{
        ComputerName = $env:COMPUTERNAME
        SerialNumber = $bios.SerialNumber
        Model = $cs.Model
        MAC = $mac
        Manufacturer = $cs.Manufacturer
        OfficeState = '확인 전'
        HancomState = '확인 전'
        Timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
        RebootRequired = $false
    }
    Write-DeploymentState -Path $StateFile -State $state
    Write-DeploymentLog '01: 기기 정보 수집 완료'

    Send-DeploymentEvent -StateFile $StateFile -Stage '01' -Status completed
    exit 0
} catch {
    Write-DeploymentFailure '01' $_.Exception.Message
    exit 1
}
