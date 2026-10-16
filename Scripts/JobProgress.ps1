function Write-JobProgress {
    param([string]$Phase,[string]$Status,[string]$Module,[Nullable[long]]$Current,[Nullable[long]]$Total,[string]$Unit)
    if (-not $env:DUCT_JOB_ID) {return}
    try {
        $id=([guid]$env:DUCT_JOB_ID).ToString()
        $root=Split-Path $PSScriptRoot -Parent
        $directory=Join-Path $root 'logs'
        New-Item -ItemType Directory $directory -Force | Out-Null
        $event=[ordered]@{phase=$Phase;status=$Status}
        if ($Module) {$event.module=$Module}
        if ($null -ne $Current) {$event.current=[long]$Current}
        if ($null -ne $Total -and $Total -gt 0) {$event.total=[long]$Total}
        if ($Unit) {$event.unit=$Unit}
        [IO.File]::AppendAllText((Join-Path $directory ($id+'.progress.jsonl')),($event|ConvertTo-Json -Compress)+[Environment]::NewLine,(New-Object Text.UTF8Encoding($false)))
    } catch { }
}

function Receive-AgentMedia {
    param([string]$Uri,$Headers,[string]$OutFile)
    Write-JobProgress -Phase download -Status started
    $request=[Net.HttpWebRequest]::Create($Uri)
    $request.Method='GET';$request.AllowAutoRedirect=$false
    $request.Timeout=1800000;$request.ReadWriteTimeout=1800000
    foreach ($name in $Headers.Keys) {$request.Headers[$name]=$Headers[$name]}
    $response=$null;$inputStream=$null;$outputStream=$null
    try {
        $response=$request.GetResponse()
        if ([int]$response.StatusCode -ne 200) {throw 'MEDIA_DOWNLOAD_FAILED'}
        $total=if ($response.ContentLength -gt 0) {[long]$response.ContentLength} else {$null}
        $inputStream=$response.GetResponseStream();$outputStream=[IO.File]::Create($OutFile)
        $buffer=New-Object byte[] 131072;$received=[long]0;$last=[DateTime]::UtcNow
        Write-JobProgress -Phase download -Status progress -Current 0 -Total $total -Unit bytes
        while (($count=$inputStream.Read($buffer,0,$buffer.Length)) -gt 0) {
            $outputStream.Write($buffer,0,$count);$received += $count
            if (([DateTime]::UtcNow-$last).TotalSeconds -ge 1) {
                Write-JobProgress -Phase download -Status progress -Current $received -Total $total -Unit bytes
                $last=[DateTime]::UtcNow
            }
        }
        if ($null -ne $total -and $received -ne $total) {throw 'MEDIA_DOWNLOAD_INCOMPLETE'}
        Write-JobProgress -Phase download -Status completed -Current $received -Total $total -Unit bytes
    } finally {
        if ($null -ne $outputStream) {$outputStream.Dispose()}
        if ($null -ne $inputStream) {$inputStream.Dispose()}
        if ($null -ne $response) {$response.Dispose()}
    }
}
