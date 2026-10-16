$ErrorActionPreference="Stop"
$ScriptDir=Split-Path -Parent $MyInvocation.MyCommand.Path
$Py=Join-Path $ScriptDir "bia_stage37_corpus_inventory.py"

$Python=Get-Command python -ErrorAction SilentlyContinue
if(-not $Python){$Python=Get-Command py -ErrorAction SilentlyContinue}
if(-not $Python){throw "Python was not found in PATH."}

& $Python.Source $Py
if($LASTEXITCODE -ne 0){throw "Stage 37 failed with exit code $LASTEXITCODE"}
