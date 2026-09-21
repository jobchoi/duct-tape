# Windows PowerShell 5.1; dot-source from Modules or Scripts.
$DeployRoot = Split-Path -Path $PSScriptRoot -Parent
$ConfigDir = Join-Path $DeployRoot 'Config'
$HancomDir = Join-Path $DeployRoot 'Hancom'
$OfficeDir = Join-Path $DeployRoot 'Office'
$ErrorActionPreference = 'Stop'
$script:LastInstallerExitCode = $null

function Read-DeploymentState {
    param([Parameter(Mandatory=$true)][string]$Path)
    try {
        $value = Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($null -eq $value -or $null -eq $value.OfficeState -or $null -eq $value.HancomState) { throw 'invalid' }
        return $value
    } catch { throw 'STATE_READ_FAILED' }
}

function Write-DeploymentState {
    param([Parameter(Mandatory=$true)][string]$Path, [Parameter(Mandatory=$true)]$State)
    $temporary = "$Path.$([guid]::NewGuid().ToString('N')).tmp"
    try {
        $State | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $temporary -Encoding UTF8
        Move-Item -LiteralPath $temporary -Destination $Path -Force
    } catch { throw 'STATE_WRITE_FAILED' }
    finally { if (Test-Path -LiteralPath $temporary) { Remove-Item -LiteralPath $temporary -Force -ErrorAction SilentlyContinue } }
}

function Write-DeploymentLog {
    param([Parameter(Mandatory=$true)][string]$Message, [string]$Level = 'INFO')
    # Callers supply fixed messages/codes only, never keys or process arguments.
    $line = '{0} [{1}] {2}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Level, $Message
    Write-Host $line
    try {
        $directory = Join-Path ([IO.Path]::GetTempPath()) 'duct-tape'
        New-Item -ItemType Directory -Path $directory -Force | Out-Null
        Add-Content -LiteralPath (Join-Path $directory 'Deployment.log') -Value $line -Encoding UTF8
    } catch { Write-Warning 'LOG_WRITE_FAILED' }
}

function Get-HancomKey {
    $path = Join-Path $ConfigDir 'HancomKey.txt'
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw 'KEY_MISSING' }
    try { $key = (Get-Content -LiteralPath $path -Raw -Encoding UTF8).Trim() }
    catch { throw 'KEY_UNREADABLE' }
    # Restrict command-line metacharacters without assuming a vendor key length.
    if ([string]::IsNullOrWhiteSpace($key) -or $key -eq 'REPLACE_WITH_YOUR_LICENSE_KEY' -or
        $key -eq '---' -or $key -notmatch '^[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*$') { throw 'KEY_INVALID' }
    return $key
}

function Assert-DeploymentFile {
    param([Parameter(Mandatory=$true)][string]$Path)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw 'MEDIA_MISSING' }
}

function Unblock-DeploymentFiles {
    $failures = @()
    Get-ChildItem -LiteralPath $DeployRoot -File -Recurse -ErrorAction SilentlyContinue -ErrorVariable +failures |
        Unblock-File -ErrorAction SilentlyContinue -ErrorVariable +failures
    if ($failures.Count -gt 0) { Write-DeploymentLog 'UNBLOCK_INCOMPLETE: 배포 파일 권한과 보안 정책을 확인하세요.' 'WARN' }
}

function Assert-HancomSilentConfiguration {
    # Shared/read-only media is prepared once by the operator, never concurrently rewritten by clients.
    $files = @(Get-ChildItem -LiteralPath $HancomDir -Filter setup.ini -File -Recurse)
    if ($files.Count -eq 0) { throw 'HANCOM_INI_MISSING' }
    foreach ($file in $files) {
        $settings = @(Get-Content -LiteralPath $file.FullName | Where-Object { $_ -match '^\s*LevelOption\s*=' })
        if ($settings.Count -eq 0) { throw 'HANCOM_INI_INVALID' }
        foreach ($setting in $settings) {
            if ($setting -notmatch '^\s*LevelOption\s*=\s*1\s*(?:[;#].*)?$') { throw 'HANCOM_INI_INVALID' }
        }
    }
}

function Invoke-DeploymentProcess {
    param([string]$FilePath, [string]$Arguments, [int[]]$SuccessCodes = @(0, 3010))
    $process = Start-Process -FilePath $FilePath -ArgumentList $Arguments -Wait -PassThru -WindowStyle Hidden
    $script:LastInstallerExitCode = [int]$process.ExitCode
    Write-DeploymentLog ('PROCESS_EXIT: {0}' -f $process.ExitCode)
    if ($process.ExitCode -notin $SuccessCodes) { throw 'INSTALL_PROCESS_FAILED' }
    return [int]$process.ExitCode
}

function Set-RebootRequired {
    param($State, [int]$ExitCode)
    if ($ExitCode -eq 3010) { $State | Add-Member -NotePropertyName RebootRequired -NotePropertyValue $true -Force }
}

function Write-DeploymentFailure {
    param([string]$Module, [string]$Code)
    $known = @('KEY_MISSING','KEY_UNREADABLE','KEY_INVALID','STATE_READ_FAILED','STATE_WRITE_FAILED',
        'MEDIA_MISSING','HANCOM_INI_MISSING','HANCOM_INI_INVALID','INSTALL_PROCESS_FAILED',
        'UNINSTALL_COMMAND_INVALID','STATE_INVALID')
    if ($Code -notin $known) { $Code = 'OPERATION_FAILED' }
    Write-DeploymentLog "$Module : $Code" 'ERROR'
    Send-DeploymentEvent -StateFile $StateFile -Stage $Module -Status failed -ErrorCode $Code
}

function Send-DeploymentEvent {
    param([string]$StateFile, [string]$Stage, [string]$Status, [string]$ErrorCode = '')
    try {
        $reporter = Join-Path $DeployRoot 'Scripts/ReportStatus.ps1'
        if (Test-Path -LiteralPath $reporter -PathType Leaf) {
            & $reporter -StateFile $StateFile -Stage $Stage -Status $Status -ErrorCode $ErrorCode `
                -InstallerExitCode $script:LastInstallerExitCode
        }
    } catch { Write-Warning 'REPORT_UNAVAILABLE: 설치를 계속합니다.' }
}
