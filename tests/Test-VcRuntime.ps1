$ErrorActionPreference = 'Stop'
. (Join-Path (Split-Path $PSScriptRoot -Parent) 'Scripts/Common.ps1')
$script:InstalledRuntime = $null
$script:Calls = 0
$script:ExitCode = 0
$script:AfterInstall = $null
$script:PackageVersion = [version]'14.29.30139.0'
function Get-VcRuntimePackageVersion { param($Path) return $script:PackageVersion }
function Get-ItemProperty {
    param($LiteralPath,$ErrorAction)
    if ($LiteralPath -like '*WOW6432Node*') { return $script:InstalledRuntime }
}
function Start-Process {
    param($FilePath,$ArgumentList,[switch]$Wait,[switch]$PassThru,$WindowStyle)
    $script:Calls++
    $script:InstalledRuntime = $script:AfterInstall
    return [pscustomobject]@{ExitCode=$script:ExitCode}
}
function Assert-Error {
    param([scriptblock]$Action,[string]$Expected)
    $message = $null
    try { & $Action | Out-Null } catch { $message=$_.Exception.Message }
    if ($message -ne $Expected) { throw "Expected $Expected; got $message" }
}
# x64-only does not match x86 registration; absent, invalid, disabled or old x86 installs.
foreach ($runtime in @($null,
    [pscustomobject]@{Installed=0;Version='v14.50.35719.0'},
    [pscustomobject]@{Installed=1;Version='bad'},
    [pscustomobject]@{Installed=1;Version='v14.10.25000.0'},
    [pscustomobject]@{Installed=1;Version='v15.0.0.0'})) {
    $script:InstalledRuntime=$runtime
    $script:Calls=0
    $null=Install-VcX86Runtime 'fixture.exe'
    if ($script:Calls -ne 1) { throw 'Missing/invalid/old runtime was skipped' }
}
foreach ($version in @('v14.29.30139.0','v14.50.35719.0')) {
    $script:InstalledRuntime=[pscustomobject]@{Installed=1;Version=$version}
    $script:Calls=0
    if ((Install-VcX86Runtime 'fixture.exe') -ne 0 -or $script:Calls) { throw 'Compatible runtime not skipped' }
}
foreach ($code in @(1638,-2147023258)) {
    $script:ExitCode=$code
    $script:InstalledRuntime=$null
    $script:AfterInstall=$null
    Assert-Error {Install-VcX86Runtime 'fixture.exe'} 'VC_RUNTIME_CONFLICT'
    $script:AfterInstall=[pscustomobject]@{Installed=1;Version='v14.50.35719.0'}
    if ((Install-VcX86Runtime 'fixture.exe') -ne 0) { throw 'Verified concurrent runtime failed' }
}
$script:InstalledRuntime=$null
$script:AfterInstall=$null
$script:ExitCode=1603
Assert-Error {Install-VcX86Runtime 'fixture.exe'} 'INSTALL_PROCESS_FAILED'
$script:ExitCode=3010
if ((Install-VcX86Runtime 'fixture.exe') -ne 3010) { throw 'Reboot code lost' }
$script:PackageVersion=$null
$script:InstalledRuntime=[pscustomobject]@{Installed=1;Version='v14.50.35719.0'}
$script:ExitCode=1638
Assert-Error {Install-VcX86Runtime 'fixture.exe'} 'VC_RUNTIME_CONFLICT'
Write-Host 'PASS: absent/old/invalid x86, equal/newer versions, verified conflicts, unknown metadata, fatal error and reboot'
