$ErrorActionPreference='Stop'
$repo=Split-Path $PSScriptRoot -Parent
. (Join-Path $repo 'Scripts/ManagedApplications.ps1')
Add-Type -AssemblyName System.IO.Compression.FileSystem
$fixture=Join-Path $env:TEMP ('duct-app-test-'+[guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory $fixture|Out-Null
function Write-JobProgress {param($Phase,$Status,$ApplicationId)}
function Test-ManagedAppInstalled {param($App) return $script:Detected}
function Assert-ManagedMsiIdentity {param($Path,$App) if($script:BadIdentity){throw 'PACKAGE_INVALID'}}
function Receive-AgentMedia {param($Uri,$Headers,$OutFile) $script:Downloads++;Copy-Item $script:Archive $OutFile}
function Invoke-ManagedMsi {param($Path) $script:Installs++;$script:Detected=$script:AfterInstall;return $script:NativeCode}
try {
    $payload=Join-Path $fixture 'payload';New-Item -ItemType Directory $payload|Out-Null
    Set-Content (Join-Path $payload 'fixture.msi') 'inert fixture'
    $script:Archive=Join-Path $fixture 'source.zip'
    [IO.Compression.ZipFile]::CreateFromDirectory($payload,$script:Archive)
    $hash=(Get-FileHash $script:Archive -Algorithm SHA256).Hash.ToLowerInvariant()
    $app=[pscustomobject]@{schema_version=2;adapter='msi-v1';id='sample';version='1.1.7';sha256=$hash;product_code='{A23A2428-0549-4AF0-8C9B-85F60CBE9AE7}';installer='fixture.msi';enrollment=$true}
    $root=Join-Path $fixture 'agent';New-Item -ItemType Directory $root|Out-Null
    $script:Downloads=0;$script:Installs=0;$script:Detected=$true;$script:AfterInstall=$true;$script:NativeCode=3010;$script:BadIdentity=$false
    $result=Invoke-ManagedApp -Root $root -JobId ([guid]::NewGuid()) -App $app -ServerUrl 'https://example.test' -Headers @{}
    if($result.status -ne 'already_installed' -or $script:Downloads -or $script:Installs){throw 'Installed skip failed'}
    $script:Detected=$false
    $result=Invoke-ManagedApp -Root $root -JobId ([guid]::NewGuid()) -App $app -ServerUrl 'https://example.test' -Headers @{}
    if(-not $result.verified -or -not $result.reboot_required -or $result.enrollment -ne 'required' -or $script:Downloads -ne 1){throw 'Install/reboot/enrollment separation failed'}
    $script:Detected=$false;$script:AfterInstall=$false;$script:NativeCode=0
    $result=Invoke-ManagedApp -Root $root -JobId ([guid]::NewGuid()) -App $app -ServerUrl 'https://example.test' -Headers @{}
    if($result.error_code -ne 'VERIFY_FAILED' -or $result.verified -or $script:Downloads -ne 1){throw 'Cache/postcheck failed'}
    $script:NativeCode=1603
    $result=Invoke-ManagedApp -Root $root -JobId ([guid]::NewGuid()) -App $app -ServerUrl 'https://example.test' -Headers @{}
    if($result.error_code -ne 'INSTALL_FAILED' -or $result.exit_code -ne 1603){throw 'Native failure lost'}
    $script:BadIdentity=$true;$before=$script:Installs
    $result=Invoke-ManagedApp -Root $root -JobId ([guid]::NewGuid()) -App $app -ServerUrl 'https://example.test' -Headers @{}
    if($result.error_code -ne 'PACKAGE_INVALID' -or $script:Installs -ne $before){throw 'Identity mismatch installed'}
    $script:BadIdentity=$false
    # A bad declared hash must stop before extraction/installation.
    $app.sha256='0'*64
    $result=Invoke-ManagedApp -Root $root -JobId ([guid]::NewGuid()) -App $app -ServerUrl 'https://example.test' -Headers @{}
    if($result.error_code -ne 'PACKAGE_INVALID' -or $script:Installs -ne $before){throw 'Hash mismatch installed'}
    # Extraction guard blocks traversal even if a server supplied the archive.
    $bad=Join-Path $fixture 'bad.zip'
    $z=[IO.Compression.ZipFile]::Open($bad,[IO.Compression.ZipArchiveMode]::Create)
    $entry=$z.CreateEntry('../escape.msi');$z.Dispose()
    $blocked=$false
    try{Expand-ManagedAppPackage -Zip $bad -Destination (Join-Path $fixture 'unpack')}catch{$blocked=$_.Exception.Message -eq 'PACKAGE_INVALID'}
    if(-not $blocked -or (Test-Path (Join-Path $fixture 'escape.msi'))){throw 'Traversal escaped'}
    Write-Host 'PASS: preinstalled skip, cached package, MSI success/reboot, failed postcheck, native failure, identity/hash mismatch and traversal; no installer runs'
} finally {Remove-Item $fixture -Recurse -Force}
