function Sync-AgentLicenseKeys {
    param([string]$Root, [scriptblock]$Request)
    try {
        $agent = Get-Content (Join-Path $Root 'Config/Agent.json') -Raw -Encoding UTF8 | ConvertFrom-Json
        $headers = if ($agent.AuthMode -eq 'development') { @{'X-Duct-Tape-Request'='1';'X-Duct-Device-ID'=$agent.DeviceId} } else { @{Authorization=('Bearer '+$agent.AgentToken)} }
        $uri = $agent.ServerUrl.TrimEnd('/')+'/api/agent/licenses'
        if ($Request) { $result = & $Request $uri $headers }
        else {
            try { $result = Invoke-RestMethod -Uri $uri -Headers $headers -TimeoutSec 20 -MaximumRedirection 0 }
            catch {
                $status = 0
                try { $status = [int]$_.Exception.Response.StatusCode } catch {}
                if ($status -eq 404) { Write-Host 'LICENSE_SYNC_LEGACY_SERVER'; return }
                throw 'LICENSE_SYNC_FAILED'
            }
        }
        if ($null -eq $result -or $null -eq $result.keys) { throw 'LICENSE_SYNC_FAILED' }
        $paths = @{office='Config/OfficeKey.txt';hancom='Config/HancomKey.txt'}
        $updates = @();$seen = @{}
        foreach ($entry in $result.keys) {
            if (-not $paths.ContainsKey([string]$entry.app) -or $seen.ContainsKey([string]$entry.app)) { throw 'LICENSE_SYNC_FAILED' }
            $seen[$entry.app] = $true
            $key = [string]$entry.key
            $pattern = if ($entry.app -eq 'office') { '^[A-Za-z0-9]{5}(?:-[A-Za-z0-9]{5}){4}$' } else { '^[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*$' }
            if ($key.Length -gt 160 -or $key -notmatch $pattern) { throw 'LICENSE_SYNC_FAILED' }
            $updates += @{path=(Join-Path $Root $paths[$entry.app]);key=$key}
        }
        foreach ($update in $updates) {
            $temporary = $update.path+'.'+[guid]::NewGuid().ToString('N')+'.tmp'
            try {
                [IO.File]::WriteAllText($temporary,$update.key,(New-Object Text.UTF8Encoding($false)))
                Move-Item -LiteralPath $temporary -Destination $update.path -Force
            } finally { if (Test-Path -LiteralPath $temporary) { Remove-Item -LiteralPath $temporary -Force -ErrorAction SilentlyContinue } }
        }
        Write-Host 'LICENSE_SYNC_COMPLETED'
    } catch { throw 'LICENSE_SYNC_FAILED' }
}
