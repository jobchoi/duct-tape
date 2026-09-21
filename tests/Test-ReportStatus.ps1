$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
. (Join-Path $root 'Scripts/ReportStatus.ps1')
$temporary = Join-Path ([IO.Path]::GetTempPath()) ('duct-report-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory $temporary | Out-Null
function Get-ItemProperty { param($LiteralPath,$Name,$ErrorAction)
    [pscustomobject]@{MachineGuid = '11111111-2222-3333-4444-555555555555'}
}
function Get-CimInstance { param($ClassName,$Filter,$ErrorAction)
    [pscustomobject]@{MACAddress = '00:11:22:33:44:55'}
}
function Start-Sleep { param($Seconds) }
$script:Calls = 0
$script:Failures = 0
$script:LastBody = $null
$script:RequestIds = @()
function Invoke-RestMethod {
    param($Uri,$Method,$Headers,$Body,$ContentType,$TimeoutSec,$MaximumRedirection,$ErrorAction)
    $script:Calls++
    if ($TimeoutSec -ne 2 -or $MaximumRedirection -ne 0 -or $ContentType -ne 'application/json; charset=utf-8') { throw 'Request options' }
    $script:LastBody = [Text.Encoding]::UTF8.GetString($Body)
    $script:RequestIds += ($script:LastBody | ConvertFrom-Json).report_id
    if ($script:Calls -le $script:Failures) { throw 'offline' }
    return @{accepted=$true}
}
try {
    $configPath = Join-Path $temporary 'Monitoring.json'
    $statePath = Join-Path $temporary 'State.json'
    $config = @{Enabled=$true;ServerUrl='https://school.example';ReportToken=('TEST-' + ('X' * 40));TimeoutSeconds=2;MaxAttempts=2;AllowHttp=$false}
    $state = @{OfficeState='설치 필요';HancomState='정상';SerialNumber='학교기기';Model='테스트';PIDKEY='DO_NOT_SEND';RebootRequired=$false}
    $state | ConvertTo-Json | Set-Content $statePath -Encoding UTF8
    $config | ConvertTo-Json | Set-Content $configPath -Encoding UTF8
    $args = @{StateFile=$statePath;Stage='04';Status='running';ErrorCode='';ConfigPath=$configPath}
    if (-not (Send-StatusReport @args)) { throw 'Report failed' }
    $body = $script:LastBody | ConvertFrom-Json
    if ($body.office -ne '설치 중' -or $body.serial -ne '학교기기' -or $body.mac -ne '00:11:22:33:44:55') { throw 'Mapping failed' }
    if ($script:LastBody -match 'PIDKEY|DO_NOT_SEND|ReportToken') { throw 'Secret included' }
    $script:Calls=0; $script:Failures=1; $script:RequestIds=@()
    if (-not (Send-StatusReport @args) -or $script:Calls -ne 2) { throw 'Retry failed' }
    if ($script:RequestIds[0] -ne $script:RequestIds[1]) { throw 'Retry identity changed' }
    $script:Calls=0; $script:Failures=100
    if ((Send-StatusReport @args) -or $script:Calls -ne 2) { throw 'Retry unbounded' }
    $script:Calls=0; $script:Failures=0
    $config.Enabled=$false
    $config | ConvertTo-Json | Set-Content $configPath -Encoding UTF8
    if ((Send-StatusReport @args) -or $script:Calls -ne 0) { throw 'Disabled sent' }
    $config.Enabled=$true; $config.ServerUrl='http://school.example'
    $config | ConvertTo-Json | Set-Content $configPath -Encoding UTF8
    if ((Send-StatusReport @args) -or $script:Calls -ne 0) { throw 'Insecure config accepted' }
    Write-Host 'PASS: report allowlist, UTF8, status mapping, fixed retry identity, bounded offline retries, disabled mode, HTTP opt-in'
} finally { Remove-Item -LiteralPath $temporary -Recurse -Force }
