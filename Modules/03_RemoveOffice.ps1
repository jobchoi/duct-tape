param(
    [Parameter(Mandatory=$true)]
    [string]$StateFile
)

# 1. 상태 파일 읽어오기
if (Test-Path $StateFile) {
    $state = Get-Content -Path $StateFile -Raw | ConvertFrom-Json
} else {
    Write-Host " [오류] 상태 파일을 찾을 수 없습니다." -ForegroundColor Red
    exit 1
}

# 2. 앞 단계(02번)에서 '설치 필요' 판정이 나왔을 때만 삭제 진행
if ($state.OfficeState -eq "설치 필요") {
    Write-Host " -> 진행 중: 기존 Office 버전을 백그라운드에서 삭제하고 있습니다. (1~3분 소요)" -ForegroundColor Cyan
    
    # setup.exe와 remove.xml 경로 자동 지정
    $DeployRoot = Split-Path -Path (Split-Path -Path $MyInvocation.MyCommand.Path) -Parent
    $OfficePath = Join-Path -Path $DeployRoot -ChildPath "Office"
    $SetupExe = Join-Path -Path $OfficePath -ChildPath "setup.exe"
    $RemoveXml = Join-Path -Path $OfficePath -ChildPath "remove.xml"

    if ((Test-Path $SetupExe) -and (Test-Path $RemoveXml)) {
        # ODT 실행 (창 숨김, 완료될 때까지 대기)
        $process = Start-Process -FilePath $SetupExe -ArgumentList "/configure `"$RemoveXml`"" -Wait -PassThru -WindowStyle Hidden
        
        if ($process.ExitCode -eq 0) {
            Write-Host " -> 성공: 기존 Office가 깔끔하게 삭제되었습니다." -ForegroundColor Green
        } else {
            Write-Host " -> 안내: 삭제가 이미 완료되어 있거나 일부 프로세스가 남아있을 수 있습니다. (종료 코드: $($process.ExitCode))" -ForegroundColor Yellow
        }
    } else {
        Write-Host " [오류] Office 폴더 안에 setup.exe 또는 remove.xml 파일이 없습니다!" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host " -> 건너뜐: 이미 목표 버전(LTSC 2024)이 설치되어 있어 삭제 단계를 건너뜁니다." -ForegroundColor Green
}

exit 0