function Get-AgentRegistration {
    param([string]$ServerUrl, [string]$DeviceId, [string]$Hostname, $Stored)
    if ($Stored -and $Stored.DeviceId -ne $DeviceId) { throw '로컬 PC 식별값이 다릅니다. 다른 PC의 설정 파일을 복사하지 마세요.' }
    if ($Stored -and $Stored.ServerUrl.TrimEnd('/') -eq $ServerUrl.TrimEnd('/')) {
        $headers = if ($Stored.AuthMode -eq 'development') { @{'X-Duct-Tape-Request'='1';'X-Duct-Device-ID'=$DeviceId} } else { @{Authorization=('Bearer '+$Stored.AgentToken)} }
        try {
            $status = Invoke-RestMethod -Uri ($ServerUrl+'/api/agent/status') -Headers $headers -TimeoutSec 10 -MaximumRedirection 0
            if (@($status.jobs | Where-Object {$_.state -in @('queued','running','interrupted')}).Count) { throw 'PC 작업이 진행 중이거나 중단 확인이 필요합니다. 작업을 먼저 정리하세요.' }
            $result = Invoke-RestMethod -Uri ($ServerUrl+'/api/agent/reconnect') -Headers $headers -Method Post -ContentType 'application/json' -Body '{}' -TimeoutSec 10 -MaximumRedirection 0
            return [pscustomobject]@{device_id=$DeviceId;agent_token=$Stored.AgentToken;client_token=$result.client_token;auth_mode=$result.auth_mode;approved=$result.approved}
        } catch {
            $code=0
            try {$code=[int]$_.Exception.Response.StatusCode} catch {}
            if ($code -ne 401) { throw '기존 연결 상태를 확인할 수 없거나 작업이 진행 중입니다. 서버 연결과 PC 작업 상태를 먼저 확인하세요.' }
            # A missing/revoked server registration can be safely rejoined.
        }
    }
    $body=@{device_id=$DeviceId;hostname=$Hostname} | ConvertTo-Json -Compress
    try { return Invoke-RestMethod -Uri ($ServerUrl+'/api/agent/join') -Method Post -ContentType 'application/json' -Body $body -TimeoutSec 10 -MaximumRedirection 0 }
    catch {
        $code=0
        try {$code=[int]$_.Exception.Response.StatusCode} catch {}
        if ($code -eq 409) { throw '서버에 PC가 남아 있지만 로컬 인증 정보가 일치하지 않습니다. 관리자에서 연결 해제 후 다시 실행하세요.' }
        throw 'PC 연결 복구에 실패했습니다. 서버 주소와 Tailscale 연결을 확인하세요.'
    }
}
