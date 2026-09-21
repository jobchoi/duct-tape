# No installers run. Execute with powershell -File tests/Test-Common.ps1 or pwsh.
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$files = @(Get-ChildItem (Join-Path $root 'Scripts') -Filter *.ps1) + @(Get-ChildItem (Join-Path $root 'Modules') -Filter *.ps1)
foreach ($file in $files) {
    $tokens = $null; $errors = $null
    $null = [System.Management.Automation.Language.Parser]::ParseFile($file.FullName, [ref]$tokens, [ref]$errors)
    if ($errors.Count) { throw "Parse failed: $($file.Name)" }
}
. (Join-Path $root 'Scripts/Common.ps1')
if ($DeployRoot -ne $root) { throw 'Root mismatch' }
$temporary = Join-Path ([IO.Path]::GetTempPath()) ('duct-test-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory $temporary | Out-Null
function Assert-Failure {
    param([scriptblock]$Action, [string]$Expected)
    $code = $null
    try { & $Action } catch { $code = $_.Exception.Message }
    if ($code -ne $Expected) { throw "Expected $Expected; received $code" }
}
try {
    $ConfigDir = $temporary
    Assert-Failure { Get-HancomKey } 'KEY_MISSING'
    $keyPath = Join-Path $temporary 'HancomKey.txt'
    foreach ($value in @(' ', '---', 'REPLACE_WITH_YOUR_LICENSE_KEY', "ABC`nDEF", 'ABC /qn', 'ABC"DEF')) {
        Set-Content -LiteralPath $keyPath -Value $value -Encoding UTF8
        Assert-Failure { Get-HancomKey } 'KEY_INVALID'
    }
    Set-Content -LiteralPath $keyPath -Value 'TEST-ONLY-NOT-A-LICENSE' -Encoding UTF8
    if ((Get-HancomKey) -ne 'TEST-ONLY-NOT-A-LICENSE') { throw 'Key round trip' }
    $statePath = Join-Path $temporary 'state.json'
    $state = [pscustomobject]@{ OfficeState = '설치 필요'; HancomState = '정상' }
    Write-DeploymentState $statePath $state
    if ((Read-DeploymentState $statePath).OfficeState -ne '설치 필요') { throw 'UTF8 round trip' }
    Set-RebootRequired $state 3010
    if (-not $state.RebootRequired) { throw 'Reboot lost' }
    Set-Content -LiteralPath $statePath -Value '{broken' -Encoding UTF8
    Assert-Failure { Read-DeploymentState $statePath } 'STATE_READ_FAILED'
    Assert-Failure { Write-DeploymentState (Join-Path $temporary 'missing/state.json') $state } 'STATE_WRITE_FAILED'
    $HancomDir = $temporary
    Assert-Failure { Assert-HancomSilentConfiguration } 'HANCOM_INI_MISSING'
    $ini = Join-Path $temporary 'setup.ini'
    Set-Content $ini 'LevelOption=2'
    Assert-Failure { Assert-HancomSilentConfiguration } 'HANCOM_INI_INVALID'
    Set-Content $ini @('[Setup]', 'LevelOption=1')
    Assert-HancomSilentConfiguration
    # Process stub verifies return-code policy without launching an executable.
    function Start-Process { param($FilePath,$ArgumentList,[switch]$Wait,[switch]$PassThru,$WindowStyle)
        [pscustomobject]@{ ExitCode = $script:FakeExitCode }
    }
    foreach ($code in @(0,3010)) {
        $script:FakeExitCode = $code
        if ((Invoke-DeploymentProcess 'fake.exe' '/qn') -ne $code) { throw 'Exit code lost' }
    }
    $script:FakeExitCode = 1603
    Assert-Failure { Invoke-DeploymentProcess 'fake.exe' '/qn' } 'INSTALL_PROCESS_FAILED'
    # Loading 06 with invalid key must return 1 before process or state access.
    $fixture = Join-Path $temporary 'fixture'
    New-Item -ItemType Directory (Join-Path $fixture 'Scripts') -Force | Out-Null
    New-Item -ItemType Directory (Join-Path $fixture 'Modules') -Force | Out-Null
    New-Item -ItemType Directory (Join-Path $fixture 'Config') -Force | Out-Null
    Copy-Item (Join-Path $root 'Scripts/Common.ps1') (Join-Path $fixture 'Scripts/Common.ps1')
    Copy-Item (Join-Path $root 'Modules/06_InstallHancom.ps1') (Join-Path $fixture 'Modules/06_InstallHancom.ps1')
    $engine = (Get-Process -Id $PID).Path
    & $engine -NoProfile -File (Join-Path $fixture 'Modules/06_InstallHancom.ps1') -StateFile (Join-Path $fixture 'missing.json')
    if ($LASTEXITCODE -ne 1) { throw 'Missing key did not stop 06' }
    # Exercise the complete 06 flow in a child process using inert installers.
    $media = Join-Path $fixture 'Hancom/Install'
    New-Item -ItemType Directory $media -Force | Out-Null
    Set-Content (Join-Path $media 'Hwp130.msi') 'fixture'
    Set-Content (Join-Path $media 'VC_redist.x86.exe') 'fixture'
    Set-Content (Join-Path $fixture 'Hancom/setup.ini') 'LevelOption=1'
    Set-Content (Join-Path $fixture 'Config/HancomKey.txt') 'TEST-ONLY-NOT-A-LICENSE'
    $fixtureState = Join-Path $fixture 'state.json'
    Write-DeploymentState $fixtureState ([pscustomobject]@{ OfficeState='정상'; HancomState='설치 필요' })
    $stubs = @'
function Stop-Process { param($Name,[switch]$Force,$ErrorAction)
    Add-Content (Join-Path $DeployRoot 'calls.log') ('STOP:' + ($Name -join ','))
}
function Start-Sleep { param($Seconds,$Milliseconds) }
function Get-ItemProperty { param($Path,$ErrorAction) }
function Start-Process { param($FilePath,$ArgumentList,[switch]$Wait,[switch]$PassThru,$WindowStyle)
    if (-not $Wait -or -not $PassThru -or $WindowStyle -ne 'Hidden') { throw 'Wrong invocation' }
    Add-Content (Join-Path $DeployRoot 'calls.log') ([IO.Path]::GetFileName($FilePath))
    if ($FilePath -eq 'msiexec.exe') {
        if ($ArgumentList -notlike '*/i *Hwp130.msi* /qn AGREETOLICENSE=yes PIDKEY=TEST-ONLY-NOT-A-LICENSE /norestart') { throw 'Wrong MSI arguments' }
        return [pscustomobject]@{ExitCode=3010}
    }
    if ($ArgumentList -ne '/install /quiet /norestart') { throw 'Wrong runtime arguments' }
    return [pscustomobject]@{ExitCode=0}
}
'@
    Add-Content (Join-Path $fixture 'Scripts/Common.ps1') $stubs -Encoding UTF8
    $output = & $engine -NoProfile -File (Join-Path $fixture 'Modules/06_InstallHancom.ps1') -StateFile $fixtureState
    if ($LASTEXITCODE -ne 0) { throw 'Mock install failed' }
    if (($output -join '') -match 'TEST-ONLY-NOT-A-LICENSE') { throw 'Key leaked' }
    $result = Read-DeploymentState $fixtureState
    if ($result.HancomState -ne '정상' -or -not $result.RebootRequired) { throw 'Install state incorrect' }
    $callsPath = Join-Path $fixture 'calls.log'
    $calls = @(Get-Content $callsPath)
    if ($calls.Count -ne 3 -or $calls[0] -ne 'STOP:Install,setup,msiexec' -or
        $calls[1] -ne 'VC_redist.x86.exe' -or $calls[2] -ne 'msiexec.exe') { throw 'Install order incorrect' }
    Remove-Item $callsPath
    Write-DeploymentState $fixtureState ([pscustomobject]@{ OfficeState='정상'; HancomState='설치 필요' })
    Set-Content (Join-Path $fixture 'Hancom/setup.ini') 'LevelOption=2'
    $null = & $engine -NoProfile -File (Join-Path $fixture 'Modules/06_InstallHancom.ps1') -StateFile $fixtureState
    if ($LASTEXITCODE -ne 1 -or (Test-Path $callsPath)) { throw 'Invalid INI caused mutation' }
    Write-Host 'PASS: syntax, roots, keys, UTF8 state, INI, process codes, reboot, 06 early exit and mocked install order/options'

} finally { Remove-Item -LiteralPath $temporary -Recurse -Force }
