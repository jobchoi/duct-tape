function Initialize-AgentMedia {
    param([string]$Root)
    . (Join-Path $PSScriptRoot 'AgentActions.ps1')
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
                if ($name -match '(^/|(^|/)\.\.(/|$)|:)' -or
                    -not ($name.StartsWith('Office/') -or $name.StartsWith('Hancom/') -or $name -in @('Config/HancomKey.txt','Config/OfficeKey.txt'))) {
                    throw '서버 매체 압축 파일에 허용되지 않은 경로가 있습니다.'
                }
            }
        } finally { $archive.Dispose() }
        $extract = Join-Path $work 'extracted'
        Expand-Archive -LiteralPath $zip -DestinationPath $extract
        foreach ($folder in @('Office','Hancom')) {
            Copy-Item -LiteralPath (Join-Path $extract $folder) -Destination $Root -Recurse -Force
        }
        foreach ($name in @('HancomKey.txt','OfficeKey.txt')) {
            Copy-Item -LiteralPath (Join-Path $extract ('Config/'+$name)) -Destination (Join-Path $Root ('Config/'+$name)) -Force
        }
        if (-not (Test-AgentSetupReady -Root $Root)) { throw '서버에서 받은 설치 매체가 완전하지 않습니다.' }
    } finally { Remove-Item -LiteralPath $work -Recurse -Force }
}
