param(
    [Parameter(Mandatory=$true)]
    [string]$StateFile
)

# 1. 상태 파일 읽어오기
$state = Get-Content -Path $StateFile -Raw | ConvertFrom-Json

if ($state.OfficeState -eq "설치 필요") {
    # # [시각 효과] 설치 시작 전 로딩 애니메이션
    # Write-Host "`n -> 준비 중: 설치를 위한 마법을 부리는 중..." -ForegroundColor Yellow
    # for ($i = 0; $i -lt 5; $i++) {
    #     Write-Host " [▒]" -ForegroundColor Cyan -NoNewline
    #     Start-Sleep -Milliseconds 400
    # }
    # Write-Host " 시작!" -ForegroundColor Green

    # [시각 효과] 안전한 로딩 애니메이션 (특수 문자 대신 '='와 '>' 사용)
    Write-Host "`n -> 준비 중: 설치를 위한 마법을 부리는 중..." -ForegroundColor Yellow
    $bar = ""
    for ($i = 0; $i -lt 10; $i++) {
        $bar += "="
        # 하단에 로딩바를 시각적으로 표현
        Write-Host " [" -NoNewline -ForegroundColor Cyan
        Write-Host $bar.PadRight(10, ".") -NoNewline -ForegroundColor Green
        Write-Host "]" -NoNewline -ForegroundColor Cyan
        Write-Host " 진행 중..." -ForegroundColor Gray
        Start-Sleep -Milliseconds 300
        # 이전 줄을 지우고 다시 그리는 효과
        if ($i -lt 9) { Write-Host "`r" -NoNewline }
    }
    Write-Host " 시작!" -ForegroundColor Green
    
    Write-Host "`n -> 진행 중: Office LTSC 2024를 설치하고 있습니다." -ForegroundColor Cyan
    Write-Host " (화면이 멈춘 것처럼 보여도 백그라운드에서 열심히 작업 중이니 잠시만 기다려주세요!)" -ForegroundColor Gray
    
    $DeployRoot = Split-Path -Path (Split-Path -Path $MyInvocation.MyCommand.Path) -Parent
    $SetupExe = Join-Path -Path $DeployRoot -ChildPath "Office\setup.exe"
    $InstallXml = Join-Path -Path $DeployRoot -ChildPath "Office\install.xml"

    # [시각 효과] 설치 중 진행 상황 표시 (시스템 기본 로딩바)
    Write-Progress -Activity "Office LTSC 2024 설치 중" -Status "설치 파일 배포 및 구성 중..."

    # ODT 설치 실행 (창 숨김)
    $process = Start-Process -FilePath $SetupExe -ArgumentList "/configure `"$InstallXml`"" -Wait -PassThru -WindowStyle Hidden
    
    if ($process.ExitCode -eq 0) {
        Write-Progress -Activity "Office LTSC 2024 설치 중" -Status "완료!" -Completed
        Write-Host "`n -> [성공] Office LTSC 2024 설치 및 정품 인증이 완벽하게 완료되었습니다!" -ForegroundColor Green
        
        $state.OfficeState = "정상"
        $state | ConvertTo-Json -Depth 3 | Out-File -FilePath $StateFile -Encoding utf8
    } else {
        Write-Host "`n -> [오류] 설치 실패 (종료 코드: $($process.ExitCode))" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "`n -> [건너뜀] 이미 Office LTSC 2024가 설치되어 있습니다." -ForegroundColor Green
}

exit 0