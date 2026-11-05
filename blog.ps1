# Standalone Blogger environment; never installs into the server environment.
$ErrorActionPreference = 'Stop'
$BlogRoot = $PSScriptRoot
$BlogEnv = Join-Path $BlogRoot '.venv-blog'
$BlogPython = Join-Path $BlogEnv 'Scripts/python.exe'
if ($args.Count -gt 0 -and $args[0] -eq 'setup') {
    Write-Host "실행 명령: py -3 -m venv $BlogEnv"
    & py -3 -m venv $BlogEnv
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    Write-Host "실행 명령: $BlogPython -m pip install -r tools/blogger/requirements.txt"
    & $BlogPython -m pip install -r (Join-Path $BlogRoot 'tools/blogger/requirements.txt')
    exit $LASTEXITCODE
}
if (-not (Test-Path -LiteralPath $BlogPython)) {
    throw '먼저 .\blog.ps1 setup 을 실행하세요.'
}
Write-Host "실행 명령: $BlogPython tools/blogger/cli.py $args"
& $BlogPython (Join-Path $BlogRoot 'tools/blogger/cli.py') @args
exit $LASTEXITCODE
