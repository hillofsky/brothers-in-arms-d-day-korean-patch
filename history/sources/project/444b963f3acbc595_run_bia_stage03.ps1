param([string]$Root = "PROJECT_ROOT")
$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Py = Join-Path $ScriptDir "bia_stage03_font_assets.py"

$Python = Get-Command python -ErrorAction SilentlyContinue
if (-not $Python) { $Python = Get-Command py -ErrorAction SilentlyContinue }
if (-not $Python) { throw "Python was not found in PATH." }

& $Python.Source $Py --root $Root
if ($LASTEXITCODE -ne 0) { throw "Stage 03 failed with exit code $LASTEXITCODE" }
