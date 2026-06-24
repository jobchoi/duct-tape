param(
    [Parameter(Mandatory=$true)]
    [string]$StateFile
)

# 🚨 [경로 계산 방식 일원화] 네트워크(UNC) 환경 완벽 대응
$ScriptDir = $PSScriptRoot
$DeployRoot = Split-Path -Path $ScriptDir -Parent

# 디렉토리 구조 동적 맵핑 (상관없는 구조 일절 건드리지 않고 인지 처리)
$ConfigDir  = Join-Path -Path $DeployRoot -ChildPath "Config"
$HancomDir  = Join-Path -Path $DeployRoot -ChildPath "Hancom"

# 🚨 [알맹이 MSI 직접 정밀 조준] 블로그 교훈 반영 구조
$MsiFile     = Join-Path -Path $HancomDir -ChildPath "Install\Hwp130.msi"
$VCRedistX86 = Join-Path -Path $HancomDir -ChildPath "Install\VC_redist.x86.exe"
$KeyFilePath = Join-Path -Path $ConfigDir -ChildPath "HancomKey.txt"

# 0. 상태 데이터 로드
$state = Get-Content -Path $StateFile -Raw | ConvertFrom-Json

if ($state.HancomState -eq "설치 필요")
{
    Write-Host "[6/7] 한컴오피스 2024 MSI 다이렉트 무인 배포를 시작합니다..." -ForegroundColor Cyan

    # 🚨 [좀비 프로세스 강제 소거] 꼬여서 화면 뒤에 멈춰있던 엔진 클리어
    Write-Host " -> 잔존하는 기존 설치 엔진 좀비 프로세스 청소 중..." -ForegroundColor Gray
    Stop-Process -Name "Install", "setup", "msiexec" -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2

    # 1. 시스템 내 잔존하는 모든 구버전 한컴오피스(2018~2022) 동적 검색 후 무인 박멸
    Write-Host " -> 시스템 내 잔존하는 모든 구버전 한컴오피스 추적 제거 중..." -ForegroundColor Gray
    $RegPaths = @(
        "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*", 
        "HKLM:\SOFTWARE\Wow6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*"
    )
    $OldHancoms = Get-ItemProperty $RegPaths -ErrorAction SilentlyContinue | 
                  Where-Object { $_.DisplayName -like "*한컴오피스*" -and $_.DisplayName -notlike "*2024*" }

    foreach ($app in $OldHancoms) {
        if ($app.UninstallString) {
            Write-Host " -> 구버전 강제 박멸 가동: $($app.DisplayName)" -ForegroundColor Yellow
            if ($app.PSChildName -like "{*}") {
                # MSI 기반 GUID 자동 사일런트 컷
                Start-Process -FilePath "msiexec.exe" -ArgumentList "/x $($app.PSChildName) /qn /norestart" -Wait -WindowStyle Hidden
            } else {
                # 일반 EXE 언인스톨러 대응
                Start-Process -FilePath $app.UninstallString -ArgumentList "/s /v`"/qn`"" -Wait -WindowStyle Hidden
            }
        }
    }
    Start-Sleep -Seconds 3

    # 2. 마스터가 파워쉘 단독 검증 완료한 VC++ x86 무인 옵션 선제 주입
    if (Test-Path $VCRedistX86) {
        Write-Host " -> 한컴 필수 구성 요소(VC++ x86) 무인 사전 설치 중..." -ForegroundColor Gray
        Start-Process -FilePath $VCRedistX86 -ArgumentList "/install /quiet /norestart" -Wait -WindowStyle Hidden
        Start-Sleep -Seconds 3
    }

    # 3. Config\HancomKey.txt 파일로부터 안전하게 시디키 로드
    if (-not (Test-Path $KeyFilePath)) { 
        Write-Host " -> [에러] 시디키 파일($KeyFilePath)을 찾을 수 없습니다!" -ForegroundColor Red
        exit 1 
    }
    $SerialKey = (Get-Content -Path $KeyFilePath -Raw).Trim()
    
    # 4. Windows 표준 커널 엔진을 이용한 100% 무UI 강제 주입
    # /i : 설치, /qn : UI 완전 폐쇄(숨김), AGREETOLICENSE=yes : 무인 동의 강제 수락
    $LogFile = "C:\Windows\Temp\HancomMSIInstall.log"
    $argsList = "/i `"$MsiFile`" /qn AGREETOLICENSE=yes PIDKEY=$SerialKey /norestart /l*v `"$LogFile`""

    Write-Host " -> 한컴오피스 2024 무음 커널 주입 중 (창 차단)..." -ForegroundColor Cyan
    Write-Host " -> 로그 추적 위치 : $LogFile" -ForegroundColor DarkGray
    
    # msiexec는 OS 기본 프로세스이므로 WindowStyle Hidden이 완벽히 무결하게 작동합니다.
    $process = Start-Process -FilePath "msiexec.exe" -ArgumentList $argsList -Wait -PassThru -WindowStyle Hidden

    Write-Host " -> MSI 무인 설치 종료 코드 : $($process.ExitCode)"

    # 5. 결과 처리 및 파일 동적 갱신
    if ($process.ExitCode -eq 0 -or $process.ExitCode -eq 3010) {
        Write-Host " -> 한컴오피스 2024 최종 배포 성공!" -ForegroundColor Green
        $state.HancomState = "정상"
        $state | ConvertTo-Json -Depth 3 | Out-File -FilePath $StateFile -Encoding utf8 -Force
    } else {
        Write-Host " -> [에러] 한컴오피스 2024 MSI 설치 실패 (종료 코드: $($process.ExitCode))" -ForegroundColor Red
        exit 1
    }
}
else
{
    Write-Host " -> [건너뜀] 한컴오피스 2024가 이미 정상 설치되어 있습니다." -ForegroundColor Gray
}

exit 0