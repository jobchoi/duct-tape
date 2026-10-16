$ErrorActionPreference='Stop'
$repo=Split-Path $PSScriptRoot -Parent
$temp=Join-Path ([IO.Path]::GetTempPath()) ('duct-progress-'+[guid]::NewGuid().ToString('N'))
try {
    New-Item -ItemType Directory (Join-Path $temp 'Scripts') -Force | Out-Null
    Copy-Item (Join-Path $repo 'Scripts/JobProgress.ps1') (Join-Path $temp 'Scripts/JobProgress.ps1')
    . (Join-Path $temp 'Scripts/JobProgress.ps1')
    . (Join-Path $repo 'Scripts/ProgressDelivery.ps1')
    $env:DUCT_JOB_ID=[guid]::NewGuid().ToString()
    Write-JobProgress -Phase download -Status progress -Current 512 -Total 1024 -Unit bytes
    Write-JobProgress -Phase module -Status started -Module '04_InstallOffice.ps1' -Current 3 -Total 6 -Unit steps
    $script:Requests=@();$script:Fail=$false
    function Invoke-AgentApi {
        param($Path,$Body)
        if ($script:Fail) {throw 'offline'}
        $script:Requests+=@($Body.events)
    }
    $after=Send-AgentProgress -Root $temp -JobId $env:DUCT_JOB_ID
    if ($after -ne 2 -or $script:Requests.Count -ne 2 -or $script:Requests[0].current -ne 512 -or $script:Requests[0].sequence -ne 1) {throw 'Event delivery mismatch'}
    $again=Send-AgentProgress -Root $temp -JobId $env:DUCT_JOB_ID -After $after
    if ($again -ne 2 -or $script:Requests.Count -ne 2) {throw 'Delivered duplicates after acknowledgement'}
    Write-JobProgress -Phase report -Status completed
    $script:Fail=$true;$blocked=$false
    try {$null=Send-AgentProgress -Root $temp -JobId $env:DUCT_JOB_ID -After 2} catch {$blocked=$true}
    if (-not $blocked) {throw 'Offline delivery falsely acknowledged'}
    $script:Fail=$false
    if ((Send-AgentProgress -Root $temp -JobId $env:DUCT_JOB_ID -After 2) -ne 3) {throw 'Retry lost event'}
    $allowed=@('phase','status','module','current','total','unit','sequence')
    foreach ($event in $script:Requests) {
        if (@($event.PSObject.Properties.Name|Where-Object {$_ -notin $allowed}).Count) {throw 'Unexpected free text or secret field'}
    }
    Write-Host 'PASS: real JSONL event output, numeric counters, ordered delivery, acknowledgement, offline retry and structured fields only'
} finally {Remove-Item $temp -Recurse -Force;Remove-Item Env:DUCT_JOB_ID -ErrorAction SilentlyContinue}
