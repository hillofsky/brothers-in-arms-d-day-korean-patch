$ErrorActionPreference="Stop"
$ScriptDir=Split-Path -Parent $MyInvocation.MyCommand.Path
$Py=Join-Path $ScriptDir "bia_stage07_preload_fontmap.py"
$Python=Get-Command python -ErrorAction SilentlyContinue
if(-not $Python){$Python=Get-Command py -ErrorAction SilentlyContinue}
if(-not $Python){throw "Python was not found in PATH."}
& $Python.Source $Py --root "PROJECT_ROOT"
if($LASTEXITCODE -ne 0){throw "Stage 07 failed with exit code $LASTEXITCODE"}
