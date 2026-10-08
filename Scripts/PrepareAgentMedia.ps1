function Initialize-AgentMedia {
    param([string]$Root)
    . (Join-Path $PSScriptRoot 'AgentActions.ps1')
    . (Join-Path $PSScriptRoot 'ApplicationMedia.ps1')
    $apps=(Get-ApplicationCatalog -Root $Root).applications
    if (Test-AgentSetupReady -Root $Root) { return }
    $agent = Get-Content (Join-Path $Root 'Config/Agent.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    $headers = if ($agent.AuthMode -eq 'development') { @{'X-Duct-Tape-Request'='1'; 'X-Duct-Device-ID'=$agent.DeviceId} } else { @{Authorization=('Bearer '+$agent.AgentToken)} }
    $work = Join-Path $Root ('media-stage-'+[guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory $work | Out-Null
    try {
        $zip = Join-Path $work 'media.zip'
        Invoke-WebRequest -Uri ($agent.ServerUrl+'/api/agent/media') -Headers $headers -OutFile $zip -UseBasicParsing -TimeoutSec 1800 -MaximumRedirection 0 | Out-Null
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
        Expand-Archive -LiteralPath $zip -DestinationPath $extract
        foreach ($app in $apps) {
            Copy-Item -LiteralPath (Join-Path $extract $app.media_folder) -Destination $Root -Recurse -Force
            if ($app.key_file) {Copy-Item -LiteralPath (Join-Path $extract $app.key_file) -Destination (Join-Path $Root $app.key_file) -Force}
        }
        if (-not (Test-AgentSetupReady -Root $Root)) { throw '서버에서 받은 설치 매체가 완전하지 않습니다.' }
    } finally { Remove-Item -LiteralPath $work -Recurse -Force }
}
