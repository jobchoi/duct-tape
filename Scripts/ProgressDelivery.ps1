function Send-AgentProgress {
    param([string]$Root,[string]$JobId,[int]$After=0)
    $path=Join-Path $Root ('logs/'+([guid]$JobId).ToString()+'.progress.jsonl')
    if (-not (Test-Path $path)) {return $After}
    $lines=[IO.File]::ReadAllLines($path)
    $events=@();$last=$After
    for ($index=$After;$index -lt $lines.Count -and $events.Count -lt 32;$index++) {
        if (-not $lines[$index].Trim()) {continue}
        $event=$lines[$index] | ConvertFrom-Json
        $event | Add-Member -NotePropertyName sequence -NotePropertyValue ($index+1)
        $events += $event;$last=$index+1
    }
    if ($events.Count) {
        $null=Invoke-AgentApi ('/api/agent/jobs/'+$JobId+'/progress') @{events=@($events)}
    }
    return $last
}
