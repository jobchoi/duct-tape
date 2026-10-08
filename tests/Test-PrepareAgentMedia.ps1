$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
. (Join-Path $root 'Scripts/PrepareAgentMedia.ps1')
. (Join-Path $root 'Scripts/AgentActions.ps1')
Add-Type -AssemblyName System.IO.Compression.FileSystem
$tempRoot=Join-Path ([IO.Path]::GetTempPath()) ('duct-media-test-'+[guid]::NewGuid().ToString('N'))
function Invoke-WebRequest {
    param($Uri,$Headers,$OutFile,[switch]$UseBasicParsing,$TimeoutSec,$MaximumRedirection)
    if ($Uri -ne 'https://server.example/api/agent/media' -or $Headers.Authorization -ne 'Bearer fake-agent-key') { throw 'Unexpected media endpoint' }
    Copy-Item $script:Fixture $OutFile
}
try {
    New-Item -ItemType Directory (Join-Path $tempRoot 'pc/Config') -Force | Out-Null
    @{ServerUrl='https://server.example';AgentToken='fake-agent-key';AuthMode='secure'} | ConvertTo-Json | Set-Content (Join-Path $tempRoot 'pc/Config/Agent.json')
    $source=Join-Path $tempRoot 'source'
    foreach ($name in @('Office/setup.exe','Office/install.xml','Office/remove.xml','Hancom/Install/Hwp130.msi','Hancom/Install/VC_redist.x86.exe','Config/HancomKey.txt', 'Config/OfficeKey.txt')) {
        $file=Join-Path $source $name
        New-Item -ItemType Directory (Split-Path $file -Parent) -Force | Out-Null
        Set-Content $file 'test-placeholder'
    }
    $script:Fixture=Join-Path $tempRoot 'media.zip'
    Compress-Archive -Path (Join-Path $source '*') -DestinationPath $script:Fixture
    Initialize-AgentMedia -Root (Join-Path $tempRoot 'pc')
    if (-not (Test-AgentSetupReady -Root (Join-Path $tempRoot 'pc'))) { throw 'Media not prepared' }
    if (@(Get-ChildItem (Join-Path $tempRoot 'pc') -Filter 'media-stage-*').Count) { throw 'Staging not cleaned' }
    Remove-Item (Join-Path $tempRoot 'pc/Office/setup.exe')
    Remove-Item $script:Fixture
    $bad=[IO.Compression.ZipFile]::Open($script:Fixture,[IO.Compression.ZipArchiveMode]::Create)
    try { $null=$bad.CreateEntry('Office/../../escape.txt') } finally { $bad.Dispose() }
    $rejected=$false
    try { Initialize-AgentMedia -Root (Join-Path $tempRoot 'pc') } catch { $rejected=$true }
    if (-not $rejected -or (Test-Path (Join-Path $tempRoot 'escape.txt'))) { throw 'Unsafe archive accepted' }
    Write-Host 'PASS: media download, actual ZIP extraction, key placement, readiness and cleanup'
} finally {Remove-Item $tempRoot -Recurse -Force}
