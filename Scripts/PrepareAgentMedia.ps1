function Initialize-AgentMedia {
    param([string]$Root,[scriptblock]$Download)
    . (Join-Path $PSScriptRoot 'JobProgress.ps1')
    Write-JobProgress -Phase media_ready -Status started
    . (Join-Path $PSScriptRoot 'AgentActions.ps1')
    . (Join-Path $PSScriptRoot 'ApplicationMedia.ps1')
    $apps=(Get-ApplicationCatalog -Root $Root).applications
    if (Test-AgentSetupReady -Root $Root) {Write-JobProgress -Phase media_ready -Status completed; return}
    $agent = Get-Content (Join-Path $Root 'Config/Agent.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    $headers = if ($agent.AuthMode -eq 'development') { @{'X-Duct-Tape-Request'='1'; 'X-Duct-Device-ID'=$agent.DeviceId} } else { @{Authorization=('Bearer '+$agent.AgentToken)} }
    $work = Join-Path $Root ('media-stage-'+[guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory $work | Out-Null
    $phase='download'
    try {
        $zip = Join-Path $work 'media.zip'
        if ($Download) {& $Download ($agent.ServerUrl+'/api/agent/media') $headers $zip}
        else {Receive-AgentMedia -Uri ($agent.ServerUrl+'/api/agent/media') -Headers $headers -OutFile $zip}
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        $archive = [IO.Compression.ZipFile]::OpenRead($zip)
        try {
            foreach ($entry in $archive.Entries) {
                $name = $entry.FullName.Replace('\','/')
                $allowed=@($apps | Where-Object {$name.StartsWith($_.media_folder+'/') -or $name -eq $_.key_file}).Count -gt 0
                if ($name -match '(^/|(^|/)\.\.(/|$)|:)' -or
                    -not $allowed) {
                    throw '서버 매체 압축 파일에 허용되지 않은 경로가 있습니다.'
                }
            }
        } finally { $archive.Dispose() }
        $extract = Join-Path $work 'extracted'
        $phase='extract'
        Write-JobProgress -Phase extract -Status started
        New-Item -ItemType Directory $extract | Out-Null
        $archive=[IO.Compression.ZipFile]::OpenRead($zip)
        try {
            $total=$archive.Entries.Count;$done=0;$last=[DateTime]::UtcNow
            foreach ($entry in $archive.Entries) {
                $destination=Join-Path $extract $entry.FullName
                if ($entry.FullName.EndsWith('/')) {New-Item -ItemType Directory $destination -Force | Out-Null}
                else {
                    New-Item -ItemType Directory (Split-Path $destination -Parent) -Force | Out-Null
                    [IO.Compression.ZipFileExtensions]::ExtractToFile($entry,$destination,$true)
                }
                $done++
                if (([DateTime]::UtcNow-$last).TotalSeconds -ge 1) {Write-JobProgress -Phase extract -Status progress -Current $done -Total $total -Unit items;$last=[DateTime]::UtcNow}
            }
            Write-JobProgress -Phase extract -Status completed -Current $done -Total $total -Unit items
        } finally {$archive.Dispose()}
        $phase='prepare'
        Write-JobProgress -Phase prepare -Status started
        foreach ($app in $apps) {
            Copy-Item -LiteralPath (Join-Path $extract $app.media_folder) -Destination $Root -Recurse -Force
            if ($app.key_file) {Copy-Item -LiteralPath (Join-Path $extract $app.key_file) -Destination (Join-Path $Root $app.key_file) -Force}
        }
        if (-not (Test-AgentSetupReady -Root $Root)) { throw '서버에서 받은 설치 매체가 완전하지 않습니다.' }
        Write-JobProgress -Phase prepare -Status completed
        Write-JobProgress -Phase media_ready -Status completed
    } catch {Write-JobProgress -Phase $phase -Status failed;throw} finally { Remove-Item -LiteralPath $work -Recurse -Force }
}
