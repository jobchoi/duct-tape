$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$temp = Join-Path ([IO.Path]::GetTempPath()) ('duct-office-removal-' + [guid]::NewGuid().ToString('N'))
try {
    foreach ($folder in @('Modules','Scripts','Office')) { New-Item -ItemType Directory (Join-Path $temp $folder) -Force | Out-Null }
    Copy-Item (Join-Path $root 'Modules/03_RemoveOffice.ps1') (Join-Path $temp 'Modules/03_RemoveOffice.ps1')
    $stubs = @'
$ErrorActionPreference = 'Stop'
$DeployRoot = Split-Path $PSScriptRoot -Parent
$OfficeDir = Join-Path $DeployRoot 'Office'
$script:Scenario = Get-Content (Join-Path $DeployRoot 'scenario.json') -Raw | ConvertFrom-Json
function Read-DeploymentState { param($Path); [pscustomobject]@{ OfficeState=$script:Scenario.state; HancomState='normal' } }
function Write-DeploymentState { param($Path,$State) }
function Write-DeploymentLog { param($Message); Write-Output $Message }
function Write-DeploymentFailure { param($Module,$Code); Write-Output $Code }
function Send-DeploymentEvent { param($StateFile,$Stage,$Status); Write-Output ('EVENT:'+$Status) }
function Test-Path {
    param($LiteralPath)
    if ($LiteralPath -like 'HKLM:*') {
        if ($LiteralPath -like '*Uninstall') { return -not $script:Scenario.missingRoots }
        return [bool]$script:Scenario.configuration
    }
    throw 'UNEXPECTED_FILESYSTEM_QUERY'
}
function Get-ItemProperty {
    param($Path,$ErrorAction)
    if ($script:Scenario.queryFailure) { throw 'INVENTORY_QUERY_FAILED' }
    if ($Path -notlike 'HKLM:*Uninstall\*') { throw 'UNEXPECTED_REGISTRY_QUERY' }
    foreach ($entry in $script:Scenario.entries) { $entry }
}
function Get-Service { param($Name,$ErrorAction)
    if ($Name -ne 'ClickToRunSvc') { throw 'UNEXPECTED_SERVICE_QUERY' }
    if ($script:Scenario.service) { [pscustomobject]@{ Status=$script:Scenario.service } }
}
function Assert-DeploymentFile { param($Path) }
function Invoke-DeploymentProcess { param($Path,$Arguments)
    if ($Path -notlike '*setup.exe' -or $Arguments -notlike '/configure *remove.xml*') { throw 'WRONG_INSTALLER' }
    Set-Content (Join-Path $DeployRoot 'installer-called') 'yes'
    if ($script:Scenario.installerFailure) { throw 'INSTALL_PROCESS_FAILED' }
    return 3010
}
function Set-RebootRequired { param($State,$ExitCode)
    if ($ExitCode -ne 3010) { throw 'EXIT_CODE_LOST' }
    Set-Content (Join-Path $DeployRoot 'reboot-required') 'yes'
}
'@
    [IO.File]::WriteAllText((Join-Path $temp 'Scripts/Common.ps1'), $stubs, (New-Object Text.UTF8Encoding($true)))
    $cases = @(
        @{name='empty PC'; state='설치 필요'; entries=@(); expected='OFFICE_REMOVE_SKIPPED_NO_PRODUCT'; exit=0; calls=$false},
        @{name='missing uninstall roots'; state='설치 필요'; entries=@();missingRoots=$true; expected='OFFICE_REMOVE_SKIPPED_NO_PRODUCT'; exit=0; calls=$false},
        @{name='unrelated apps'; state='설치 필요'; entries=@(@{DisplayName='Microsoft Visual C++ Runtime'},@{DisplayName='LibreOffice'}); expected='OFFICE_REMOVE_SKIPPED_NO_PRODUCT'; exit=0; calls=$false},
        @{name='target already present'; state='정상'; entries=@(); expected='EVENT:completed'; exit=0; calls=$false},
        @{name='C2R running'; state='설치 필요'; entries=@(@{DisplayName='Microsoft 365 Apps for enterprise'}); service='Running'; expected='EVENT:completed'; exit=0; calls=$true},
        @{name='orphan product'; state='설치 필요'; entries=@(@{DisplayName='Microsoft Office Professional Plus 2019'}); expected='OFFICE_C2R_SERVICE_MISSING'; exit=1; calls=$false},
        @{name='orphan config'; state='설치 필요'; entries=@(); configuration=$true; expected='OFFICE_C2R_SERVICE_MISSING'; exit=1; calls=$false},
        @{name='stopped C2R'; state='설치 필요'; entries=@(); service='Stopped'; expected='OFFICE_C2R_SERVICE_NOT_RUNNING'; exit=1; calls=$false},
        @{name='MSI product'; state='설치 필요'; entries=@(@{DisplayName='Microsoft Office Professional Plus 2016';WindowsInstaller=1}); expected='OFFICE_MSI_REMOVAL_REQUIRED'; exit=1; calls=$false},
        @{name='mixed MSI and C2R'; state='설치 필요'; entries=@(@{DisplayName='Microsoft Visio 2016';WindowsInstaller=1});service='Running'; expected='OFFICE_MSI_REMOVAL_REQUIRED'; exit=1; calls=$false},
        @{name='inventory access failure'; state='설치 필요'; entries=@();queryFailure=$true; expected='INVENTORY_QUERY_FAILED'; exit=1; calls=$false},
        @{name='installer failed'; state='설치 필요'; entries=@();service='Running';installerFailure=$true; expected='INSTALL_PROCESS_FAILED'; exit=1; calls=$true},
        @{name='invalid state'; state='invalid'; entries=@(); expected='STATE_INVALID'; exit=1; calls=$false}
    )
    $engine = (Get-Process -Id $PID).Path
    foreach ($case in $cases) {
        foreach ($marker in @('installer-called','reboot-required')) { Remove-Item (Join-Path $temp $marker) -ErrorAction SilentlyContinue }
        $case | ConvertTo-Json -Depth 5 | Set-Content (Join-Path $temp 'scenario.json') -Encoding UTF8
        $output = & $engine -NoProfile -NonInteractive -ExecutionPolicy Bypass -File (Join-Path $temp 'Modules/03_RemoveOffice.ps1') -StateFile (Join-Path $temp 'state.json')
        if ($LASTEXITCODE -ne $case.exit -or ($output -join "`n") -notmatch [regex]::Escape($case.expected)) { throw ('CASE_FAILED: '+$case.name+' '+($output -join ' ')) }
        if ((Test-Path (Join-Path $temp 'installer-called')) -ne $case.calls) { throw ('UNEXPECTED_INSTALLER_CALL: '+$case.name) }
        if ($case.exit -ne 0 -and ($output -join '') -match 'EVENT:completed') { throw 'FALSE_COMPLETION' }
        if ($case.calls -and $case.exit -eq 0 -and -not (Test-Path (Join-Path $temp 'reboot-required'))) { throw 'REBOOT_FLAG_LOST' }
    }
    . (Join-Path $root 'Scripts/Common.ps1')
    function Write-DeploymentLog { param($Message,$Level); $script:ErrorMessage=$Message }
    function Send-DeploymentEvent { param($StateFile,$Stage,$Status,$ErrorCode); $script:ReportedError=$ErrorCode }
    foreach ($code in @('OFFICE_MSI_REMOVAL_REQUIRED','OFFICE_C2R_SERVICE_MISSING','OFFICE_C2R_SERVICE_NOT_RUNNING')) {
        Write-DeploymentFailure '03' $code
        if ($script:ReportedError -ne $code -or $script:ErrorMessage -notmatch $code) { throw 'ERROR_CODE_NOT_PRESERVED' }
    }
    Write-Host ('PASS: '+$cases.Count+' Office removal scenarios; no real installers, services or registry modified')
} finally { Remove-Item $temp -Recurse -Force -ErrorAction SilentlyContinue }
