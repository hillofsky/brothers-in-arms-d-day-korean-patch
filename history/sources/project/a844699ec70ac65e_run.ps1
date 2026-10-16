$ErrorActionPreference="Stop"
[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false)
$env:PYTHONUTF8="1";$env:PYTHONIOENCODING="utf-8"

$Root="PROJECT_ROOT";$LogRoot="PROJECT_ROOT\log";$Attempt="STEP_069_FIX1"
$LogDir=Join-Path $LogRoot $Attempt;$OutDir=Join-Path $LogDir "outputs";$ScriptsUsed=Join-Path $LogDir "scripts_used"
$SuccessZip=Join-Path $LogRoot "bia_STEP_069_FIX1_nonmdi_int92_build_RESULT.zip"
$FailureZip=Join-Path $LogRoot "fall_bia_STEP_069_FIX1_nonmdi_int92_build_RESULT.zip"
$Failed=$false;$LastSuccessfulAction="PowerShell startup";$PythonExit=$null

if(Test-Path $LogDir){
 $stamp=Get-Date -Format "yyyyMMdd_HHmmss";$archive=Join-Path $LogRoot "old\$stamp"
 New-Item -ItemType Directory -Force -Path $archive|Out-Null
 Move-Item $LogDir (Join-Path $archive $Attempt)
}
New-Item -ItemType Directory -Force -Path $LogRoot,$LogDir,$OutDir,$ScriptsUsed,(Join-Path $LogRoot "steps")|Out-Null
Copy-Item $PSCommandPath (Join-Path $ScriptsUsed "run.ps1") -Force
Copy-Item (Join-Path $PSScriptRoot "STEP_INFO.txt") $LogDir -Force
Copy-Item (Join-Path $PSScriptRoot "FIX1_DIAGNOSIS.txt") $LogDir -Force
Copy-Item (Join-Path $PSScriptRoot "INT92_APPLY_MANIFEST.tsv") $OutDir -Force
Copy-Item (Join-Path $PSScriptRoot "int92_manifest.json") $ScriptsUsed -Force
Copy-Item (Join-Path $PSScriptRoot "scripts\build_int92_test_iso_fix1.py") $ScriptsUsed -Force
Copy-Item (Join-Path $PSScriptRoot "scripts\update_state.py") $ScriptsUsed -Force
try{Start-Transcript -LiteralPath (Join-Path $LogDir "run.log") -Force|Out-Null}catch{}

function FindPython{
 $p="LOCAL_PATH"
 if(Test-Path $p){return $p}
 $c=Get-Command python.exe -ErrorAction SilentlyContinue
 if($c){return $c.Source}
 throw "Python runtime not found"
}
function State([string]$Phase,[string]$Detail){
 $old=$ErrorActionPreference;$ErrorActionPreference="Continue"
 try{
  & $Py (Join-Path $PSScriptRoot "scripts\update_state.py") --root $Root --phase $Phase --detail $Detail
  $ec=$LASTEXITCODE
 }finally{$ErrorActionPreference=$old}
 if($ec -ne 0){throw "update_state failed phase=$Phase exit=$ec"}
}
function Failure([string]$Reason){
@"
PROJECT: bia
STEP: STEP_069_FIX1
TIME: $(Get-Date -Format o)
STATUS: FAILED
FAILURE_REASON:
$Reason
PYTHON_EXIT_CODE: $PythonExit
LAST_SUCCESSFUL_ACTION: $LastSuccessfulAction
NEXT_RECOMMENDED_ACTION:
Upload PROJECT_ROOT\log\fall_bia_STEP_069_FIX1_nonmdi_int92_build_RESULT.zip.
"@|Set-Content (Join-Path $LogDir "FAILURE.txt") -Encoding UTF8
}

try{
 $Py=FindPython
 State "start" "STEP069_FIX1_nonmdi_INT92_build_started"
 $LastSuccessfulAction="STEP_069 FIX1 marked IN_PROGRESS"

 $old=$ErrorActionPreference;$ErrorActionPreference="Continue"
 try{
  & $Py (Join-Path $PSScriptRoot "scripts\build_int92_test_iso_fix1.py") `
    --root $Root `
    --manifest (Join-Path $PSScriptRoot "int92_manifest.json") `
    --outdir $OutDir `
    1> (Join-Path $LogDir "stdout.txt") `
    2> (Join-Path $LogDir "stderr.txt")
  $PythonExit=$LASTEXITCODE
 }finally{$ErrorActionPreference=$old}
 if($null -eq $PythonExit){$PythonExit=0}
 if($PythonExit -ne 0){throw "build_int92_test_iso_fix1.py failed ExitCode=$PythonExit"}

 $report=Get-Content (Join-Path $OutDir "step069_fix1_report.json") -Raw -Encoding UTF8|ConvertFrom-Json
 if(!(Test-Path "PROJECT_ROOT\BIA_STAGE69_FIX1_NONMDI_INT92_TEST.iso")){throw "Output ISO missing"}
 $LastSuccessfulAction="INT92 FIX1 test ISO built and static readback verified"
 State "built" ("STEP069_FIX1_BUILT_UNVERIFIED_changed_"+$report.occurrences_changed+"_drifted_"+$report.occurrences_drifted_from_stage38)
 $LastSuccessfulAction="STEP_069 FIX1 BUILT_UNVERIFIED"
}catch{
 $Failed=$true;$reason=$_|Out-String
 $reason|Set-Content (Join-Path $LogDir "stderr_powershell.txt") -Encoding UTF8
 try{Failure $reason}catch{}
 try{State "failure" "STEP069_FIX1_failed_source_Stage43T_preserved"}catch{}
}finally{
 try{Stop-Transcript|Out-Null}catch{}
 try{
  foreach($p in @(
   "PROJECT_ROOT\PROJECT_STATE.md",
   "PROJECT_ROOT\log\steps\STEP_069_FIX1.md",
   "PROJECT_ROOT\translation\text_master.tsv"
  )){
   if(Test-Path $p){Copy-Item $p $OutDir -Force}
  }
 }catch{($_|Out-String)|Set-Content (Join-Path $LogDir "collection_error.txt") -Encoding UTF8}

 $zip=if($Failed){$FailureZip}else{$SuccessZip}
 try{
  if(Test-Path $zip){Remove-Item $zip -Force}
  Compress-Archive -Path (Join-Path $LogDir "*") -DestinationPath $zip -Force
  if(!(Test-Path $zip)){throw "RESULT ZIP missing"}
  if((Get-Item $zip).Length -eq 0){throw "RESULT ZIP empty"}
 }catch{
@"
STEP=STEP_069_FIX1
WORK_FAILED=$Failed
ZIP_TARGET=$zip
ZIP_ERROR=$($_|Out-String)
LOG_FOLDER=$LogDir
"@|Set-Content (Join-Path $LogRoot "fall_STEP_069_FIX1_ZIP_CREATION_FAILED.txt") -Encoding UTF8
 }

 Write-Host ""
 if($Failed){
  Write-Host "STEP_069 FIX1 FAILED" -ForegroundColor Red
  Write-Host "Upload: $FailureZip"
 }else{
  Write-Host "STEP_069 FIX1 BUILT_UNVERIFIED - INT92 TEST ISO READY" -ForegroundColor Yellow
  Write-Host "ISO: PROJECT_ROOT\BIA_STAGE69_FIX1_NONMDI_INT92_TEST.iso"
  Write-Host "Upload: $SuccessZip"
 }
}
if($Failed){exit 1}
