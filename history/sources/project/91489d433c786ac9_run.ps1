$ErrorActionPreference='Stop'
[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false)
$env:PYTHONUTF8='1';$env:PYTHONIOENCODING='utf-8'
$Root='PROJECT_ROOT';$LogRoot=Join-Path $Root 'log';$Step='STEP_076'
$Dir=Join-Path $LogRoot $Step;$Out=Join-Path $Dir 'outputs';$Scr=Join-Path $Dir 'scripts_used'
$Success=Join-Path $LogRoot 'bia_STEP_076_targeted_dsl_binding_audit_RESULT.zip'
$Failure=Join-Path $LogRoot 'fall_bia_STEP_076_targeted_dsl_binding_audit_RESULT.zip'
$Python='LOCAL_PATH'
$Failed=$false;$Stage='startup'
if(Test-Path -LiteralPath $Dir){$stamp=Get-Date -Format 'yyyyMMdd_HHmmss';$old=Join-Path (Join-Path $LogRoot 'old') $stamp;New-Item -ItemType Directory -Force $old|Out-Null;Move-Item -LiteralPath $Dir -Destination (Join-Path $old $Step)}
New-Item -ItemType Directory -Force $LogRoot,$Dir,$Out,$Scr,(Join-Path $LogRoot 'steps')|Out-Null
Copy-Item $PSCommandPath (Join-Path $Scr 'run.ps1') -Force
Copy-Item (Join-Path $PSScriptRoot 'scripts\*') $Scr -Force
Copy-Item (Join-Path $PSScriptRoot 'evidence\*') $Scr -Force
Copy-Item (Join-Path $PSScriptRoot 'reference\*') $Scr -Force
Copy-Item (Join-Path $PSScriptRoot 'STEP_INFO.txt') $Dir -Force
try{Start-Transcript -LiteralPath (Join-Path $Dir 'run.log') -Force|Out-Null}catch{}
function State([string]$Phase,[string]$Detail){
 & $Python (Join-Path $PSScriptRoot 'scripts\update_state.py') --root $Root --phase $Phase --detail $Detail
 if($LASTEXITCODE -ne 0){throw "State update failed: $Phase"}
}
try{
 if(!(Test-Path $Python)){throw "Python missing: $Python"}
 foreach($p in @((Join-Path $Root 'Brothers in Arms - D-Day (USA) (v1.01).iso'),(Join-Path $Root 'BIA_STAGE69_FIX2_NONMDI_INT92_TEST.iso'))){if(!(Test-Path $p)){throw "ISO missing: $p"}}
 State start 'Reading original+Stage69 DSL variants and verified D0_0130_ reference only; no output ISO.'
 $Stage='run-targeted-audit'
 Write-Host '[1/3] Comparing verified first-mission DSL control...' -ForegroundColor Cyan
 Write-Host '[2/3] Ranking relocation-table groups + B8 GPU contexts across 32 DSL...' -ForegroundColor Cyan
 $oldEA=$ErrorActionPreference;$ErrorActionPreference='Continue'
 try{
  & $Python (Join-Path $PSScriptRoot 'scripts\audit_linked_dsl.py') --package-root $PSScriptRoot --outdir $Out 1> (Join-Path $Dir 'stdout.txt') 2> (Join-Path $Dir 'stderr.txt')
  $ec=$LASTEXITCODE
 }finally{$ErrorActionPreference=$oldEA}
 if($ec -ne 0){throw "Targeted audit failed: exit=$ec"}
 $report=Get-Content (Join-Path $Out 'step076_report.json') -Raw -Encoding UTF8 | ConvertFrom-Json
 if($report.status -ne 'VERIFIED_TARGETED_DSL_DIAGNOSTIC' -or $report.target_mdis -ne 32 -or !$report.source_iso_preserved){throw 'Report validation failed'}
 State success 'All 32 DSL analyzed; candidate offsets are hypotheses only; no ISO changed.'
 $Stage='verified-analysis'
 Write-Host '[3/3] Targeted DSL audit completed. NO ISO change.' -ForegroundColor Green
}catch{
 $Failed=$true;$reason=$_|Out-String
 $FailureText=@"
STEP=STEP_076
STATUS=FAILED
TIME=$(Get-Date -Format o)
STAGE=$Stage
REASON=$reason
ISO_MODIFIED=NO
"@
 $FailureText | Set-Content (Join-Path $Dir 'FAILURE.txt') -Encoding UTF8
 try{if(Test-Path $Python){State failure 'DSL linked audit failed; source ISO preserved.'}}catch{}
}finally{
 try{Stop-Transcript|Out-Null}catch{}
 foreach($p in @((Join-Path $Root 'PROJECT_STATE.md'),(Join-Path $LogRoot 'steps\STEP_076.md'))){if(Test-Path $p){Copy-Item $p $Out -Force -ErrorAction SilentlyContinue}}
 $zip=if($Failed){$Failure}else{$Success}
 try{
  if(Test-Path $zip){Remove-Item $zip -Force}
  Compress-Archive -Path (Join-Path $Dir '*') -DestinationPath $zip -Force
 }catch{($_|Out-String)|Set-Content (Join-Path $LogRoot 'fall_STEP_076_ZIP_CREATION_FAILED.txt') -Encoding UTF8}
 if($Failed){Write-Host "STEP_076 FAILED: $Failure" -ForegroundColor Red}
 else{Write-Host "STEP_076 VERIFIED: $Success" -ForegroundColor Green}
}
if($Failed){exit 1}
