param([Parameter(Mandatory=$true)][string]$StateFile)
. (Join-Path (Split-Path -Path $PSScriptRoot -Parent) 'Scripts/Common.ps1')
try {
    Send-DeploymentEvent -StateFile $StateFile -Stage '06' -Status running
    $key = Get-HancomKey
    $state = Read-DeploymentState $StateFile
    if ($state.HancomState -notin @('정상', '설치 필요')) { throw 'STATE_INVALID' }
    if ($state.HancomState -eq '설치 필요') {
        $msi = Join-Path $HancomDir 'Install\Hwp130.msi'
        $runtime = Join-Path $HancomDir 'Install\VC_redist.x86.exe'
        Assert-DeploymentFile $msi
        Assert-DeploymentFile $runtime
        Assert-HancomSilentConfiguration
        Write-DeploymentLog '06: 잔존 설치 프로세스 정리'
        Stop-Process -Name 'Install', 'setup', 'msiexec' -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 2
        $paths = @('HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*',
            'HKLM:\SOFTWARE\Wow6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*')
        $oldApps = @(Get-ItemProperty $paths -ErrorAction SilentlyContinue |
            Where-Object { $_.DisplayName -like '*한컴오피스*' -and $_.DisplayName -notlike '*2024*' })
        foreach ($app in $oldApps) {
            if ($app.PSChildName -match '^\{[0-9A-Fa-f-]{36}\}$') {
                $code = Invoke-DeploymentProcess 'msiexec.exe' "/x $($app.PSChildName) /qn /norestart" @(0, 1605, 1614, 3010)
            } else {
                # Preserve registry arguments, but never execute through a shell.
                $command = $app.UninstallString
                if ($command -match '^\s*"([^"]+\.exe)"\s*(.*)$' -or
                    $command -match '^\s*(.+?\.exe)(?:\s+(.*))?$') {
                    $exe = [Environment]::ExpandEnvironmentVariables($Matches[1])
                    $arguments = $Matches[2]
                    Assert-DeploymentFile $exe
                    $code = Invoke-DeploymentProcess $exe ($arguments + ' /s /v"/qn"')
                } else { throw 'UNINSTALL_COMMAND_INVALID' }
            }
            Set-RebootRequired $state $code
        }
        Start-Sleep -Seconds 3
        $code = Invoke-DeploymentProcess $runtime '/install /quiet /norestart'
        Set-RebootRequired $state $code
        Start-Sleep -Seconds 3
        # Do not enable verbose MSI logging with the license property.
        $arguments = "/i `"$msi`" /qn AGREETOLICENSE=yes PIDKEY=$key /norestart"
        $code = Invoke-DeploymentProcess 'msiexec.exe' $arguments
        Set-RebootRequired $state $code
        $key = $null
        $arguments = $null
        $state.HancomState = '정상'
        Write-DeploymentState $StateFile $state
        Write-DeploymentLog '06: 한컴 설치 완료'
    } else { Write-DeploymentLog '06: 한컴 설치 건너뜀' }

    Send-DeploymentEvent -StateFile $StateFile -Stage '06' -Status completed
    exit 0
} catch {
    Write-DeploymentFailure '06' $_.Exception.Message
    exit 1
}
