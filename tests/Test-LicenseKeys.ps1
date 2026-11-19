$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
. (Join-Path $root 'Scripts/LicenseKeys.ps1')
$temp=Join-Path ([IO.Path]::GetTempPath()) ('duct-license-test-'+[guid]::NewGuid().ToString('N'))
try {
    New-Item -ItemType Directory (Join-Path $temp 'Config') -Force | Out-Null
    @{ServerUrl='https://server.example';AuthMode='secure';AgentToken='FAKE-TOKEN'} | ConvertTo-Json | Set-Content (Join-Path $temp 'Config/Agent.json') -Encoding UTF8
    $office=Join-Path $temp 'Config/OfficeKey.txt'
    Set-Content $office 'old-value'
    Sync-AgentLicenseKeys -Root $temp -Request {
        param($Uri,$Headers)
        if ($Uri -ne 'https://server.example/api/agent/licenses' -or $Headers.Authorization -ne 'Bearer FAKE-TOKEN') { throw 'Wrong request' }
        [pscustomobject]@{keys=@([pscustomobject]@{app='office';key='ABCDE-FGHIJ-KLMNO-PQRST-UVWXY'})}
    }
    if ((Get-Content $office -Raw) -ne 'ABCDE-FGHIJ-KLMNO-PQRST-UVWXY') {throw 'Cached key not refreshed'}
    # Invalid second entry must not partially apply the first entry.
    $caught=$false
    try {
        Sync-AgentLicenseKeys -Root $temp -Request {
            [pscustomobject]@{keys=@([pscustomobject]@{app='office';key='11111-22222-33333-44444-55555'},[pscustomobject]@{app='../../escape';key='unsafe'})}
        }
    } catch { $caught=$_.Exception.Message -eq 'LICENSE_SYNC_FAILED' }
    if (-not $caught -or (Get-Content $office -Raw) -ne 'ABCDE-FGHIJ-KLMNO-PQRST-UVWXY') {throw 'Unsafe partial update'}
    if (@(Get-ChildItem (Join-Path $temp 'Config') -Filter '*.tmp').Count) {throw 'Secret temporary file left'}
    Write-Host 'PASS: authenticated key refresh, cached-key replacement, validation before writes and cleanup; no real product keys used'
} finally { Remove-Item $temp -Recurse -Force }
