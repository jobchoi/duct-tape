# Compatibility entry point: use the maintained installer and its safety checks.
param([Parameter(Mandatory=$true)][string]$StateFile)
& (Join-Path $PSScriptRoot '06_InstallHancom.ps1') -StateFile $StateFile
exit $LASTEXITCODE
