param([switch]$Elevated)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$configPath = Join-Path $root 'Config/Monitoring.json'

function New-ClientMonitoringConfig {
    param([string]$ServerUrl, [string]$ReportToken, [int]$Grade, [string]$SchoolCode)
    $uri = $null
    if (-not [uri]::TryCreate($ServerUrl, [UriKind]::Absolute, [ref]$uri) -or
        $uri.Scheme -ne 'https' -or -not $uri.Host -or $uri.UserInfo -or
        $uri.Query -or $uri.Fragment -or $uri.AbsolutePath -ne '/') {
        throw '서버 주소는 경로가 없는 HTTPS 주소를 입력하세요.'
    }
    if ($ReportToken.Length -lt 32 -or $ReportToken -match '[^\x21-\x7e]') {
        throw '보고 토큰은 공백 없는 ASCII 문자 32자 이상이어야 합니다.'
    }
    if ($Grade -lt 1 -or $Grade -gt 6) { throw '학년은 1~6 사이여야 합니다. 중고등학교는 1~3을 입력하세요.' }
    if ($SchoolCode -and $SchoolCode -cnotmatch '^[A-Z0-9_-]{1,32}$') {
        throw '학교 코드는 영문 대문자, 숫자, 밑줄, 하이픈으로 입력하세요.'
    }
    $config = [ordered]@{Enabled=$true; Grade=$Grade; ServerUrl=$uri.GetLeftPart([UriPartial]::Authority);
        ReportToken=$ReportToken; AllowHttp=$false; TimeoutSeconds=3; MaxAttempts=2}
    if ($SchoolCode) { $config.SchoolCode = $SchoolCode }
    return $config
}

function Read-ClientSecret {
    param([string]$Prompt)
    $secure = Read-Host $Prompt -AsSecureString
    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try { return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer) }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer); $secure.Dispose() }
}

function Set-ClientMonitoring {
    $url = Read-Host '서버 HTTPS 주소 (https://기기이름.tailxxxxx.ts.net)'
    $school = Read-Host '학교 코드 (기본 DUCT_REPORT_TOKEN 사용 시 Enter)'
    $grade = 0
    if (-not [int]::TryParse((Read-Host '학년 (1~6, 중고등 1~3)'), [ref]$grade)) { throw '학년은 정수로 입력하세요.' }
    $token = Read-ClientSecret '보고 토큰 (DUCT_REPORT_TOKEN 또는 학교 전용 토큰)'
    try {
        $config = New-ClientMonitoringConfig -ServerUrl $url.Trim() -ReportToken $token -Grade $grade -SchoolCode $school.Trim()
        $config | ConvertTo-Json | Set-Content -LiteralPath $configPath -Encoding UTF8
    } finally { $token = $null; $config = $null }
    Write-Host 'Config/Monitoring.json 저장 완료. 이 파일에는 보고 토큰이 포함되어 있습니다.'
}

function Test-ClientReporting {
    if (-not (Test-Path -LiteralPath $configPath)) { throw '먼저 1번 메뉴에서 보고 설정을 저장하세요.' }
    $current = Get-Content -LiteralPath $configPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($current.Enabled -ne $true) { throw '보고 설정의 Enabled가 true여야 합니다.' }
    . (Join-Path $PSScriptRoot 'ReportStatus.ps1')
    $sent = Send-StatusReport -StateFile (Join-Path $env:TEMP 'Tapbook_State.json') -Stage Preflight -Status running -ConfigPath $configPath
    if (-not $sent) { throw '보고 실패. Tailscale 연결, 서버 실행, 주소, 보고 토큰 및 학교 코드를 확인하세요.' }
    Write-Host '보고 성공. 대시보드에서 이 PC를 확인하세요. 설치 작업은 실행하지 않았습니다.'
}

# 테스트에서는 함수만 로드합니다.
if ($MyInvocation.InvocationName -eq '.') { return }
try {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $admin = (New-Object Security.Principal.WindowsPrincipal($identity)).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    if (-not $admin) {
        if ($Elevated) { throw '관리자 권한으로 실행해야 합니다.' }
        $process = Start-Process powershell.exe -Verb RunAs -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', ('"' + $PSCommandPath + '"'), '-Elevated') -Wait -PassThru
        exit $process.ExitCode
    }
    while ($true) {
        Write-Host "`n=== duct-tape 클라이언트 ==="
        Write-Host '1. 보고 설정 (최초 1회 또는 변경 시)'
        Write-Host '2. 보고 연결 테스트 (설치 없음)'
        Write-Host '3. Office / 한컴 배포 실행'
        Write-Host '0. 종료'
        $choice = Read-Host '선택'
        try {
            switch ($choice) {
                '1' { Set-ClientMonitoring }
                '2' { Test-ClientReporting }
                '3' {
                    Test-ClientReporting
                    Write-Host '기존 Office/한컴 제거 및 설치가 진행될 수 있습니다. 설치 매체와 라이선스 키를 준비하세요.'
                    if ((Read-Host '배포를 실행하려면 Y 입력') -ieq 'Y') {
                        & (Join-Path $root 'Main.bat')
                        if ($LASTEXITCODE -ne 0) { throw '배포 실패. 화면 오류와 %TEMP%\duct-tape\Deployment.log를 확인하세요.' }
                    }
                }
                '0' { exit 0 }
                default { Write-Host '0~3 중 선택하세요.' }
            }
        } catch { Write-Host $_.Exception.Message -ForegroundColor Red }
    }
} catch {
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}
