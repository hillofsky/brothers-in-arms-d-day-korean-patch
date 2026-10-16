$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

$ProjectRoot="PROJECT_ROOT"
$LegacyRoot="LOCAL_PATH"
$LogsRoot="PROJECT_ROOT\log"
$Attempt="STEP_044_FIX5"
$StepLogDir=Join-Path $LogsRoot $Attempt
$OutputsDir=Join-Path $StepLogDir "outputs"
$ScriptsUsed=Join-Path $StepLogDir "scripts_used"
$SuccessZip=Join-Path $LogsRoot "bia_STEP_044_campaign_next_batch_RESULT.zip"
$FailureZip=Join-Path $LogsRoot "fall_bia_STEP_044_campaign_next_batch_RESULT.zip"
$ExpectedTsv="PROJECT_ROOT\translation\campaign_next_translation.tsv"
$Failed=$false
$LastSuccessfulAction="PowerShell startup"
$PythonExitCode=$null

# Never mix retry logs. Archive an existing FIX5 attempt first.
if(Test-Path $StepLogDir){
    $stamp=Get-Date -Format "yyyyMMdd_HHmmss"
    $old=Join-Path $LogsRoot "old\$stamp"
    New-Item -ItemType Directory -Force -Path $old | Out-Null
    Move-Item -LiteralPath $StepLogDir -Destination (Join-Path $old $Attempt)
}
New-Item -ItemType Directory -Force -Path $StepLogDir,$OutputsDir,$ScriptsUsed,(Join-Path $LogsRoot "steps") | Out-Null

Copy-Item -LiteralPath $PSCommandPath -Destination (Join-Path $ScriptsUsed "run.ps1") -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot "STEP_INFO.txt") -Destination $StepLogDir -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot "scripts\discover_campaign_fix5.py") -Destination $ScriptsUsed -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot "scripts\update_state.py") -Destination $ScriptsUsed -Force

try{Start-Transcript -LiteralPath (Join-Path $StepLogDir "run.log") -Force|Out-Null}catch{}

function Find-Python{
 $p="LOCAL_PATH"
 if(Test-Path $p){return $p}
 $c=Get-Command python.exe -ErrorAction SilentlyContinue
 if($c){return $c.Source}
 throw "Python runtime not found"
}
function Invoke-Python{
 param([string]$Script,[string[]]$Args,[string]$OutFile,[string]$ErrFile)
 & $Python $Script @Args 1> $OutFile 2> $ErrFile
 $ec=$LASTEXITCODE
 if($null -eq $ec){$ec=0}
 return [int]$ec
}
function Update-State([string]$Phase,[string]$Detail){
 # Keep detail ASCII-only to avoid Windows PowerShell 5 code-page surprises.
 & $Python (Join-Path $PSScriptRoot "scripts\update_state.py") `
   --root $ProjectRoot --phase $Phase --detail $Detail `
   1> (Join-Path $StepLogDir "state_${Phase}_stdout.txt") `
   2> (Join-Path $StepLogDir "state_${Phase}_stderr.txt")
 if($LASTEXITCODE -ne 0){throw "update_state.py failed phase=$Phase ExitCode=$LASTEXITCODE"}
}
function Failure-File([string]$Reason){
@"
PROJECT: bia
STEP: STEP_044
RETRY: FIX5
TIME: $(Get-Date -Format o)
STATUS: FAILED
FAILURE_REASON:
$Reason
PYTHON_EXIT_CODE: $PythonExitCode
LAST_SUCCESSFUL_ACTION: $LastSuccessfulAction
EXPECTED_OUTPUT: $ExpectedTsv
PARTIAL_OUTPUTS: $OutputsDir
NEXT_RECOMMENDED_ACTION:
Upload PROJECT_ROOT\log\fall_bia_STEP_044_campaign_next_batch_RESULT.zip.
"@|Set-Content -LiteralPath (Join-Path $StepLogDir "FAILURE.txt") -Encoding UTF8
}

try{
 $Python=Find-Python
 Update-State "start" "FIX5_start_full_campaign_discovery_ISO_untouched"
 $LastSuccessfulAction="State marked IN_PROGRESS"

 $BaseIso="PROJECT_ROOT\BIA_STAGE43T_TITLE_PROMPT_FIX.iso"
 if(!(Test-Path $BaseIso)){throw "Missing baseline ISO: $BaseIso"}
 $h=Get-FileHash -Algorithm SHA256 -LiteralPath $BaseIso
 "$($h.Hash)`t$BaseIso"|Set-Content -LiteralPath (Join-Path $StepLogDir "hashes.txt") -Encoding UTF8
 @"
TIME=$(Get-Date -Format o)
PROJECT_ROOT=$ProjectRoot
LEGACY_ROOT=$LegacyRoot
BASE_ISO=$BaseIso
PYTHON=$Python
"@|Set-Content -LiteralPath (Join-Path $StepLogDir "environment.txt") -Encoding UTF8
 $LastSuccessfulAction="Baseline validated"

 $PythonExitCode=Invoke-Python `
   -Script (Join-Path $PSScriptRoot "scripts\discover_campaign_fix5.py") `
   -Args @("--project-root",$ProjectRoot,"--legacy-root",$LegacyRoot,"--out-dir",$OutputsDir) `
   -OutFile (Join-Path $StepLogDir "stdout.txt") `
   -ErrFile (Join-Path $StepLogDir "stderr.txt")
 if($PythonExitCode -ne 0){
   throw "Campaign discovery failed ExitCode=$PythonExitCode. Inspect candidate_inventory.json and source_evidence in result ZIP."
 }
 $LastSuccessfulAction="Next campaign translation TSV generated"

 if(!(Test-Path $ExpectedTsv)){throw "Expected TSV missing: $ExpectedTsv"}
 if((Get-Item $ExpectedTsv).Length -eq 0){throw "Expected TSV is empty"}

 $rp=Join-Path $OutputsDir "campaign_discovery_report.json"
 if(!(Test-Path $rp)){throw "Missing campaign_discovery_report.json"}
 $r=Get-Content -LiteralPath $rp -Raw -Encoding UTF8|ConvertFrom-Json
 Update-State "success" ("FIX5_selected_"+$r.selected_source_file+"_units_"+$r.selected_unit_count)
 $LastSuccessfulAction="STEP_044 discovery/export VERIFIED"
}catch{
 $Failed=$true
 $reason=$_|Out-String
 $reason|Set-Content -LiteralPath (Join-Path $StepLogDir "stderr_powershell.txt") -Encoding UTF8
 try{Failure-File $reason}catch{}
 try{Update-State "failure" "FIX5_failed_discovery_evidence_collected"}catch{}
}finally{
 try{Stop-Transcript|Out-Null}catch{}
 try{
   if(Test-Path "PROJECT_ROOT\PROJECT_STATE.md"){Copy-Item "PROJECT_ROOT\PROJECT_STATE.md" $StepLogDir -Force}
   if(Test-Path "PROJECT_ROOT\log\steps\STEP_044.md"){Copy-Item "PROJECT_ROOT\log\steps\STEP_044.md" $StepLogDir -Force}
   if(Test-Path $ExpectedTsv){Copy-Item $ExpectedTsv $OutputsDir -Force}
   if(Test-Path "PROJECT_ROOT\translation\text_master.tsv"){Copy-Item "PROJECT_ROOT\translation\text_master.tsv" $OutputsDir -Force}
 }catch{
   ($_|Out-String)|Set-Content -LiteralPath (Join-Path $StepLogDir "collection_error.txt") -Encoding UTF8
 }
 $zip=if($Failed){$FailureZip}else{$SuccessZip}
 try{
   if(Test-Path $zip){Remove-Item $zip -Force}
   Compress-Archive -Path (Join-Path $StepLogDir "*") -DestinationPath $zip -Force
   if(!(Test-Path $zip)){throw "Result ZIP missing"}
 }catch{
   @"
STEP=STEP_044_FIX5
ZIP_ERROR=$($_|Out-String)
LOG_FOLDER=$StepLogDir
"@|Set-Content -LiteralPath (Join-Path $LogsRoot "fall_STEP_044_FIX5_ZIP_CREATION_FAILED.txt") -Encoding UTF8
 }
 Write-Host ""
 if($Failed){
   Write-Host "STEP_044 FIX5 FAILED" -ForegroundColor Red
   Write-Host "Upload: $FailureZip"
 }else{
   Write-Host "STEP_044 VERIFIED (discovery/export only)" -ForegroundColor Green
   Write-Host "TSV: $ExpectedTsv"
   Write-Host "Upload: $SuccessZip"
 }
}
if($Failed){exit 1}
