$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
. (Join-Path $root 'Scripts/AgentActions.ps1')
$fixture=Join-Path $env:TEMP ('duct-process-'+[guid]::NewGuid().ToString('N'))
try {
    New-Item -ItemType Directory (Join-Path $fixture 'Scripts') -Force | Out-Null
    New-Item -ItemType Directory (Join-Path $fixture 'logs') -Force | Out-Null
    $runner=Join-Path $fixture 'Scripts/RunAgentJob.ps1'
    foreach ($code in @(0,1,3010)) {
        $content=@'
param([guid]$JobId,[switch]$ReportOnly)
[Console]::OutputEncoding=New-Object Text.UTF8Encoding($false)
Write-Host '한컴 설치 완료'
exit EXIT_CODE
'@
        Set-Content $runner ($content.Replace('EXIT_CODE',[string]$code)) -Encoding UTF8
        $id=[guid]::NewGuid().ToString()
        $process=Start-AgentAction -Action deploy -Root $fixture -JobId $id
        while(-not $process.WaitForExit(2000)) {}
        $process.Refresh()
        if ($null -eq $process.ExitCode -or $process.ExitCode -ne $code) { throw "ExitCode lost: expected $code" }
        $process.WaitForExit()
        $text=Get-Content (Join-Path $fixture ('logs/'+$id+'.out.log')) -Raw -Encoding UTF8
        if ($text.Trim() -ne '한컴 설치 완료') { throw 'Korean output corrupted' }
        $process.Dispose()
    }
    Write-Host 'PASS: real redirected Windows processes preserve 0/1/3010 and Korean UTF8 output; no installers run'
} finally {Remove-Item $fixture -Recurse -Force}
