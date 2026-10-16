$ErrorActionPreference="Stop"
$Root="PROJECT_ROOT"
$Partial=Join-Path $Root "BIA_STAGE40H_LOCALIZE_ENCODING_TEST.iso"

if(Test-Path $Partial){
    Remove-Item $Partial -Force
}

$ScriptDir=Split-Path -Parent $MyInvocation.MyCommand.Path
$Py=Join-Path $ScriptDir "bia_stage40h_localize_encoding.py"

$Python=Get-Command python -ErrorAction SilentlyContinue
if(-not $Python){$Python=Get-Command py -ErrorAction SilentlyContinue}
if(-not $Python){throw "Python was not found in PATH."}

& $Python.Source $Py
if($LASTEXITCODE -ne 0){throw "Stage 40H failed with exit code $LASTEXITCODE"}
