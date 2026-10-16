$ErrorActionPreference = 'Stop'
. (Join-Path (Split-Path $PSScriptRoot -Parent) 'Scripts/ClientSetup.ps1')
$token = 'test-report-' + ('x' * 40)
$config = New-ClientMonitoringConfig -ServerUrl 'https://school.example/' -ReportToken $token -Grade 2
if ($config.ServerUrl -ne 'https://school.example' -or $config.Contains('SchoolCode') -or $config.AllowHttp -or -not $config.Enabled) { throw 'Default config mismatch' }
$school = New-ClientMonitoringConfig -ServerUrl 'https://school.example' -ReportToken $token -Grade 3 -SchoolCode 'SCHOOL_E01'
if ($school.SchoolCode -ne 'SCHOOL_E01' -or $school.Grade -ne 3) { throw 'School config mismatch' }
foreach ($url in @('http://school.example','https://school.example/api/report','https://user@school.example','https://school.example/?q=1','https://school.example/#test','invalid')) {
    $rejected = $false
    try { $null = New-ClientMonitoringConfig -ServerUrl $url -ReportToken $token -Grade 1 } catch { $rejected = $true }
    if (-not $rejected) { throw "Invalid URL accepted: $url" }
}
foreach ($invalid in @(@{ReportToken='short'; Grade=1}, @{ReportToken=($token+' '); Grade=1}, @{ReportToken=$token; Grade=0}, @{ReportToken=$token; Grade=7}, @{ReportToken=$token; Grade=1; SchoolCode='lowercase'})) {
    $rejected = $false
    try { $null = New-ClientMonitoringConfig -ServerUrl 'https://school.example' @invalid } catch { $rejected = $true }
    if (-not $rejected) { throw 'Invalid configuration accepted' }
}
Write-Host 'PASS: HTTPS origin, token validation, grade bounds, optional school code'
