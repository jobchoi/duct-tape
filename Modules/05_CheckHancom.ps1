param(
    [Parameter(Mandatory=$true)]
    [string]$StateFile
)

# 🚨 [경로 계산 방식 일원화] 네트워크(UNC) 공유 및 폴더명 변경(duct-tape) 대응 목적
$ScriptDir = $PSScriptRoot
$DeployRoot = Split-Path -Path $ScriptDir -Parent

# 0. 상태 데이터 로드
$state = Get-Content -Path $StateFile -Raw | ConvertFrom-Json

Write-Host "[5/8] 한컴오피스 2024 설치 상태를 확인하는 중..." -ForegroundColor Cyan

# 1. 2024 버전의 진짜 한글 실행 파일 경로 지정
$Hancom2024Path = "C:\Program Files (x86)\Hnc\HOffice2024\Bin\Hwp.exe"
$IsVersion2024 = $false

# 2. 판정 로직 고도화: 파일이 존재하고, 내부 제품 버전이 13(2024) 계열인지 교차 검증
if (Test-Path $Hancom2024Path)
{
    $FileVersion = (Get-Item $Hancom2024Path).VersionInfo.ProductVersion
    if ($FileVersion -like "13.*") {
        $IsVersion2024 = $true
    }
}

if ($IsVersion2024)
{
    Write-Host " -> 안내: 한컴오피스 2024가 정상적으로 설치되어 있습니다." -ForegroundColor Green
    $state.HancomState = "정상"
}
else
{
    # 구버전(2018 등)이 깔려 있거나 미설치 시 무조건 '설치 필요' 판정!
    Write-Host " -> [미탐지] 한컴오피스 2024가 없거나 구버전이 감지되었습니다. 교체가 필요합니다." -ForegroundColor Yellow
    $state.HancomState = "설치 필요"
}

# 3. 상태 파일 업데이트 (안전한 인코딩 저장 처리)
$state | ConvertTo-Json -Depth 3 | Out-File -FilePath $StateFile -Encoding utf8 -Force
exit 0