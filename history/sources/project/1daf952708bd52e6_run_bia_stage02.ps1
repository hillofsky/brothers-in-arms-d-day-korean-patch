param(
    [string]$Root = "PROJECT_ROOT"
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Py = Join-Path $ScriptDir "bia_stage02_collect.py"

Write-Host "=============================================================================="
Write-Host " Brothers in Arms: D-Day PSP - Stage 02 localization/font collection"
Write-Host "=============================================================================="
Write-Host "Root: $Root"
Write-Host ""

$Python = Get-Command python -ErrorAction SilentlyContinue
if (-not $Python) {
    $Python = Get-Command py -ErrorAction SilentlyContinue
}
if (-not $Python) {
    throw "Python was not found in PATH."
}

& $Python.Source $Py --root $Root
if ($LASTEXITCODE -ne 0) {
    throw "Stage 02 failed with exit code $LASTEXITCODE"
}
