$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
. (Join-Path $root 'Scripts/diagnostics/Collect-ClientDiagnostics.ps1')
$fixture = Join-Path ([IO.Path]::GetTempPath()) ('duct-diagnostics-test-'+[guid]::NewGuid().ToString('N'))
$oldTemp=$env:TEMP;$oldWindows=$env:windir
function Get-CimInstance {
    param($ClassName,$ErrorAction)
    switch ($ClassName) {
        'Win32_ComputerSystem' { return [pscustomobject]@{Manufacturer='TEST';Model='Desktop';PCSystemType=1} }
        'Win32_BIOS' { return [pscustomobject]@{SerialNumber='00001234'} }
        'Win32_OperatingSystem' { return [pscustomobject]@{Caption='Test Windows';Version='10.0';OSArchitecture='64-bit'} }
        default { throw 'Unapproved inventory call' }
    }
}
function Get-ItemProperty {
    param($Path,$ErrorAction)
    [pscustomobject]@{DisplayName='Microsoft Office LTSC 2024';DisplayVersion='16.0';UninstallString='PRIVATE-UNINSTALL'}
}
function Get-ScheduledTask { param($TaskName,$ErrorAction) [pscustomobject]@{State='Ready'} }
$script:NetworkCalls=0
function Invoke-RestMethod {
    param($Uri,$Method,$TimeoutSec,$MaximumRedirection,$ErrorAction)
    if ($Uri -ne 'https://test.invalid:9443/api/config' -or $Method -ne 'Get' -or $MaximumRedirection -ne 0) { throw 'Unexpected request' }
    $script:NetworkCalls++
    @{media=@{ready=$true};PrivateKey='PRIVATE-API-RESPONSE'}
}
try {
    $env:TEMP=Join-Path $fixture 'user-temp';$env:windir=Join-Path $fixture 'Windows'
    $agent=Join-Path $fixture 'agent'
    foreach ($p in @($env:TEMP,(Join-Path $env:windir 'Temp/duct-tape'),(Join-Path $agent 'Config'),(Join-Path $agent 'logs'))) {
        New-Item -ItemType Directory -Path $p -Force | Out-Null
    }
    $config=Join-Path $agent 'Config/Agent.json'
    @{ServerUrl='https://test.invalid:9443';DeviceId='11111111-2222-3333-4444-555555555555';AgentToken='PRIVATE-AGENT-TOKEN';ClientToken='PRIVATE-CLIENT-TOKEN'} |
        ConvertTo-Json | Set-Content -LiteralPath $config -Encoding UTF8
    $before=Get-Content -LiteralPath $config -Raw
    @{OfficeState='정상';HancomState='정상';PIDKEY='PRIVATE-LICENSE';RebootRequired=$true} |
        ConvertTo-Json | Set-Content -LiteralPath (Join-Path $env:TEMP 'Tapbook_State.json') -Encoding UTF8
    $id='aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'
    @('2026-11-05 [INFO] PROCESS_EXIT: 1638','raw PIDKEY=PRIVATE-LOG-KEY','2026-11-05 [ERROR] 06 : INSTALL_PROCESS_FAILED',
        'AGENT_RESULT: state=failed exit_code=1') | Set-Content (Join-Path $agent ('logs/'+$id+'.out.log')) -Encoding UTF8
    [IO.File]::WriteAllText((Join-Path $agent ('logs/'+$id+'.err.log')),'')
    'PRIVATE-DEPLOYMENT-LOG' | Set-Content (Join-Path $env:windir 'Temp/duct-tape/Deployment.log') -Encoding UTF8
    $out=Invoke-ClientDiagnostics -AgentRoot $agent -JobId $id -OutputDirectory (Join-Path $fixture 'result')
    $text=Get-Content -LiteralPath $out -Raw -Encoding UTF8;$report=$text | ConvertFrom-Json
    if ($text -match 'PRIVATE-|AgentToken|ClientToken|PIDKEY|UninstallString') { throw 'Private value leaked' }
    if ($report.computer.pc_system_type -ne 1 -or $report.computer.serial -ne '00001234') { throw 'Desktop metadata incorrect' }
    if ($report.states[0].office -ne '정상' -or -not $report.states[0].reboot_required) { throw 'State mapping incorrect' }
    if ($report.agent.device_id -ne '11111111-2222-3333-4444-555555555555' -or $report.agent.task_state -ne 'Ready') { throw 'Agent mapping incorrect' }
    if (-not $report.server.media_ready -or $script:NetworkCalls -ne 1) { throw 'Health check incorrect' }
    $log=@($report.logs | Where-Object { $_.path -like '*.out.log' })[0]
    if (@($log.signals | Where-Object {$_.kind -eq 'process_exit' -and $_.exit_code -eq 1638}).Count -ne 1) { throw 'Exit signal missing' }
    if (@($log.signals | Where-Object {$_.kind -eq 'agent_result' -and $_.state -eq 'failed'}).Count -ne 1) { throw 'Agent signal missing' }
    if (@($report.logs | Where-Object {$_.path -like '*.err.log' -and $_.bytes -eq 0}).Count -ne 1) { throw 'Empty log not recorded' }
    if ((Get-Content -LiteralPath $config -Raw) -ne $before) { throw 'Agent configuration modified' }
    foreach ($url in @('https://user:password@example.test','https://test.invalid/?token=PRIVATE','https://test.invalid/#key=PRIVATE','http://192.168.1.1','file:///C:/secret')) {
        if (Get-DiagnosticOrigin $url) { throw 'Unsafe origin accepted' }
    }
    if ((Get-DiagnosticOrigin 'http://127.0.0.1:8001') -ne 'http://127.0.0.1:8001') { throw 'Loopback origin rejected' }
    $rejected=$false
    try { Invoke-ClientDiagnostics -AgentRoot $agent -OutputDirectory (Join-Path $fixture 'result') | Out-Null } catch { $rejected=$true }
    if (-not $rejected -or (Get-Content -LiteralPath $out -Raw -Encoding UTF8) -ne $text) { throw 'Existing report overwritten' }
    $rejected=$false
    try { Invoke-ClientDiagnostics -AgentRoot $agent -JobId '../secret' -OutputDirectory (Join-Path $fixture 'invalid') | Out-Null } catch { $rejected=$true }
    if (-not $rejected -or (Test-Path (Join-Path $fixture 'invalid'))) { throw 'Invalid job accepted' }
    Write-Host 'PASS: desktop inventory, state mapping, safe log signals, empty logs, secret exclusion, origin validation and read-only behavior; no installers run'
} finally {
    $env:TEMP=$oldTemp;$env:windir=$oldWindows
    if (Test-Path -LiteralPath $fixture) { Remove-Item -LiteralPath $fixture -Recurse -Force }
}
