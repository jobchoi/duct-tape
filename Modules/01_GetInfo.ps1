param(
    [Parameter(Mandatory=$true)]
    [string]$StateFile
)

# 🚨 [경로 계산 방식 개선] param 블록 바로 밑에 안전하게 배치!
# 스크립트의 현재 위치와 최상위 duct-tape 루트 경로를 유연하게 동적 매핑합니다.
$ScriptDir = $PSScriptRoot
$DeployRoot = Split-Path -Path $ScriptDir -Parent

$ConfigDir  = Join-Path -Path $DeployRoot -ChildPath "Config"
$HancomDir  = Join-Path -Path $DeployRoot -ChildPath "Hancom"
$ScriptsDir = Join-Path -Path $DeployRoot -ChildPath "Scripts"

# 🚨 [0클릭 프리패스 레이어] 윈도우 보안 경고 팝업 원천 차단
# duct-tape 폴더 내의 모든 모듈(.ps1)과 한컴 설치본(.exe/.msi)의 인터넷 차단 플래그를 백그라운드에서 전부 밀어버립니다.
Write-Host " -> 보안 검사 우회 및 네트워크 파일 차단 해제 중..." -ForegroundColor Gray
Get-ChildItem -Path $DeployRoot -Recurse | Unblock-File -ErrorAction SilentlyContinue

try {
    # 기기 정보 수집
    $bios = Get-CimInstance -ClassName Win32_BIOS -ErrorAction Stop
    $cs = Get-CimInstance -ClassName Win32_ComputerSystem -ErrorAction Stop

    # 다음 단계들로 전달할 상태 데이터(State) 구조체 생성
    $state = @{
        ComputerName = $env:COMPUTERNAME
        SerialNumber = $bios.SerialNumber
        Model        = $cs.Model
        Manufacturer = $cs.Manufacturer
        OfficeState  = "확인 전"
        HancomState  = "확인 전"
        Timestamp    = (Get-Date -Format "yyyy-MM-dd HH:mm")
    }

    # 객체를 JSON으로 변환하여 임시 폴더(%TEMP%)에 저장 (UTF8 인코딩)
    $state | ConvertTo-Json -Depth 3 | Out-File -FilePath $StateFile -Encoding utf8

    Write-Host " -> 성공: 기기 정보 수집 완료 [$($state.ComputerName) / $($state.SerialNumber)]" -ForegroundColor Green
    exit 0
}
catch {
    Write-Host " -> 실패: 기기 정보를 수집하지 못했습니다. 상세: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}