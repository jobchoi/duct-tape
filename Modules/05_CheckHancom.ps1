param([Parameter(Mandatory=$true)][string]$StateFile)

$state = Get-Content -Path $StateFile -Raw | ConvertFrom-Json

# 확인된 정확한 이름 "한컴오피스 2024 한글 Edu"를 포함하여 검색
$hancomFound = Get-ItemProperty -Path "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*", "HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*" -ErrorAction SilentlyContinue | 
               Where-Object { $_.DisplayName -match "한컴오피스 2024|Hancom|한컴|한글" }

if ($hancomFound) {
    Write-Host " -> 안내: 한컴오피스가 정상적으로 설치되어 있습니다." -ForegroundColor Green
    $state.HancomState = "정상"
} else {
    Write-Host " -> 안내: 한컴오피스 [설치 필요]" -ForegroundColor Yellow
    $state.HancomState = "설치 필요"
}

$state | ConvertTo-Json -Depth 3 | Out-File -FilePath $StateFile -Encoding utf8
exit 0