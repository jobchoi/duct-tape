param([string]$StateFile)
function Invoke-ApplicationPlan {
    param([string]$Root, [string]$StateFile)
    . (Join-Path $PSScriptRoot 'ApplicationMedia.ps1')
    . (Join-Path $PSScriptRoot 'JobProgress.ps1')
    $catalog=Get-ApplicationCatalog -Root $Root
    $modules=@($catalog.common_modules)+@($catalog.applications | ForEach-Object {$_.modules})
    foreach ($module in $modules) {
        if ($module -notmatch '^Modules/[^/]+\.ps1$' -or -not (Test-Path -LiteralPath (Join-Path $Root $module) -PathType Leaf)) {throw 'APPLICATION_MODULE_MISSING'}
    }
    foreach ($app in $catalog.applications) {
        if ($app.key_file -and -not (Test-Path -LiteralPath (Join-Path $Root $app.key_file) -PathType Leaf)) {throw 'APPLICATION_KEY_MISSING'}
    }
    $done=0
    foreach ($module in $modules) {
        Write-JobProgress -Phase module -Status started -Module ([IO.Path]::GetFileName($module)) -Current $done -Total $modules.Count -Unit steps
        Write-Host ('실행: '+[IO.Path]::GetFileName($module))
        try {Invoke-ApplicationModule -Path (Join-Path $Root $module) -StateFile $StateFile}
        catch {Write-JobProgress -Phase module -Status failed -Module ([IO.Path]::GetFileName($module)) -Current $done -Total $modules.Count -Unit steps;throw}
        $done++
        Write-JobProgress -Phase module -Status completed -Module ([IO.Path]::GetFileName($module)) -Current $done -Total $modules.Count -Unit steps
    }
}
function Invoke-ApplicationModule {
    param([string]$Path,[string]$StateFile)
    $engine=(Get-Process -Id $PID).Path
    & $engine -NoProfile -ExecutionPolicy Bypass -File $Path -StateFile $StateFile
    if ($LASTEXITCODE -ne 0) {throw 'APPLICATION_MODULE_FAILED'}
}
if ($MyInvocation.InvocationName -eq '.') {return}
try {
    if (-not $StateFile) {throw 'STATE_PATH_MISSING'}
    Invoke-ApplicationPlan -Root (Split-Path $PSScriptRoot -Parent) -StateFile $StateFile
} catch {
    Write-Host '애플리케이션 모듈 실행을 중단했습니다. 직전 모듈의 상태와 오류 코드를 확인하세요.'
    exit 1
}
