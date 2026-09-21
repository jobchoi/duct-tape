param([Parameter(Mandatory=$true)][string]$StateFile)
. (Join-Path (Split-Path -Path $PSScriptRoot -Parent) 'Scripts/Common.ps1')
try {
    Send-DeploymentEvent -StateFile $StateFile -Stage '05' -Status running
    $state = Read-DeploymentState $StateFile
    $path = 'C:\Program Files (x86)\Hnc\HOffice2024\Bin\Hwp.exe'
    $is2024 = $false
    if (Test-Path -LiteralPath $path -PathType Leaf) {
        $version = (Get-Item -LiteralPath $path).VersionInfo.ProductVersion
        $is2024 = $version -like '13.*'
    }
    $state.HancomState = if ($is2024) { '정상' } else { '설치 필요' }
    Write-DeploymentState $StateFile $state
    Write-DeploymentLog ('05: 한컴 {0}' -f $state.HancomState)

    Send-DeploymentEvent -StateFile $StateFile -Stage '05' -Status completed
    exit 0
} catch {
    Write-DeploymentFailure '05' $_.Exception.Message
    exit 1
}
