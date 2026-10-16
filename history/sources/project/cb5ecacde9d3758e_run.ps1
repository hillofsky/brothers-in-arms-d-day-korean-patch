$ErrorActionPreference="Stop"
[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false)
$env:PYTHONUTF8="1";$env:PYTHONIOENCODING="utf-8"
$Root="PROJECT_ROOT";$LogRoot="PROJECT_ROOT\log";$Attempt="STEP_058"
$LogDir=Join-Path $LogRoot $Attempt;$OutDir=Join-Path $LogDir "outputs";$ScriptsUsed=Join-Path $LogDir "scripts_used"
$SuccessZip=Join-Path $LogRoot "bia_STEP_058_D09_0800_translation_RESULT.zip";$FailureZip=Join-Path $LogRoot "fall_bia_STEP_058_D09_0800_translation_RESULT.zip"
$Failed=$false;$LastSuccessfulAction="PowerShell startup";$PythonExit=$null
if(Test-Path $LogDir){$stamp=Get-Date -Format "yyyyMMdd_HHmmss";$archive=Join-Path $LogRoot "old\$stamp";New-Item -ItemType Directory -Force -Path $archive|Out-Null;Move-Item $LogDir (Join-Path $archive $Attempt)}
New-Item -ItemType Directory -Force -Path $LogRoot,$LogDir,$OutDir,$ScriptsUsed,(Join-Path $LogRoot "steps")|Out-Null
Copy-Item $PSCommandPath (Join-Path $ScriptsUsed "run.ps1") -Force
Copy-Item (Join-Path $PSScriptRoot "STEP_INFO.txt") $LogDir -Force
Copy-Item (Join-Path $PSScriptRoot "translations_STEP058.json") $ScriptsUsed -Force
Copy-Item (Join-Path $PSScriptRoot "translation_review_report.json") $OutDir -Force
Copy-Item (Join-Path $PSScriptRoot "D09_0800_BAUPTE_KO_reviewed.tsv") $OutDir -Force
Copy-Item (Join-Path $PSScriptRoot "scripts\apply_and_export_next.py") $ScriptsUsed -Force
Copy-Item (Join-Path $PSScriptRoot "scripts\update_state.py") $ScriptsUsed -Force
try{Start-Transcript -LiteralPath (Join-Path $LogDir "run.log") -Force|Out-Null}catch{}
function FindPython{$p="LOCAL_PATH";if(Test-Path $p){return $p};$c=Get-Command python.exe -ErrorAction SilentlyContinue;if($c){return $c.Source};throw "Python runtime not found"}
function State([string]$Phase,[string]$Detail){$old=$ErrorActionPreference;$ErrorActionPreference="Continue";try{& $Py (Join-Path $PSScriptRoot "scripts\update_state.py") --root $Root --phase $Phase --detail $Detail;$ec=$LASTEXITCODE}finally{$ErrorActionPreference=$old};if($ec -ne 0){throw "update_state failed phase=$Phase exit=$ec"}}
function Failure([string]$Reason){@"
PROJECT: bia
STEP: STEP_058
TIME: $(Get-Date -Format o)
STATUS: FAILED
FAILURE_REASON:
$Reason
PYTHON_EXIT_CODE: $PythonExit
LAST_SUCCESSFUL_ACTION: $LastSuccessfulAction
NEXT_RECOMMENDED_ACTION:
Upload PROJECT_ROOT\log\fall_bia_STEP_058_D09_0800_translation_RESULT.zip.
"@|Set-Content (Join-Path $LogDir "FAILURE.txt") -Encoding UTF8}
try{
 $Py=FindPython;State "start" "STEP058_D09_0800_translation_started";$LastSuccessfulAction="STEP_058 marked IN_PROGRESS"
 foreach($p in @("PROJECT_ROOT\translation\text_master.tsv","PROJECT_ROOT\translation\campaign_next_translation.tsv")){if(!(Test-Path $p)){throw "Missing required input: $p"}}
 $old=$ErrorActionPreference;$ErrorActionPreference="Continue"
 try{& $Py (Join-Path $PSScriptRoot "scripts\apply_and_export_next.py") --root $Root --mapping (Join-Path $PSScriptRoot "translations_STEP058.json") --out $OutDir 1> (Join-Path $LogDir "stdout.txt") 2> (Join-Path $LogDir "stderr.txt");$PythonExit=$LASTEXITCODE}finally{$ErrorActionPreference=$old}
 if($null -eq $PythonExit){$PythonExit=0};if($PythonExit -ne 0){throw "apply_and_export_next.py failed ExitCode=$PythonExit"}
 $report=Get-Content (Join-Path $OutDir "step058_report.json") -Raw -Encoding UTF8|ConvertFrom-Json
 $LastSuccessfulAction="46 reviewed translations persisted and next batch exported";State "success" ("STEP058_46_TRANSLATED_next_"+$report.next_reference_group+"_units_"+$report.next_unit_count);$LastSuccessfulAction="STEP_058 translation metadata VERIFIED"
}catch{$Failed=$true;$reason=$_|Out-String;$reason|Set-Content (Join-Path $LogDir "stderr_powershell.txt") -Encoding UTF8;try{Failure $reason}catch{};try{State "failure" "STEP058_failed_no_ISO_change"}catch{}}
finally{
 try{Stop-Transcript|Out-Null}catch{}
 try{foreach($p in @("PROJECT_ROOT\PROJECT_STATE.md","PROJECT_ROOT\log\steps\STEP_058.md","PROJECT_ROOT\translation\text_master.tsv","PROJECT_ROOT\translation\campaign_next_translation.tsv")){if(Test-Path $p){Copy-Item $p $OutDir -Force}}}catch{($_|Out-String)|Set-Content (Join-Path $LogDir "collection_error.txt") -Encoding UTF8}
 $zip=if($Failed){$FailureZip}else{$SuccessZip}
 try{if(Test-Path $zip){Remove-Item $zip -Force};Compress-Archive -Path (Join-Path $LogDir "*") -DestinationPath $zip -Force;if(!(Test-Path $zip)){throw "RESULT ZIP missing"};if((Get-Item $zip).Length -eq 0){throw "RESULT ZIP empty"}}catch{@"
STEP=STEP_058
WORK_FAILED=$Failed
ZIP_TARGET=$zip
ZIP_ERROR=$($_|Out-String)
LOG_FOLDER=$LogDir
"@|Set-Content (Join-Path $LogRoot "fall_STEP_058_ZIP_CREATION_FAILED.txt") -Encoding UTF8}
 Write-Host "";if($Failed){Write-Host "STEP_058 FAILED" -ForegroundColor Red;Write-Host "Upload: $FailureZip"}else{Write-Host "STEP_058 VERIFIED (translation data only; ISO untouched)" -ForegroundColor Green;Write-Host "Upload: $SuccessZip"}
}
if($Failed){exit 1}
