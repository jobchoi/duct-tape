param([string]$OutputDirectory, [string]$ServerUrl, [string]$JobId,
    [string]$AgentRoot = (Join-Path $env:ProgramData 'DuctTapeAgent'))

function Get-DiagnosticSignals {
    param([string]$Path)
    $allowed = @('INSTALL_PROCESS_FAILED','STATE_INVALID','APPLICATION_MODULE_FAILED',
        'OFFICE_KEY_MISSING','HANCOM_KEY_MISSING','KEY_MISSING','REPORT_UNAVAILABLE',
        'JOB_EXIT_CODE_UNAVAILABLE','VC_RUNTIME_FAILED','VC_RUNTIME_NOT_FOUND')
    $signals = @()
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $signals }
    foreach ($line in (Get-Content -LiteralPath $Path -Tail 500 -Encoding UTF8 -ErrorAction Stop)) {
        if ($line -match 'PROCESS_EXIT:\s*(-?\d+)') {
            $signals += @{kind='process_exit';exit_code=[long]$Matches[1]}
        } elseif ($line -match '^AGENT_RESULT: state=(succeeded|failed) exit_code=(-?\d+)\s*$') {
            $signals += @{kind='agent_result';state=$Matches[1];exit_code=[long]$Matches[2]}
        } else {
            foreach ($code in $allowed) {
                if ($line -match ('(?<![A-Z0-9_])'+[regex]::Escape($code)+'(?![A-Z0-9_])')) {
                    $signals += @{kind='error_code';code=$code}
                }
            }
        }
    }
    return $signals
}

function Get-DiagnosticOrigin {
    param([string]$Value)
    $uri = $null
    if (-not [uri]::TryCreate($Value,[UriKind]::Absolute,[ref]$uri)) { return '' }
    if ($uri.UserInfo -or $uri.Query -or $uri.Fragment -or $uri.AbsolutePath -ne '/') { return '' }
    if ($uri.Scheme -ne 'https' -and -not ($uri.Scheme -eq 'http' -and $uri.IsLoopback)) { return '' }
    return $uri.GetLeftPart([UriPartial]::Authority)
}

function Invoke-ClientDiagnostics {
    param([string]$OutputDirectory, [string]$ServerUrl, [string]$JobId,
        [string]$AgentRoot = (Join-Path $env:ProgramData 'DuctTapeAgent'))
    if ($JobId -and $JobId -notmatch '^[0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}$') {
        throw 'DIAGNOSTIC_JOB_ID_INVALID'
    }
    if (-not $OutputDirectory) {
        $OutputDirectory = Join-Path ([IO.Path]::GetTempPath()) ('duct-diagnostics-'+[guid]::NewGuid().ToString('N'))
    }
    if (Test-Path -LiteralPath $OutputDirectory) { throw 'DIAGNOSTIC_OUTPUT_EXISTS' }
    $report = [ordered]@{schema_version=1;created_at=[DateTime]::UtcNow.ToString('o');
        computer=@{};agent=@{};applications=@();states=@();logs=@();server=@{checked=$false};issues=@()}
    try {
        $cs = Get-CimInstance -ClassName Win32_ComputerSystem -ErrorAction Stop
        $bios = Get-CimInstance -ClassName Win32_BIOS -ErrorAction Stop
        $os = Get-CimInstance -ClassName Win32_OperatingSystem -ErrorAction Stop
        $report.computer = @{hostname=[string]$env:COMPUTERNAME;manufacturer=[string]$cs.Manufacturer;
            model=[string]$cs.Model;serial=[string]$bios.SerialNumber;pc_system_type=[int]$cs.PCSystemType;
            os=[string]$os.Caption;version=[string]$os.Version;architecture=[string]$os.OSArchitecture}
    } catch { $report.issues += 'DEVICE_INFO_UNAVAILABLE' }
    $configPath = Join-Path $AgentRoot 'Config/Agent.json'
    $report.agent.config_present = Test-Path -LiteralPath $configPath -PathType Leaf
    if ($report.agent.config_present) {
        try {
            $config = Get-Content -LiteralPath $configPath -Raw -Encoding UTF8 -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
            $origin = Get-DiagnosticOrigin ([string]$config.ServerUrl)
            $report.agent.server_origin = $origin
            $parsedId = [guid]::Empty
            if ([guid]::TryParse([string]$config.DeviceId,[ref]$parsedId)) { $report.agent.device_id = $parsedId.ToString() }
            if (-not $ServerUrl) { $ServerUrl = $origin }
        } catch { $report.issues += 'AGENT_CONFIG_UNREADABLE' }
    }
    try {
        $task = Get-ScheduledTask -TaskName 'DuctTapeAgent' -ErrorAction Stop
        $report.agent.task_state = [string]$task.State
    } catch { $report.agent.task_state = 'not_found_or_inaccessible' }
    try {
        # Read registry only. Win32_Product can trigger MSI repair and is never queried.
        $paths = @('HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*',
            'HKLM:\SOFTWARE\Wow6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*')
        $apps = @(Get-ItemProperty -Path $paths -ErrorAction SilentlyContinue |
            Where-Object { $_.DisplayName -match 'Office|Microsoft 365|한컴|Hancom|Hangeul' })
        $report.applications = @($apps | ForEach-Object { @{name=[string]$_.DisplayName;version=[string]$_.DisplayVersion} })
    } catch { $report.issues += 'APPLICATION_INVENTORY_UNAVAILABLE' }
    $statePaths = @((Join-Path $env:TEMP 'Tapbook_State.json'),(Join-Path $env:windir 'Temp/Tapbook_State.json')) | Select-Object -Unique
    foreach ($path in $statePaths) {
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { continue }
        try {
            $state = Get-Content -LiteralPath $path -Raw -Encoding UTF8 -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
            $known = @('확인 전','설치 필요','설치 중','정상','오류')
            $office = if ($state.OfficeState -in $known) { [string]$state.OfficeState } else { '확인 전' }
            $hancom = if ($state.HancomState -in $known) { [string]$state.HancomState } else { '확인 전' }
            $report.states += @{path=$path;modified_at=(Get-Item -LiteralPath $path).LastWriteTimeUtc.ToString('o');office=$office;hancom=$hancom;reboot_required=($state.RebootRequired -eq $true)}
        } catch { $report.issues += 'DEPLOYMENT_STATE_UNREADABLE' }
    }
    $logPaths = @((Join-Path $env:TEMP 'duct-tape/Deployment.log'),(Join-Path $env:windir 'Temp/duct-tape/Deployment.log'))
    $logRoot = Join-Path $AgentRoot 'logs'
    if (Test-Path -LiteralPath $logRoot -PathType Container) {
        $files = @(Get-ChildItem -LiteralPath $logRoot -File -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -match '^[0-9a-fA-F-]{36}\.(out|err)\.log$' -and (-not $JobId -or $_.Name.StartsWith($JobId,[StringComparison]::OrdinalIgnoreCase)) } |
            Sort-Object LastWriteTimeUtc -Descending | Select-Object -First 6)
        $logPaths += @($files | ForEach-Object { $_.FullName })
    }
    foreach ($path in ($logPaths | Select-Object -Unique)) {
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { continue }
        try {
            $file = Get-Item -LiteralPath $path -ErrorAction Stop
            $report.logs += @{path=$path;bytes=$file.Length;modified_at=$file.LastWriteTimeUtc.ToString('o');signals=@(Get-DiagnosticSignals $path)}
        } catch { $report.issues += 'LOG_UNREADABLE' }
    }
    if ($ServerUrl) {
        $origin = Get-DiagnosticOrigin $ServerUrl
        if (-not $origin) { $report.issues += 'SERVER_ORIGIN_INVALID' }
        else {
            try {
                $data = Invoke-RestMethod -Uri ($origin+'/api/config') -Method Get -TimeoutSec 5 -MaximumRedirection 0 -ErrorAction Stop
                $report.server = @{checked=$true;origin=$origin;reachable=$true;media_ready=($data.media.ready -eq $true)}
            } catch { $report.server = @{checked=$true;origin=$origin;reachable=$false} }
        }
    }
    New-Item -ItemType Directory -Path $OutputDirectory -ErrorAction Stop | Out-Null
    $output = Join-Path $OutputDirectory 'report.json'
    [IO.File]::WriteAllText($output,($report | ConvertTo-Json -Depth 8),(New-Object Text.UTF8Encoding($false)))
    return $output
}

if ($MyInvocation.InvocationName -eq '.') { return }
try {
    $result = Invoke-ClientDiagnostics -OutputDirectory $OutputDirectory -ServerUrl $ServerUrl -JobId $JobId -AgentRoot $AgentRoot
    Write-Host ('진단 결과: '+$result)
    Write-Host '설치·제거·등록 변경 없이 읽기 전용 점검했습니다. 기기 식별 정보가 있으므로 결과를 공개 게시하지 마세요.'
} catch {
    Write-Error 'DIAGNOSTICS_FAILED: 출력 폴더·접근 권한·작업 ID를 확인하세요.'
    exit 1
}
