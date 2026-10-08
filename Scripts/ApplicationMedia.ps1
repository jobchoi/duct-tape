function Get-ApplicationCatalog {
    param([string]$Root)
    $ErrorActionPreference='Stop'
    try { $catalog=Get-Content -LiteralPath (Join-Path $Root 'Config/Applications.json') -Raw -Encoding UTF8 | ConvertFrom-Json }
    catch { throw 'APPLICATION_CATALOG_INVALID' }
    if (-not $catalog.applications) { throw 'APPLICATION_CATALOG_INVALID' }
    $ids=@();$folders=@()
    foreach ($app in $catalog.applications) {
        if (-not $app.id -or $app.id -in $ids -or -not $app.media_folder -or $app.media_folder -in $folders -or
            ($app.media_folder.Contains('/') -or $app.media_folder.Contains('\') -or $app.media_folder.Contains(':')) -or -not $app.source_candidates -or -not $app.required_files -or -not $app.modules) { throw 'APPLICATION_CATALOG_INVALID' }
        $ids += $app.id;$folders += $app.media_folder
        foreach ($name in @($app.source_candidates)+@($app.required_files)+@($app.modules)+@($catalog.common_modules)+@($app.key_file)) {
            if ($name) {
                $normalized=$name.Replace('\','/')
                if ($normalized.StartsWith('/') -or $normalized.Contains(':') -or $normalized.Split('/') -contains '..') {throw 'APPLICATION_CATALOG_INVALID'}
            }
        }
    }
    foreach ($module in @($catalog.common_modules)+@($catalog.applications|ForEach-Object {$_.modules})) {
        if ($module -notmatch '^Modules/[^/]+\.ps1$') {throw 'APPLICATION_CATALOG_INVALID'}
    }
    return $catalog
}

function Resolve-ApplicationMedia {
    param([string]$Root, $Application)
    foreach ($candidate in $Application.source_candidates) {
        $directory=Join-Path $Root $candidate
        $missing=@($Application.required_files | Where-Object {-not (Test-Path -LiteralPath (Join-Path $directory $_) -PathType Leaf)})
        if ($missing.Count -eq 0) { return $directory }
    }
    foreach ($candidate in $Application.source_candidates) {
        $directory=Join-Path $Root $candidate
        if (@($Application.required_files | Where-Object {Test-Path -LiteralPath (Join-Path $directory $_) -PathType Leaf}).Count) {return $directory}
    }
    return Join-Path $Root $Application.source_candidates[0]
}
