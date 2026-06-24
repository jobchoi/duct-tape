param([Parameter(Mandatory=$true)][string]$StateFile)

$state = Get-Content -Path $StateFile -Raw | ConvertFrom-Json
$DeployRoot = Split-Path -Path (Split-Path -Path $MyInvocation.MyCommand.Path) -Parent
$InstallExe = Join-Path -Path $DeployRoot -ChildPath "Hancom\Install.exe"

if ($state.HancomState -eq "설치 필요") {
    # [1] 1603 방지: 삭제 후 10초 대기
    Write-Host " -> 기존 정보 정리 및 설치 준비 중..." -ForegroundColor Gray
    Start-Process -FilePath "msiexec.exe" -ArgumentList "/x {2A390EF0-DD11-4267-A387-10DA12D9CAA8} /qn /norestart" -Wait -WindowStyle Hidden
    Start-Sleep -Seconds 10 

    # [2] Install.exe를 통해 제품키를 포함한 무인 설치 실행
    # /s: 자동설치, /v"/qn": 내부 MSI에 자동 설치 옵션 전달
    # $SerialKey = "DVH6H-64YTR-E9WPT-7Q3DY"
    $SerialKey = "---"
    $argsList = '/s /v"/qn SERIALNUMBER=' + $SerialKey + ' /norestart"'
    
    Write-Host " -> 한컴오피스 무인 설치 시작..." -ForegroundColor Cyan
    $process = Start-Process -FilePath $InstallExe -ArgumentList $argsList -Wait -PassThru -WindowStyle Hidden
    
    # 0 혹은 3010(재부팅필요)이면 성공으로 간주
    if ($process.ExitCode -eq 0 -or $process.ExitCode -eq 3010) {
        Write-Host " -> [성공] 한컴오피스 설치 완료!" -ForegroundColor Green
        $state.HancomState = "정상"
        $state | ConvertTo-Json -Depth 3 | Out-File -FilePath $StateFile -Encoding utf8
    } else {
        # 여기서도 1603이 뜨면 제품키가 문제일 확률 99%
        Write-Host " -> [오류] 설치 실패 (코드: $($process.ExitCode))" -ForegroundColor Red
        exit 1
    }
}
exit 0