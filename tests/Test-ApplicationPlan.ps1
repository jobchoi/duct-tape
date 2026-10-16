$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
. (Join-Path $root 'Scripts/ApplicationMedia.ps1')
. (Join-Path $root 'Scripts/InvokeApplications.ps1')
$temp=Join-Path ([IO.Path]::GetTempPath()) ('duct-apps-'+[guid]::NewGuid().ToString('N'))
$script:Calls=@()
function Invoke-ApplicationModule {param($Path,$StateFile);$script:Calls += [IO.Path]::GetFileName($Path)}
try {
    New-Item -ItemType Directory (Join-Path $temp 'Config') -Force | Out-Null
    Copy-Item (Join-Path $root 'Config/Applications.json') (Join-Path $temp 'Config/Applications.json')
    $catalog=Get-ApplicationCatalog -Root $temp
    foreach ($app in $catalog.applications) {
        foreach ($name in $app.required_files) {
            $path=Join-Path $temp ('Tools/'+$app.media_folder+'/'+$name)
            New-Item -ItemType Directory (Split-Path $path -Parent) -Force | Out-Null;Set-Content $path 'fixture'
        }
        Set-Content (Join-Path $temp $app.key_file) 'fixture-key'
        if ((Resolve-ApplicationMedia -Root $temp -Application $app) -ne (Join-Path $temp ('Tools/'+$app.media_folder))) {throw 'Reference layout not selected'}
    }
    New-Item -ItemType Directory (Join-Path $temp 'Modules') -Force | Out-Null
    foreach ($name in @($catalog.common_modules)+@($catalog.applications|ForEach-Object {$_.modules})) {Set-Content (Join-Path $temp $name) '# inert fixture'}
    Invoke-ApplicationPlan -Root $temp -StateFile (Join-Path $temp 'state.json')
    if (($script:Calls -join ',') -ne '01_GetInfo.ps1,02_CheckOffice.ps1,03_RemoveOffice.ps1,04_InstallOffice.ps1,05_CheckHancom.ps1,06_InstallHancom.ps1') {throw 'Legacy order changed'}
    $extra=[pscustomobject]@{id='sample';name='Sample';media_folder='Sample';source_candidates=@('Tools/Sample');required_files=@('setup.exe');key_file=$null;modules=@('Modules/07_Sample.ps1')}
    $catalog.applications += $extra
    Set-Content (Join-Path $temp 'Modules/07_Sample.ps1') '# inert fixture'
    $catalog | ConvertTo-Json -Depth 10 | Set-Content (Join-Path $temp 'Config/Applications.json') -Encoding UTF8
    $script:Calls=@();Invoke-ApplicationPlan -Root $temp -StateFile (Join-Path $temp 'state.json')
    if ($script:Calls[-1] -ne '07_Sample.ps1') {throw 'Application extension not executed'}
    $catalog.applications[0].modules=@('../unsafe.ps1')
    $catalog | ConvertTo-Json -Depth 10 | Set-Content (Join-Path $temp 'Config/Applications.json') -Encoding UTF8
    $blocked=$false;try {$null=Get-ApplicationCatalog -Root $temp} catch {$blocked=$true}
    if (-not $blocked) {throw 'Unsafe module accepted'}
    Write-Host 'PASS: source resolution, original sequence, added application module and unsafe path rejection'
} finally {Remove-Item $temp -Recurse -Force}
