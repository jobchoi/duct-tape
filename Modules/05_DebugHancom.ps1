Write-Host "--- 한컴오피스 레지스트리 검색 결과 ---" -ForegroundColor Yellow
$keys = Get-ItemProperty -Path "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*" -ErrorAction SilentlyContinue
$hancomItems = $keys | Where-Object { $_.DisplayName -match "한컴|Hancom|한글" }

if ($hancomItems) {
    $hancomItems | ForEach-Object { Write-Host "발견된 이름: $($_.DisplayName)" -ForegroundColor Cyan }
} else {
    Write-Host "검색된 항목이 없습니다. 64비트/32비트 경로를 모두 확인합니다..." -ForegroundColor Red
    # 32비트 경로 추가 검색
    $keys32 = Get-ItemProperty -Path "HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*" -ErrorAction SilentlyContinue
    $hancomItems32 = $keys32 | Where-Object { $_.DisplayName -match "한컴|Hancom|한글" }
    
    if ($hancomItems32) {
        $hancomItems32 | ForEach-Object { Write-Host "32비트 경로에서 발견된 이름: $($_.DisplayName)" -ForegroundColor Green }
    } else {
        Write-Host "결국 찾지 못했습니다. 기기 정보에 등록된 이름이 다를 수 있습니다." -ForegroundColor Red
    }
}
Read-Host "확인 후 엔터를 누르면 종료됩니다."