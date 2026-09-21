. (Join-Path $PSScriptRoot 'Common.ps1')
try {
    $null = Get-HancomKey
    Write-DeploymentLog 'KEY_VALIDATED'
    exit 0
} catch {
    Write-DeploymentFailure 'Preflight' $_.Exception.Message
    Write-Host 'Config\HancomKey.txt에 유효한 기관 라이선스 키 한 줄을 입력한 후 다시 실행하세요.'
    exit 1
}
