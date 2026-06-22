param(
[Parameter(Mandatory=$true)]
[string]$StateFile
)

$state = Get-Content -Path $StateFile -Raw | ConvertFrom-Json

$DeployRoot = Split-Path -Path (Split-Path -Path $MyInvocation.MyCommand.Path) -Parent
$InstallExe = Join-Path -Path $DeployRoot -ChildPath "Hancom\Install.exe"

if ($state.HancomState -eq "설치 필요")
{
Write-Host " -> 기존 한컴 제거 중..." -ForegroundColor Gray

```
Start-Process `
    -FilePath "msiexec.exe" `
    -ArgumentList "/x {2A390EF0-DD11-4267-A387-10DA12D9CAA8} /qn /norestart" `
    -Wait `
    -WindowStyle Hidden

Start-Sleep -Seconds 10

# 실제 제품키 입력
$SerialKey = "실제시디키"

# 설치 로그 생성
$LogFile = Join-Path $env:TEMP "HancomInstall.log"

# PIDKEY 방식 테스트
$argsList = '/s /v"/qn PIDKEY=' + $SerialKey + ' /norestart /l*v C:\Windows\Temp\HancomInstall.log"'

Write-Host " -> 한컴오피스 설치 시작..." -ForegroundColor Cyan
Write-Host " -> 로그 위치 : $LogFile" -ForegroundColor DarkGray

$process = Start-Process `
    -FilePath $InstallExe `
    -ArgumentList $argsList `
    -Wait `
    -PassThru `
    -WindowStyle Hidden

Write-Host " -> 종료 코드 : $($process.ExitCode)"

if ($process.ExitCode -eq 0 -or $process.ExitCode -eq 3010)
{
    Write-Host " -> 설치 완료" -ForegroundColor Green

    $state.HancomState = "정상"

    $state |
        ConvertTo-Json -Depth 3 |
        Out-File -FilePath $StateFile -Encoding utf8
}
else
{
    Write-Host " -> 설치 실패 (코드: $($process.ExitCode))" -ForegroundColor Red
    Write-Host " -> 로그 확인 : C:\Windows\Temp\HancomInstall.log" -ForegroundColor Yellow

    exit 1
}
```

}

exit 0
