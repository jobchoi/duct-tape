param([switch]$Elevated)
$ErrorActionPreference = 'Stop'
try {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $admin = (New-Object Security.Principal.WindowsPrincipal($identity)).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    if (-not $admin) {
        if ($Elevated) { throw '관리자 권한이 필요합니다.' }
        $p = Start-Process powershell.exe -Verb RunAs -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File',('"'+$PSCommandPath+'"'),'-Elevated') -Wait -PassThru
        exit $p.ExitCode
    }
    $source = Split-Path $PSScriptRoot -Parent
    $target = Join-Path $env:ProgramData 'DuctTapeAgent'
    if (Test-Path (Join-Path $target 'Config/Agent.json')) { throw '이미 등록된 에이전트입니다. 기존 작업과 등록 상태를 확인하세요.' }
    if (Get-ScheduledTask -TaskName 'DuctTapeAgent' -ErrorAction SilentlyContinue) { throw '기존 DuctTapeAgent 작업을 먼저 확인하세요.' }
    . (Join-Path $PSScriptRoot 'ClientSetup.ps1')
    $generatedConfig = -not (Test-Path $configPath)
    if ($generatedConfig) {
        $url = Read-Host '서버 HTTPS 주소'
        $monitor = New-ClientMonitoringConfig -ServerUrl $url.Trim() -ReportToken ('x' * 40) -Grade 1
    } else {
        $monitor = Get-Content $configPath -Raw -Encoding UTF8 | ConvertFrom-Json
        $null = New-ClientMonitoringConfig -ServerUrl $monitor.ServerUrl -ReportToken $monitor.ReportToken -Grade $monitor.Grade -SchoolCode $monitor.SchoolCode
        if ($monitor.Enabled -ne $true) { throw '보고 설정을 활성화하세요.' }
    }
    if (-not (Test-Path (Join-Path $source 'Config/HancomKey.txt'))) { throw 'Config/HancomKey.txt에 라이선스 키를 준비하세요.' }
    foreach ($name in @('Main.bat','Scripts','Modules','Config','Office','Hancom')) {
        if (-not (Test-Path (Join-Path $source $name))) { throw "필수 배포 파일/폴더 누락: $name" }
    }
    if (Test-Path $target) { throw '전용 설치 폴더가 이미 있습니다. 기존 설치 상태를 담당자가 확인하세요.' }
    New-Item -ItemType Directory -Path $target | Out-Null
    & icacls.exe $target /inheritance:r /grant:r '*S-1-5-18:(OI)(CI)F' '*S-1-5-32-544:(OI)(CI)F' | Out-Null
    if ($LASTEXITCODE -ne 0) { throw '에이전트 폴더 접근 권한 설정에 실패했습니다.' }
    foreach ($name in @('Main.bat','Scripts','Modules','Office','Hancom')) {
        if ([IO.Path]::GetFullPath($source) -ne [IO.Path]::GetFullPath($target)) {
            Copy-Item -LiteralPath (Join-Path $source $name) -Destination $target -Recurse -Force
        }
    }
    New-Item -ItemType Directory -Path (Join-Path $target 'Config') | Out-Null
    Copy-Item -LiteralPath (Join-Path $source 'Config/HancomKey.txt') -Destination (Join-Path $target 'Config')
    $id = ([guid](Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Cryptography').MachineGuid).ToString()
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    $body = @{device_id=$id; hostname=$env:COMPUTERNAME} | ConvertTo-Json -Compress
    try {
        $registered = Invoke-RestMethod -Uri ($monitor.ServerUrl.TrimEnd('/')+'/api/agent/join') -Method Post -ContentType 'application/json' -Body $body -TimeoutSec 10 -MaximumRedirection 0
    } catch { throw '연결 요청 실패. Tailscale, 서버 주소 및 기존 연결 여부를 확인하세요.' }
    if ($generatedConfig) { $monitor.ReportToken = $registered.agent_token }
    $monitor | ConvertTo-Json | Set-Content (Join-Path $target 'Config/Monitoring.json') -Encoding UTF8
    @{ServerUrl=$monitor.ServerUrl.TrimEnd('/'); AgentToken=$registered.agent_token; DeviceId=$id} | ConvertTo-Json | Set-Content (Join-Path $target 'Config/Agent.json') -Encoding UTF8
    $action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument ('-NoProfile -ExecutionPolicy Bypass -File "'+(Join-Path $target 'Scripts/Agent.ps1')+'"') -WorkingDirectory $target
    $trigger = New-ScheduledTaskTrigger -AtStartup
    $principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
    $settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
    Register-ScheduledTask -TaskName 'DuctTapeAgent' -Action $action -Trigger $trigger -Principal $principal -Settings $settings | Out-Null
    $url = $monitor.ServerUrl.TrimEnd('/')+'/client#key='+$registered.client_token
    $desktop = [Environment]::GetFolderPath('CommonDesktopDirectory')
    "[InternetShortcut]`r`nURL=$url" | Set-Content (Join-Path $desktop 'duct-tape 작업.url') -Encoding ASCII
    Start-ScheduledTask -TaskName 'DuctTapeAgent'
    Write-Host '서버에 연결을 요청했습니다. 관리자가 PC 연결을 승인하면 바탕화면 바로가기에서 환경 셋업을 시작하세요.'
    Write-Host '등록 코드나 접속 키를 입력할 필요가 없습니다. 배포 매체는 ProgramData\DuctTapeAgent에 보관됩니다.'
} catch {
    Write-Host $_.Exception.Message -ForegroundColor Red
    Write-Host '서버 등록 후 실패했다면 관리자 페이지에서 해당 PC 등록을 해제한 후 로컬 상태를 확인하세요.'
    exit 1
}
