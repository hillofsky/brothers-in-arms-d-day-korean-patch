$ErrorActionPreference="Stop"
[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false)
$env:PYTHONUTF8="1";$env:PYTHONIOENCODING="utf-8"

$Root="PROJECT_ROOT";$LogRoot="PROJECT_ROOT\log";$Attempt="STEP_066"
$LogDir=Join-Path $LogRoot $Attempt;$OutDir=Join-Path $LogDir "outputs";$ScriptsUsed=Join-Path $LogDir "scripts_used"
$SuccessZip=Join-Path $LogRoot "bia_STEP_066_allstream_fstring_audit_RESULT.zip"
$FailureZip=Join-Path $LogRoot "fall_bia_STEP_066_allstream_fstring_audit_RESULT.zip"
$Failed=$false;$LastSuccessfulAction="PowerShell startup";$PythonExit=$null

if(Test-Path $LogDir){
 $stamp=Get-Date -Format "yyyyMMdd_HHmmss";$archive=Join-Path $LogRoot "old\$stamp"
 New-Item -ItemType Directory -Force -Path $archive|Out-Null
 Move-Item $LogDir (Join-Path $archive $Attempt)
}
New-Item -ItemType Directory -Force -Path $LogRoot,$LogDir,$OutDir,$ScriptsUsed,(Join-Path $LogRoot "steps")|Out-Null
Copy-Item $PSCommandPath (Join-Path $ScriptsUsed "run.ps1") -Force
Copy-Item (Join-Path $PSScriptRoot "STEP_INFO.txt") $LogDir -Force
Copy-Item (Join-Path $PSScriptRoot "scripts\allstream_reverse_fstring_audit.py") $ScriptsUsed -Force
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
STEP: STEP_066
TIME: $(Get-Date -Format o)
STATUS: FAILED
FAILURE_REASON:
$Reason
PYTHON_EXIT_CODE: $PythonExit
LAST_SUCCESSFUL_ACTION: $LastSuccessfulAction
NEXT_RECOMMENDED_ACTION:
Upload PROJECT_ROOT\log\fall_bia_STEP_066_allstream_fstring_audit_RESULT.zip.
"@|Set-Content (Join-Path $LogDir "FAILURE.txt") -Encoding UTF8
}

try{
 $Py=FindPython
 State "start" "STEP066_allstream_reverse_fstring_audit_started"
 $LastSuccessfulAction="STEP_066 marked IN_PROGRESS"

 $old=$ErrorActionPreference;$ErrorActionPreference="Continue"
 try{
  & $Py (Join-Path $PSScriptRoot "scripts\allstream_reverse_fstring_audit.py") $OutDir `
    1> (Join-Path $LogDir "stdout.txt") `
    2> (Join-Path $LogDir "stderr.txt")
  $PythonExit=$LASTEXITCODE
 }finally{$ErrorActionPreference=$old}

 if($null -eq $PythonExit){$PythonExit=0}
 if($PythonExit -ne 0){throw "allstream_reverse_fstring_audit.py failed ExitCode=$PythonExit"}

 $report=Get-Content (Join-Path $OutDir "step066_report.json") -Raw -Encoding UTF8|ConvertFrom-Json
 $canary=$report.d0_0700_canary.pass
 $LastSuccessfulAction="All-stream reverse FString/font audit completed"
 State "success" ("STEP066_AUDIT_VERIFIED_highIDs_"+$report.ids_with_high_confidence_ref+"_allIDs_"+$report.ids_with_any_structural_ref+"_D00700_canary_"+$canary)
 $LastSuccessfulAction="STEP_066 audit VERIFIED"
}catch{
 $Failed=$true;$reason=$_|Out-String
 $reason|Set-Content (Join-Path $LogDir "stderr_powershell.txt") -Encoding UTF8
 try{Failure $reason}catch{}
 try{State "failure" "STEP066_audit_failed_no_ISO_change"}catch{}
}finally{
 try{Stop-Transcript|Out-Null}catch{}
 try{
  foreach($p in @(
   "PROJECT_ROOT\PROJECT_STATE.md",
   "PROJECT_ROOT\log\steps\STEP_066.md",
   "PROJECT_ROOT\translation\text_master.tsv"
  )){
   if(Test-Path $p){Copy-Item $p $OutDir -Force}
  }
 }catch{
  ($_|Out-String)|Set-Content (Join-Path $LogDir "collection_error.txt") -Encoding UTF8
 }

 $zip=if($Failed){$FailureZip}else{$SuccessZip}
 try{
  if(Test-Path $zip){Remove-Item $zip -Force}
  Compress-Archive -Path (Join-Path $LogDir "*") -DestinationPath $zip -Force
  if(!(Test-Path $zip)){throw "RESULT ZIP missing"}
  if((Get-Item $zip).Length -eq 0){throw "RESULT ZIP empty"}
 }catch{
@"
STEP=STEP_066
WORK_FAILED=$Failed
ZIP_TARGET=$zip
ZIP_ERROR=$($_|Out-String)
LOG_FOLDER=$LogDir
"@|Set-Content (Join-Path $LogRoot "fall_STEP_066_ZIP_CREATION_FAILED.txt") -Encoding UTF8
 }

 Write-Host ""
 if($Failed){
  Write-Host "STEP_066 FAILED" -ForegroundColor Red
  Write-Host "Upload: $FailureZip"
 }else{
  Write-Host "STEP_066 VERIFIED - ALL-STREAM AUDIT COMPLETE" -ForegroundColor Green
  Write-Host "Upload: $SuccessZip"
 }
}
if($Failed){exit 1}
