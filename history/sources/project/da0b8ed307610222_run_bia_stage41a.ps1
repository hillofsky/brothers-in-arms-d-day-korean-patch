$ErrorActionPreference="Stop"

$Root="PROJECT_ROOT"
$OutIso=Join-Path $Root "BIA_STAGE41A_FIRST_MOVIE_KO_SUB_TEST.iso"

if(Test-Path $OutIso){
    Remove-Item $OutIso -Force
}

$ScriptDir=Split-Path -Parent $MyInvocation.MyCommand.Path
$Py=Join-Path $ScriptDir "bia_stage41a_first_movie_subtitle.py"

$Python=Get-Command python -ErrorAction SilentlyContinue
if(-not $Python){$Python=Get-Command py -ErrorAction SilentlyContinue}
if(-not $Python){throw "Python was not found in PATH."}

& $Python.Source $Py

if($LASTEXITCODE -ne 0){
    throw "Stage41A failed with exit code $LASTEXITCODE"
}
