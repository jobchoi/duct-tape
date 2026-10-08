function Start-AgentAction {
    param([string]$Action, [string]$Root, [string]$JobId)
    $id = ([guid]$JobId).ToString()
    switch ($Action) {
        'report-test' { $arguments = '-ReportOnly' }
        'deploy' { $arguments = '' }
        default { throw '허용되지 않은 작업입니다.' }
    }
    $script = Join-Path $Root 'Scripts/RunAgentJob.ps1'
    Start-Process powershell.exe -ArgumentList ('-NoProfile -ExecutionPolicy Bypass -File "'+$script+'" -JobId '+$id+' '+$arguments) -WorkingDirectory $Root -PassThru -WindowStyle Hidden -RedirectStandardOutput (Join-Path $Root ('logs/'+$id+'.out.log')) -RedirectStandardError (Join-Path $Root ('logs/'+$id+'.err.log'))
}

function Test-AgentSetupReady {
    param([string]$Root)
    . (Join-Path $PSScriptRoot 'ApplicationMedia.ps1')
    foreach ($app in (Get-ApplicationCatalog -Root $Root).applications) {
        $directory=Resolve-ApplicationMedia -Root $Root -Application $app
        foreach ($name in $app.required_files) {
            if (-not (Test-Path -LiteralPath (Join-Path $directory $name) -PathType Leaf)) { return $false }
        }
        if ($app.key_file -and -not (Test-Path -LiteralPath (Join-Path $Root $app.key_file) -PathType Leaf)) { return $false }
    }
    return $true
}
