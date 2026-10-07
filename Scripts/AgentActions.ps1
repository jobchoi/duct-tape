function Start-AgentAction {
    param([string]$Action, [string]$Root, [string]$JobId)
    $id = ([guid]$JobId).ToString()
    switch ($Action) {
        'report-test' { $arguments = '-ReportOnly' }
        'deploy' { $arguments = '' }
        default { throw '허용되지 않은 작업입니다.' }
    }
    $script = Join-Path $Root 'Scripts/RunAgentJob.ps1'
    Start-Process powershell.exe -ArgumentList ('-NoProfile -ExecutionPolicy Bypass -File "'+$script+'" '+$arguments) -WorkingDirectory $Root -PassThru -WindowStyle Hidden -RedirectStandardOutput (Join-Path $Root ('logs/'+$id+'.out.log')) -RedirectStandardError (Join-Path $Root ('logs/'+$id+'.err.log'))
}

function Test-AgentSetupReady {
    param([string]$Root)
    foreach ($name in @('Office/setup.exe','Office/install.xml','Office/remove.xml','Hancom/Install/Hwp130.msi','Hancom/Install/VC_redist.x86.exe','Config/HancomKey.txt')) {
        if (-not (Test-Path -LiteralPath (Join-Path $Root $name) -PathType Leaf)) { return $false }
    }
    return $true
}
