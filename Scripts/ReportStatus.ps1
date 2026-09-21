# Optional reporting: all configuration/network failures are isolated from installation.
param(
    [string]$StateFile,
    [ValidateSet('Preflight','01','02','03','04','05','06')][string]$Stage = 'Preflight',
    [ValidateSet('running','completed','failed')][string]$Status = 'running',
    [string]$ErrorCode = '',
    [Nullable[int]]$InstallerExitCode = $null,
    [string]$ConfigPath = (Join-Path (Split-Path $PSScriptRoot -Parent) 'Config/Monitoring.json')
)

function Send-StatusReport {
    param([string]$StateFile, [string]$Stage, [string]$Status, [string]$ErrorCode,
        [Nullable[int]]$InstallerExitCode, [string]$ConfigPath)
    try {
        if (-not (Test-Path -LiteralPath $ConfigPath -PathType Leaf)) { return $false }
        $config = Get-Content -LiteralPath $ConfigPath -Raw -Encoding UTF8 -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
        if ($config.Enabled -ne $true) { return $false }
        $uri = [uri]$config.ServerUrl
        if (-not $uri.IsAbsoluteUri -or $uri.UserInfo -or $uri.Query -or $uri.Fragment -or
            $uri.AbsolutePath -ne '/' -or $uri.Scheme -notin @('http','https') -or
            ($uri.Scheme -eq 'http' -and $config.AllowHttp -ne $true)) { throw 'REPORT_CONFIG' }
        if ([string]::IsNullOrWhiteSpace($config.ReportToken) -or $config.ReportToken.Length -lt 32 -or
            $config.ReportToken -match '\s' -or $config.ReportToken -eq 'REPLACE_WITH_REPORT_TOKEN_AT_LEAST_32_CHARS') { throw 'REPORT_CONFIG' }
        $timeout = 3
        $attempts = 2
        if ($null -ne $config.TimeoutSeconds) { $timeout = [int]$config.TimeoutSeconds }
        if ($null -ne $config.MaxAttempts) { $attempts = [int]$config.MaxAttempts }
        if ($timeout -lt 1 -or $timeout -gt 10 -or $attempts -lt 1 -or $attempts -gt 3) { throw 'REPORT_CONFIG' }
        $state = $null
        if ($StateFile -and (Test-Path -LiteralPath $StateFile -PathType Leaf) -and
            -not ($Stage -eq '01' -and $Status -eq 'running') -and $Stage -ne 'Preflight') {
            try { $state = Get-Content -LiteralPath $StateFile -Raw -Encoding UTF8 -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop }
            catch { $state = $null }
        }
        $identity = (Get-ItemProperty -LiteralPath 'HKLM:\SOFTWARE\Microsoft\Cryptography' -Name MachineGuid -ErrorAction Stop).MachineGuid
        $deviceId = ([guid]$identity).ToString()
        $mac = ''
        if ($state.MAC) { $mac = [string]$state.MAC }
        else {
            try {
                $adapter = Get-CimInstance Win32_NetworkAdapterConfiguration -Filter 'IPEnabled=True' -ErrorAction Stop |
                    Where-Object { $_.MACAddress } | Sort-Object MACAddress | Select-Object -First 1
                $mac = [string]$adapter.MACAddress
            } catch { $mac = '' }
        }
        $mac = $mac.Replace('-', ':').ToUpperInvariant()
        if ($mac -notmatch '^(?:[0-9A-F]{2}:){5}[0-9A-F]{2}$') { $mac = '' }
        $office = '확인 전'; $hancom = '확인 전'
        $states = @('확인 전','설치 필요','설치 중','정상','오류')
        if ($state.OfficeState -in $states) { $office = $state.OfficeState }
        if ($state.HancomState -in $states) { $hancom = $state.HancomState }
        if ($Status -eq 'running' -and $Stage -eq '04' -and $office -eq '설치 필요') { $office = '설치 중' }
        if ($Status -eq 'running' -and $Stage -eq '06' -and $hancom -eq '설치 필요') { $hancom = '설치 중' }
        if ($Status -eq 'failed' -and $Stage -in @('02','03','04')) { $office = '오류' }
        if ($Status -eq 'failed' -and $Stage -in @('05','06')) { $hancom = '오류' }
        if ($ErrorCode -notmatch '^[A-Z0-9_]{0,64}$') { $ErrorCode = 'OPERATION_FAILED' }
        $hostname = [string]$env:COMPUTERNAME
        if (-not $hostname) { $hostname = [Environment]::MachineName }
        # Explicit allowlist: never serialize full state/config or raw exceptions.
        $payload = @{
            device_id = $deviceId; report_id = [guid]::NewGuid().ToString()
            hostname = $hostname; serial = [string]$state.SerialNumber; model = [string]$state.Model; mac = $mac
            office = $office; hancom = $hancom; stage = $Stage; status = $Status; error_code = $ErrorCode
            installer_exit_code = $InstallerExitCode; reboot_required = ($state.RebootRequired -eq $true)
            observed_at = [DateTime]::UtcNow.ToString('o')
        }
        if ($null -ne $config.SchoolCode -and [string]$config.SchoolCode -ne '') {
            if ([string]$config.SchoolCode -cnotmatch '^[A-Z0-9_-]{1,32}$') { throw 'REPORT_CONFIG' }
            $grade = $null
            if ($null -ne $config.Grade) {
                if (($config.Grade -isnot [int] -and $config.Grade -isnot [long]) -or
                    $config.Grade -lt 1 -or $config.Grade -gt 6) { throw 'REPORT_CONFIG' }
                $grade = [int]$config.Grade
            }
            $payload.school_code = [string]$config.SchoolCode
            $payload.grade = $grade
        } elseif ($null -ne $config.Grade) { throw 'REPORT_CONFIG' }
        $body = [Text.Encoding]::UTF8.GetBytes(($payload | ConvertTo-Json -Depth 3 -Compress))
        for ($attempt = 1; $attempt -le $attempts; $attempt++) {
            try {
                $null = Invoke-RestMethod -Uri ($uri.AbsoluteUri.TrimEnd('/') + '/api/report') -Method Post `
                    -Headers @{ Authorization = ('Bearer ' + $config.ReportToken) } -Body $body `
                    -ContentType 'application/json; charset=utf-8' -TimeoutSec $timeout -MaximumRedirection 0 -ErrorAction Stop
                return $true
            } catch {
                $httpCode = 0
                try { $httpCode = [int]$_.Exception.Response.StatusCode } catch { }
                if ($httpCode -in @(400,401,403,404,422) -or $attempt -eq $attempts) { break }
                Start-Sleep -Seconds 1
            }
        }
    } catch { }
    Write-Warning 'REPORT_UNAVAILABLE: 중앙 보고를 건너뛰고 설치를 계속합니다.'
    return $false
}

if ($PSBoundParameters.ContainsKey('StateFile')) {
    $null = Send-StatusReport -StateFile $StateFile -Stage $Stage -Status $Status -ErrorCode $ErrorCode `
        -InstallerExitCode $InstallerExitCode -ConfigPath $ConfigPath
}
