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
    if (Test-Path (Join-Path $target 'Config/ActiveJob.json')) { throw '진행 중 또는 결과 확인 중인 작업이 있습니다. 실제 PC 작업 상태를 확인한 뒤 복구하세요.' }
    try { $stored = if (Test-Path (Join-Path $target 'Config/Agent.json')) { Get-Content (Join-Path $target 'Config/Agent.json') -Raw -Encoding UTF8 | ConvertFrom-Json } else { $null } } catch { throw '로컬 에이전트 설정을 읽을 수 없습니다. 설정 복구가 필요합니다.' }
    . (Join-Path $PSScriptRoot 'AgentRegistration.ps1')
    . (Join-Path $PSScriptRoot 'ClientSetup.ps1')
    $monitorPath = if (Test-Path $configPath) { $configPath } elseif (Test-Path (Join-Path $target 'Config/Monitoring.json')) { Join-Path $target 'Config/Monitoring.json' } else { $null }
    $generatedConfig = $null -eq $monitorPath
    if ($generatedConfig) {
        $addressFile = Join-Path $source 'Config/ServerUrl.txt'
        $url = if (Test-Path $addressFile) { (Get-Content $addressFile -Raw).Trim() } else { Read-Host '서버 HTTPS 주소' }
    } else {
        $monitor = Get-Content $monitorPath -Raw -Encoding UTF8 | ConvertFrom-Json
        $addressFile = Join-Path $source 'Config/ServerUrl.txt'
        $url = if (Test-Path $addressFile) { (Get-Content $addressFile -Raw).Trim() } else { $monitor.ServerUrl }
    }
    $uri = [uri]$url
    if (-not $uri.IsAbsoluteUri -or $uri.UserInfo -or $uri.Query -or $uri.Fragment -or $uri.AbsolutePath -ne '/' -or
        ($uri.Scheme -ne 'https' -and -not ($uri.Scheme -eq 'http' -and $uri.IsLoopback))) { throw 'HTTPS 서버 주소 또는 로컬 localhost 주소를 사용하세요.' }
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    $runtime = Invoke-RestMethod -Uri ($url.TrimEnd('/')+'/api/config') -TimeoutSec 10 -MaximumRedirection 0
    if ($uri.Scheme -eq 'http' -and $runtime.auth_mode -ne 'development') { throw 'HTTP 주소는 로컬 테스트 모드에서만 사용하세요.' }
    if ($generatedConfig) {
        $monitor = New-ClientMonitoringConfig -ServerUrl ('https://'+$uri.Authority) -ReportToken ('x' * 40) -Grade 1
        $monitor.ServerUrl = $url.TrimEnd('/')
        $monitor.AllowHttp = $uri.Scheme -eq 'http'
    }
    $monitor.ServerUrl = $url.TrimEnd('/')
    foreach ($name in @('Main.bat','Scripts','Modules','Config')) {
        if (-not (Test-Path (Join-Path $source $name))) { throw "필수 실행 도구 누락: $name" }
    }
    $id = ([guid](Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Cryptography').MachineGuid).ToString()
    $registered = Get-AgentRegistration -ServerUrl $url.TrimEnd('/') -DeviceId $id -Hostname $env:COMPUTERNAME -Stored $stored
    $task = Get-ScheduledTask -TaskName 'DuctTapeAgent' -ErrorAction SilentlyContinue
    if ($task) { Stop-ScheduledTask -TaskName 'DuctTapeAgent' }
    if (Test-Path (Join-Path $target 'Config/ActiveJob.json')) {
        if ($task) { Start-ScheduledTask -TaskName 'DuctTapeAgent' }
        throw '복구 전에 작업이 시작되었습니다. 파일을 변경하지 않았습니다. 작업 종료 후 다시 실행하세요.'
    }
    if (-not (Test-Path $target)) {
        New-Item -ItemType Directory -Path $target | Out-Null
        & icacls.exe $target /inheritance:r /grant:r '*S-1-5-18:(OI)(CI)F' '*S-1-5-32-544:(OI)(CI)F' | Out-Null
        if ($LASTEXITCODE -ne 0) { throw '에이전트 폴더 접근 권한 설정에 실패했습니다.' }
    }
    foreach ($name in @('Main.bat','Scripts','Modules')) {
        if ([IO.Path]::GetFullPath($source) -ne [IO.Path]::GetFullPath($target)) {
            Copy-Item -LiteralPath (Join-Path $source $name) -Destination $target -Recurse -Force
        }
    }
    New-Item -ItemType Directory -Path (Join-Path $target 'Config') -Force | Out-Null
    . (Join-Path $PSScriptRoot 'ApplicationMedia.ps1')
    foreach ($app in (Get-ApplicationCatalog -Root $source).applications) {
        $directory=Resolve-ApplicationMedia -Root $source -Application $app
        if (Test-Path $directory) {Copy-Item -LiteralPath $directory -Destination (Join-Path $target $app.media_folder) -Recurse -Force}
        if ($app.key_file -and (Test-Path (Join-Path $source $app.key_file))) {Copy-Item -LiteralPath (Join-Path $source $app.key_file) -Destination (Join-Path $target $app.key_file) -Force}
    }
    Copy-Item -LiteralPath (Join-Path $source 'Config/Applications.json') -Destination (Join-Path $target 'Config/Applications.json') -Force
    if ($generatedConfig -or -not $monitor.ReportToken -or ($stored -and $monitor.ReportToken -eq $stored.AgentToken)) { $monitor.ReportToken = $registered.agent_token }
    if ($monitor -is [Collections.IDictionary]) { $monitor.AuthMode = $registered.auth_mode } else { $monitor | Add-Member -NotePropertyName AuthMode -NotePropertyValue $registered.auth_mode -Force }
    $monitor | ConvertTo-Json | Set-Content (Join-Path $target 'Config/Monitoring.json') -Encoding UTF8
    $agentConfig = @{ServerUrl=$monitor.ServerUrl.TrimEnd('/'); DeviceId=$id; AuthMode=$registered.auth_mode}
    if ($registered.auth_mode -ne 'development') { $agentConfig.AgentToken = $registered.agent_token }
    $agentConfig | ConvertTo-Json | Set-Content (Join-Path $target 'Config/Agent.json') -Encoding UTF8
    $action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument ('-NoProfile -ExecutionPolicy Bypass -File "'+(Join-Path $target 'Scripts/Agent.ps1')+'"') -WorkingDirectory $target
    $trigger = New-ScheduledTaskTrigger -AtStartup
    $principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
    $settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
    Register-ScheduledTask -Force -TaskName 'DuctTapeAgent' -Action $action -Trigger $trigger -Principal $principal -Settings $settings | Out-Null
    $fragment = if ($registered.auth_mode -eq 'development') { 'device='+$id } else { 'key='+$registered.client_token }
    $url = $monitor.ServerUrl.TrimEnd('/')+'/client#'+$fragment
    $desktop = [Environment]::GetFolderPath('CommonDesktopDirectory')
    "[InternetShortcut]`r`nURL=$url" | Set-Content (Join-Path $desktop 'duct-tape 작업.url') -Encoding ASCII
    Start-ScheduledTask -TaskName 'DuctTapeAgent'
    try { Start-Process $url } catch { Write-Host '브라우저를 열지 못했습니다. 바탕화면 바로가기를 열어주세요.' }
    Write-Host '바탕화면에 duct-tape 작업 바로가기를 만들었습니다. 서버 연결 상태는 열린 웹 페이지에서 확인하세요.'
    Write-Host '서버에 연결을 요청했습니다. 관리자가 PC 연결을 승인하면 바탕화면 바로가기에서 환경 셋업을 시작하세요.'
    Write-Host '등록 코드나 접속 키를 입력할 필요가 없습니다. 배포 매체는 ProgramData\DuctTapeAgent에 보관됩니다.'
} catch {
    Write-Host $_.Exception.Message -ForegroundColor Red
    Write-Host '서버 등록 후 실패했다면 관리자 페이지에서 해당 PC 등록을 해제한 후 로컬 상태를 확인하세요.'
    exit 1
}
