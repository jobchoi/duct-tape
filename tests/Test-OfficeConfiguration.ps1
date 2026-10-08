$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
. (Join-Path $root 'Scripts/OfficeConfiguration.ps1')
$temp=Join-Path ([IO.Path]::GetTempPath()) ('duct-office-test-'+[guid]::NewGuid().ToString('N'))
function Assert-Code {param([scriptblock]$Run,[string]$Code)
    $caught=$false
    try {& $Run} catch {if ($_.Exception.Message -ne $Code) {throw 'Unexpected error or reflected source'};$caught=$true}
    if (-not $caught) {throw 'Expected rejection'}
}
try {
    New-Item -ItemType Directory $temp | Out-Null
    $key='ABCDE-FGHIJ-KLMNO-PQRST-UVWXY'
    $keyPath=Join-Path $temp 'OfficeKey.txt'
    $template=Join-Path $temp 'install.xml'
    Set-Content $keyPath $key
    $original='<Configuration><Add Channel="PerpetualVL2024"><Product ID="ProPlus2024Volume"><Language ID="ko-kr" /></Product></Add><Display Level="None" AcceptEULA="TRUE" /></Configuration>'
    Set-Content $template $original
    $code=Invoke-WithOfficeConfiguration -TemplatePath $template -KeyPath $keyPath -Install {
        param($path)
        $script:RuntimePath=$path
        [xml]$runtime=Get-Content $path -Raw
        if ($runtime.Configuration.Add.Product.PIDKEY -ne $key) {throw 'Missing runtime key'}
        if ($runtime.Configuration.Display.Level -ne 'None') {throw 'Template options lost'}
        return 3010
    }
    if ($code -ne 3010 -or (Test-Path $script:RuntimePath)) {throw 'Result or cleanup mismatch'}
    if ((Get-Content $template -Raw).Trim() -ne $original) {throw 'Original template mutated'}
    Assert-Code {Invoke-WithOfficeConfiguration -TemplatePath $template -KeyPath $keyPath -Install {param($path);$script:RuntimePath=$path;throw 'INSTALL_PROCESS_FAILED'}} 'INSTALL_PROCESS_FAILED'
    if (Test-Path $script:RuntimePath) {throw 'Failure left key-bearing XML'}
    foreach ($invalid in @('short','XXXXX-XXXXX-XXXXX-XXXXX-XXXXX',($key+"`n"+$key),'ABCDE;FGHIJ')) {
        Set-Content $keyPath $invalid
        Assert-Code {Get-OfficeProductKey $keyPath} 'OFFICE_KEY_INVALID'
    }
    Set-Content $keyPath $key
    Set-Content $template '<Configuration><Add><Product ID="ProPlus2021Volume" /></Add></Configuration>'
    Assert-Code {Invoke-WithOfficeConfiguration -TemplatePath $template -KeyPath $keyPath -Install {throw 'Should not execute'}} 'OFFICE_CONFIG_INVALID'
    Set-Content $template '<!DOCTYPE Configuration [<!ENTITY secret SYSTEM "file:///etc/passwd">]><Configuration>&secret;</Configuration>'
    Assert-Code {Invoke-WithOfficeConfiguration -TemplatePath $template -KeyPath $keyPath -Install {throw 'Should not execute'}} 'OFFICE_CONFIG_INVALID'
    $fixture=Join-Path $temp 'fixture'
    foreach ($folder in @('Config','Office','Scripts','Modules')) {New-Item -ItemType Directory (Join-Path $fixture $folder) -Force | Out-Null}
    foreach ($script in @('Common.ps1','OfficeConfiguration.ps1','Test-DeploymentPrerequisites.ps1')) {Copy-Item (Join-Path $root ('Scripts/'+$script)) (Join-Path $fixture ('Scripts/'+$script))}
    Copy-Item (Join-Path $root 'Modules/04_InstallOffice.ps1') (Join-Path $fixture 'Modules/04_InstallOffice.ps1')
    Set-Content (Join-Path $fixture 'Config/OfficeKey.txt') $key
    Set-Content (Join-Path $fixture 'Config/HancomKey.txt') 'TEST-HANCOM-KEY'
    Set-Content (Join-Path $fixture 'Office/install.xml') $original
    Set-Content (Join-Path $fixture 'Office/setup.exe') 'inert-placeholder'
    $stubs=@'
function Start-Sleep {param($Seconds,$Milliseconds)}
function Start-Process {param($FilePath,$ArgumentList,[switch]$Wait,[switch]$PassThru,$WindowStyle)
    if ($ArgumentList -match 'ABCDE-FGHIJ-KLMNO-PQRST-UVWXY' -or $ArgumentList -notmatch '^/configure "(.+)"$') {throw 'Key leaked or wrong command'}
    $path=$Matches[1]
    [xml]$runtime=Get-Content $path -Raw
    if ($runtime.Configuration.Add.Product.PIDKEY -ne 'ABCDE-FGHIJ-KLMNO-PQRST-UVWXY') {throw 'Injection failed'}
    Set-Content (Join-Path $DeployRoot 'runtime-path.txt') $path
    [pscustomobject]@{ExitCode=3010}
}
'@
    Add-Content (Join-Path $fixture 'Scripts/Common.ps1') $stubs
    $statePath=Join-Path $fixture 'state.json'
    @{OfficeState='설치 필요';HancomState='정상'} | ConvertTo-Json | Set-Content $statePath
    $engine=(Get-Process -Id $PID).Path
    $output=& $engine -NoProfile -File (Join-Path $fixture 'Modules/04_InstallOffice.ps1') -StateFile $statePath
    if ($LASTEXITCODE -ne 0 -or ($output -join '') -match $key) {throw 'Module failed or printed key'}
    $state=Get-Content $statePath -Raw | ConvertFrom-Json
    if ($state.OfficeState -ne '정상' -or -not $state.RebootRequired) {throw 'Module result incorrect'}
    if (Test-Path ((Get-Content (Join-Path $fixture 'runtime-path.txt') -Raw).Trim())) {throw 'Module left runtime XML'}
    Remove-Item (Join-Path $fixture 'Config/OfficeKey.txt')
    $preflight=& $engine -NoProfile -File (Join-Path $fixture 'Scripts/Test-DeploymentPrerequisites.ps1')
    if ($LASTEXITCODE -ne 1 -or ($preflight -join '') -notmatch 'OFFICE_KEY_MISSING') {throw 'Preflight failed to reject missing Office key'}
    Write-Host 'PASS: key file, validation, private runtime XML, original preservation, success/failure cleanup, XML entity rejection and mocked 04 installation'
} finally {Remove-Item $temp -Recurse -Force}
