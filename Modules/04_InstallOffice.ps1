param([Parameter(Mandatory=$true)][string]$StateFile)
. (Join-Path (Split-Path -Path $PSScriptRoot -Parent) 'Scripts/Common.ps1')
try {
    $null = Get-HancomKey
    $state = Read-DeploymentState $StateFile
    if ($state.OfficeState -notin @('정상', '설치 필요')) { throw 'STATE_INVALID' }
    if ($state.OfficeState -eq '설치 필요') {
        $setup = Join-Path $OfficeDir 'setup.exe'
        $xml = Join-Path $OfficeDir 'install.xml'
        Assert-DeploymentFile $setup
        Assert-DeploymentFile $xml
        Write-DeploymentLog '04: Office LTSC 2024 설치 준비'
        for ($i = 1; $i -le 10; $i++) {
            Write-Host ("`r [{0}] 준비 중..." -f ('=' * $i).PadRight(10, '.')) -NoNewline -ForegroundColor Cyan
            Start-Sleep -Milliseconds 300
        }
        Write-Host ''
        Write-Progress -Activity 'Office LTSC 2024 설치 중' -Status '백그라운드 설치 중입니다. 기다려주세요.'
        try { $code = Invoke-DeploymentProcess $setup "/configure `"$xml`"" }
        finally { Write-Progress -Activity 'Office LTSC 2024 설치 중' -Completed }
        Set-RebootRequired $state $code
        $state.OfficeState = '정상'
        Write-DeploymentState $StateFile $state
        Write-DeploymentLog '04: Office 설치 완료. 정품 인증은 별도로 확인하세요.'
    } else { Write-DeploymentLog '04: Office 설치 건너뜀' }

    exit 0
} catch {
    Write-DeploymentFailure '04' $_.Exception.Message
    exit 1
}
