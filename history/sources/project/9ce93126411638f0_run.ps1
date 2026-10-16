$ErrorActionPreference="Stop"
[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false)
$env:PYTHONUTF8="1";$env:PYTHONIOENCODING="utf-8"

$Root="PROJECT_ROOT";$LogRoot="PROJECT_ROOT\log";$Attempt="STEP_062"
$LogDir=Join-Path $LogRoot $Attempt;$OutDir=Join-Path $LogDir "outputs";$ScriptsUsed=Join-Path $LogDir "scripts_used"
$SuccessZip=Join-Path $LogRoot "bia_STEP_062_campaign_translation_complete_RESULT.zip"
$FailureZip=Join-Path $LogRoot "fall_bia_STEP_062_campaign_translation_complete_RESULT.zip"
$Failed=$false;$LastSuccessfulAction="PowerShell startup";$PythonExit=$null

if(Test-Path $LogDir){
 $stamp=Get-Date -Format "yyyyMMdd_HHmmss";$archive=Join-Path $LogRoot "old\$stamp"
 New-Item -ItemType Directory -Force -Path $archive|Out-Null
 Move-Item $LogDir (Join-Path $archive $Attempt)
}
New-Item -ItemType Directory -Force -Path $LogRoot,$LogDir,$OutDir,$ScriptsUsed,(Join-Path $LogRoot "steps")|Out-Null

Copy-Item $PSCommandPath (Join-Path $ScriptsUsed "run.ps1") -Force
Copy-Item (Join-Path $PSScriptRoot "STEP_INFO.txt") $LogDir -Force
Copy-Item (Join-Path $PSScriptRoot "translations_STEP062.json") $ScriptsUsed -Force
Copy-Item (Join-Path $PSScriptRoot "translation_review_report.json") $OutDir -Force
Copy-Item (Join-Path $PSScriptRoot "CAMPAIGN_FINAL_162_SKIRMISH_SYSTEM_KO_reviewed.tsv") $OutDir -Force
Copy-Item (Join-Path $PSScriptRoot "scripts\apply_and_finish_translation.py") $ScriptsUsed -Force
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
STEP: STEP_062
TIME: $(Get-Date -Format o)
STATUS: FAILED
FAILURE_REASON:
$Reason
PYTHON_EXIT_CODE: $PythonExit
LAST_SUCCESSFUL_ACTION: $LastSuccessfulAction
NEXT_RECOMMENDED_ACTION:
Upload PROJECT_ROOT\log\fall_bia_STEP_062_campaign_translation_complete_RESULT.zip.
"@|Set-Content (Join-Path $LogDir "FAILURE.txt") -Encoding UTF8
}

try{
 $Py=FindPython
 State "start" "STEP062_final_162_campaign_translation_started"
 $LastSuccessfulAction="STEP_062 marked IN_PROGRESS"

 foreach($p in @("PROJECT_ROOT\translation\text_master.tsv","PROJECT_ROOT\translation\campaign_next_translation.tsv")){
  if(!(Test-Path $p)){throw "Missing required input: $p"}
 }

 $old=$ErrorActionPreference;$ErrorActionPreference="Continue"
 try{
  & $Py (Join-Path $PSScriptRoot "scripts\apply_and_finish_translation.py") `
    --root $Root `
    --mapping (Join-Path $PSScriptRoot "translations_STEP062.json") `
    --out $OutDir `
    1> (Join-Path $LogDir "stdout.txt") `
    2> (Join-Path $LogDir "stderr.txt")
  $PythonExit=$LASTEXITCODE
 }finally{$ErrorActionPreference=$old}

 if($null -eq $PythonExit){$PythonExit=0}
 if($PythonExit -ne 0){throw "apply_and_finish_translation.py failed ExitCode=$PythonExit"}

 $report=Get-Content (Join-Path $OutDir "step062_report.json") -Raw -Encoding UTF8|ConvertFrom-Json
 $LastSuccessfulAction="162 final campaign translations persisted; NEEDS_TRANSLATION=0"
 State "success" ("STEP062_CAMPAIGN_TRANSLATION_COMPLETE_unapplied_"+$report.unapplied_campaign_units_ready_for_iso)
 $LastSuccessfulAction="STEP_062 translation metadata VERIFIED"
}catch{
 $Failed=$true;$reason=$_|Out-String
 $reason|Set-Content (Join-Path $LogDir "stderr_powershell.txt") -Encoding UTF8
 try{Failure $reason}catch{}
 try{State "failure" "STEP062_failed_no_ISO_change"}catch{}
}finally{
 try{Stop-Transcript|Out-Null}catch{}
 try{
  foreach($p in @(
   "PROJECT_ROOT\PROJECT_STATE.md",
   "PROJECT_ROOT\log\steps\STEP_062.md",
   "PROJECT_ROOT\translation\text_master.tsv",
   "PROJECT_ROOT\translation\campaign_next_translation.tsv"
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
STEP=STEP_062
WORK_FAILED=$Failed
ZIP_TARGET=$zip
ZIP_ERROR=$($_|Out-String)
LOG_FOLDER=$LogDir
"@|Set-Content (Join-Path $LogRoot "fall_STEP_062_ZIP_CREATION_FAILED.txt") -Encoding UTF8
 }

 Write-Host ""
 if($Failed){
  Write-Host "STEP_062 FAILED" -ForegroundColor Red
  Write-Host "Upload: $FailureZip"
 }else{
  Write-Host "STEP_062 VERIFIED - CAMPAIGN TRANSLATION CORPUS COMPLETE" -ForegroundColor Green
  Write-Host "Upload: $SuccessZip"
 }
}
if($Failed){exit 1}
