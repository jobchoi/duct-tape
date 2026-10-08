. (Join-Path $PSScriptRoot 'Common.ps1')
. (Join-Path $PSScriptRoot 'OfficeConfiguration.ps1')
try {
    $null = Get-HancomKey
    $null = Get-OfficeProductKey -KeyPath (Join-Path $ConfigDir 'OfficeKey.txt')
    Write-DeploymentLog 'KEY_VALIDATED'
    exit 0
} catch {
    Write-DeploymentFailure 'Preflight' $_.Exception.Message
    Write-Host 'Config\HancomKey.txt와 Config\OfficeKey.txt에 각 제품의 유효한 키를 입력한 후 다시 실행하세요.'
    exit 1
}
