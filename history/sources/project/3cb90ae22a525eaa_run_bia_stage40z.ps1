$ErrorActionPreference="Stop"

$ScriptDir=Split-Path -Parent $MyInvocation.MyCommand.Path
$Py=Join-Path $ScriptDir "bia_stage40z_pause_input_trace.py"

$Python=Get-Command python -ErrorAction SilentlyContinue
if(-not $Python){$Python=Get-Command py -ErrorAction SilentlyContinue}
if(-not $Python){throw "Python was not found in PATH."}

& $Python.Source $Py

if($LASTEXITCODE -ne 0){
    throw "Stage40Z failed with exit code $LASTEXITCODE"
}
