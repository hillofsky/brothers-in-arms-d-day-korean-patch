param([string]$Root = "PROJECT_ROOT")
$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Py = Join-Path $ScriptDir "bia_stage04_mdi_unicode_test.py"

$Python = Get-Command python -ErrorAction SilentlyContinue
if (-not $Python) { $Python = Get-Command py -ErrorAction SilentlyContinue }
if (-not $Python) { throw "Python was not found in PATH." }

& $Python.Source $Py --root $Root
if ($LASTEXITCODE -ne 0) { throw "Stage 04 failed with exit code $LASTEXITCODE" }
