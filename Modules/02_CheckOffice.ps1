param(
    [Parameter(Mandatory=$true)]
    [string]$StateFile
)

# 1. 1단계에서 만든 상태 파일(JSON) 읽어오기
if (Test-Path $StateFile) {
    $state = Get-Content -Path $StateFile -Raw | ConvertFrom-Json
} else {
    Write-Host " [오류] 상태 파일을 찾을 수 없습니다." -ForegroundColor Red
    exit 1
}

$officeInstalled = $false

# 2. 64비트 및 32비트(WOW6432Node) 레지스트리 설치 경로 모두 탐색
$paths = @(
    "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*",
    "HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*"
)

# 조용히 레지스트리를 뒤져서 'Microsoft Office'라는 이름이 들어간 프로그램 찾기
$installedPrograms = Get-ItemProperty $paths -ErrorAction SilentlyContinue | Where-Object { $_.DisplayName -ne $null }

foreach ($app in $installedPrograms) {
    if ($app.DisplayName -match "Microsoft Office") {
        # 목표 버전인 LTSC 2024가 맞는지 판별
        if ($app.DisplayName -match "LTSC Professional Plus 2024") {
            $officeInstalled = $true
            break
        }
    }
}

# 3. 판별 결과에 따라 상태 업데이트 및 화면 출력
if ($officeInstalled) {
    $state.OfficeState = "정상"
    Write-Host " -> 성공: Office 상태 [정상] (LTSC 2024 확인됨)" -ForegroundColor Green
} else {
    $state.OfficeState = "설치 필요"
    Write-Host " -> 안내: Office 상태 [설치 필요] (기존 버전 삭제 및 LTSC 2024 설치 필요)" -ForegroundColor Yellow
}

# 4. 변경된 상태를 다시 JSON 파일에 덮어쓰기 (다음 단계를 위해)
$state | ConvertTo-Json -Depth 3 | Out-File -FilePath $StateFile -Encoding utf8

exit 0