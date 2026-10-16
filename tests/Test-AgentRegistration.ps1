$ErrorActionPreference='Stop'
. (Join-Path (Split-Path $PSScriptRoot -Parent) 'Scripts/AgentRegistration.ps1')
$script:Mode='missing';$script:Calls=@()
function Invoke-RestMethod {
    param($Uri,$Headers,$Method,$Body,$ContentType,$TimeoutSec,$MaximumRedirection)
    $script:Calls += $Uri
    if ($Uri.EndsWith('/status')) {
        if ($script:Mode -in @('missing','offline')) {
            $exception=New-Object Exception('simulated')
            if ($script:Mode -eq 'missing') { $exception | Add-Member -NotePropertyName Response -NotePropertyValue ([pscustomobject]@{StatusCode=401}) }
            throw $exception
        }
        $jobs=if ($script:Mode -eq 'busy') {@([pscustomobject]@{state='running'})} else {@()}
        return [pscustomobject]@{jobs=$jobs}
    }
    if ($Uri.EndsWith('/reconnect')) {return [pscustomobject]@{client_token='new-client';auth_mode='secure';approved=$true}}
    return [pscustomobject]@{agent_token='new-agent';client_token='new-client';auth_mode='secure';approved=$false}
}
$id='11111111-2222-3333-4444-555555555555'
$stored=[pscustomobject]@{ServerUrl='https://server.example';DeviceId=$id;AgentToken='old-agent';AuthMode='secure'}
$arguments=@{ServerUrl='https://server.example';DeviceId=$id;Hostname='TEST-PC';Stored=$stored}
$result=Get-AgentRegistration @arguments
if ($result.agent_token -ne 'new-agent' -or -not $script:Calls[-1].EndsWith('/join')) {throw 'Missing registry not recovered'}
$script:Mode='valid';$script:Calls=@()
$result=Get-AgentRegistration @arguments
if ($result.agent_token -ne 'old-agent' -or $result.client_token -ne 'new-client' -or $script:Calls[-1] -notlike '*/reconnect') {throw 'Existing registry not restored'}
foreach ($mode in @('busy','offline')) {
    $script:Mode=$mode;$script:Calls=@();$failed=$false
    try {$null=Get-AgentRegistration @arguments} catch {$failed=$true}
    if (-not $failed -or $script:Calls.Count -ne 1) {throw 'Unsafe re-registration'}
}
$script:Calls=@();$stored.ServerUrl='https://old-server.example'
$null=Get-AgentRegistration @arguments
if ($script:Calls.Count -ne 1 -or -not $script:Calls[0].EndsWith('/join')) {throw 'Old credentials sent to new origin'}
$tokens=$null;$errors=$null
$null=[Management.Automation.Language.Parser]::ParseFile((Join-Path (Split-Path $PSScriptRoot -Parent) 'Scripts/InstallAgent.ps1'),[ref]$tokens,[ref]$errors)
if ($errors.Count) {throw 'Installer syntax invalid'}
Write-Host 'PASS: missing registry rejoin, valid credential reconnect, active/offline guard, origin isolation and installer syntax'
