param(
    [Parameter(Mandatory=$true)]
    [string]$StateFile
)

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