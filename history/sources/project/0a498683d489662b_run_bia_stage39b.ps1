$ErrorActionPreference="Stop"
$ScriptDir=Split-Path -Parent $MyInvocation.MyCommand.Path
$Py=Join-Path $ScriptDir "bia_stage39b_compiled_mdi_text.py"

$Python=Get-Command python -ErrorAction SilentlyContinue
if(-not $Python){$Python=Get-Command py -ErrorAction SilentlyContinue}
if(-not $Python){throw "Python was not found in PATH."}

& $Python.Source $Py
if($LASTEXITCODE -ne 0){throw "Stage 39B failed with exit code $LASTEXITCODE"}
