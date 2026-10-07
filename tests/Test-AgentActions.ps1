$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
. (Join-Path $root 'Scripts/AgentActions.ps1')
$script:Calls = 0
function Start-Process {
    param($FilePath,$ArgumentList,$WorkingDirectory,[switch]$PassThru,$WindowStyle,$RedirectStandardOutput,$RedirectStandardError)
    $script:Calls++
    if ($FilePath -ne 'powershell.exe' -or $WorkingDirectory -ne $root -or $ArgumentList -notmatch 'RunAgentJob.ps1' -or $RedirectStandardOutput -notmatch 'logs') { throw 'Unexpected execution' }
    $script:Arguments=$ArgumentList
    return [pscustomobject]@{ExitCode=0}
}
$id = [guid]::NewGuid().ToString()
$null = Start-AgentAction -Action 'report-test' -Root $root -JobId $id
if ($script:Arguments -notmatch '-ReportOnly') { throw 'Report test must not install' }
$null = Start-AgentAction -Action 'deploy' -Root $root -JobId $id
if ($script:Arguments -match '-ReportOnly') { throw 'Deploy mismatch' }
$rejected=$false
try { $null = Start-AgentAction -Action 'powershell -Command evil' -Root $root -JobId $id } catch { $rejected=$true }
if (-not $rejected -or $script:Calls -ne 2) { throw 'Arbitrary command accepted' }
foreach ($file in @('Scripts/Agent.ps1','Scripts/InstallAgent.ps1','Scripts/AgentActions.ps1','Scripts/RunAgentJob.ps1','Scripts/PrepareAgentMedia.ps1')) {
    $tokens=$null; $errors=$null
    $null=[Management.Automation.Language.Parser]::ParseFile((Join-Path $root $file),[ref]$tokens,[ref]$errors)
    if ($errors.Count) { throw "Syntax errors: $file" }
}
Write-Host 'PASS: fixed actions, report-only isolation, command rejection, agent script syntax'

$tempRoot = Join-Path ([IO.Path]::GetTempPath()) ('duct-ready-'+[guid]::NewGuid().ToString('N'))
try {
    New-Item -ItemType Directory $tempRoot | Out-Null
    if (Test-AgentSetupReady -Root $tempRoot) { throw 'Empty installation incorrectly ready' }
    foreach ($name in @('Office/setup.exe','Office/install.xml','Office/remove.xml','Hancom/Install/Hwp130.msi','Hancom/Install/VC_redist.x86.exe','Config/HancomKey.txt')) {
        $file=Join-Path $tempRoot $name
        New-Item -ItemType Directory (Split-Path $file -Parent) -Force | Out-Null
        Set-Content $file 'test-placeholder'
    }
    if (-not (Test-AgentSetupReady -Root $tempRoot)) { throw 'Prepared installation not ready' }
    Remove-Item (Join-Path $tempRoot 'Config/HancomKey.txt')
    if (Test-AgentSetupReady -Root $tempRoot) { throw 'Missing license incorrectly ready' }
    Write-Host 'PASS: media readiness and missing license guard'
} finally { Remove-Item $tempRoot -Recurse -Force }
