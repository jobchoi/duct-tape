$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$config = Get-Content (Join-Path $root 'Config/Agent.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$activePath = Join-Path $root 'Config/ActiveJob.json'
$logDirectory = Join-Path $root 'logs'
New-Item -ItemType Directory $logDirectory -Force | Out-Null
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
. (Join-Path $PSScriptRoot 'AgentActions.ps1')

function Invoke-AgentApi {
    param([string]$Path, $Body)
    $json = if ($null -eq $Body) { '{}' } else { $Body | ConvertTo-Json -Compress }
    Invoke-RestMethod -Uri ($config.ServerUrl+$Path) -Method Post -Headers @{Authorization=('Bearer '+$config.AgentToken)} -ContentType 'application/json' -Body $json -TimeoutSec 10 -MaximumRedirection 0
}

# A persisted claim is never automatically executed a second time.
while (Test-Path $activePath) {
    try {
        $active = Get-Content $activePath -Raw | ConvertFrom-Json
        $result = if ($active.state) { @{state=$active.state; exit_code=$active.exit_code} } else { @{state='interrupted'; exit_code=$null} }
        $null = Invoke-AgentApi ('/api/agent/jobs/'+([guid]$active.id).ToString()) $result
        Remove-Item $activePath
    } catch { Start-Sleep -Seconds 10 }
}
while ($true) {
    try {
        $claim = Invoke-AgentApi '/api/agent/claim' $null
        if ($null -eq $claim.job) { Start-Sleep -Seconds 5; continue }
        $job = $claim.job
        $jobId = ([guid]$job.id).ToString()
        @{id=$jobId} | ConvertTo-Json | Set-Content $activePath -Encoding UTF8
        $exitCode = 1
        try {
            $process = Start-AgentAction -Action $job.action -Root $root -JobId $jobId
            while (-not $process.WaitForExit(10000)) {
                try { $null = Invoke-AgentApi ('/api/agent/jobs/'+$jobId) @{state='running'} } catch { }
            }
            $process.Refresh()
            $exitCode = $process.ExitCode
            if ($exitCode -lt 0) { $exitCode = 1 }
        } catch { $exitCode = 1 }
        $state = if ($exitCode -eq 0) { 'succeeded' } else { 'failed' }
        @{id=$jobId; state=$state; exit_code=$exitCode} | ConvertTo-Json | Set-Content $activePath -Encoding UTF8
        while (Test-Path $activePath) {
            try {
                $null = Invoke-AgentApi ('/api/agent/jobs/'+$jobId) @{state=$state; exit_code=$exitCode}
                Remove-Item $activePath
            } catch { Start-Sleep -Seconds 10 }
        }
    } catch { Start-Sleep -Seconds 10 }
}
