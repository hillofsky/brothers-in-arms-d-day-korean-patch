$ErrorActionPreference="Stop"
$Root="PROJECT_ROOT"
$Partial=Join-Path $Root "BIA_STAGE40F_ON_MEMU_RESIDENT_MASS_TEST.iso"

# Previous Stage40F failed before appending the patched MDI, so its output ISO
# can only be a disposable copy of the Stage39U baseline. Remove it first.
if(Test-Path $Partial){
    Remove-Item $Partial -Force
}

$ScriptDir=Split-Path -Parent $MyInvocation.MyCommand.Path
$Py=Join-Path $ScriptDir "bia_stage40f_on_memu_resident_mass.py"

$Python=Get-Command python -ErrorAction SilentlyContinue
if(-not $Python){$Python=Get-Command py -ErrorAction SilentlyContinue}
if(-not $Python){throw "Python was not found in PATH."}

& $Python.Source $Py
if($LASTEXITCODE -ne 0){throw "Stage 40F retry failed with exit code $LASTEXITCODE"}
