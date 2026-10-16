$ErrorActionPreference="Stop"
[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false)
$env:PYTHONUTF8="1";$env:PYTHONIOENCODING="utf-8"

$Root="PROJECT_ROOT";$LogRoot="$Root\log";$Step="STEP_072"
$LogDir="$LogRoot\$Step";$OutDir="$LogDir\outputs";$Scripts="$LogDir\scripts_used"
$OK="$LogRoot\bia_STEP_072_compiled967_preflight_RESULT.zip"
$FAIL="$LogRoot\fall_bia_STEP_072_compiled967_preflight_RESULT.zip"
$Failed=$false;$Py=$null

if(Test-Path $LogDir){
 $s=Get-Date -Format yyyyMMdd_HHmmss
 New-Item -ItemType Directory -Force "$LogRoot\old\$s"|Out-Null
 Move-Item $LogDir "$LogRoot\old\$s\$Step"
}
New-Item -ItemType Directory -Force $LogDir,$OutDir,$Scripts,(Join-Path $LogRoot "steps")|Out-Null
Copy-Item $PSCommandPath "$Scripts\run.ps1" -Force
Copy-Item "$PSScriptRoot\scripts\*" $Scripts -Force
Copy-Item "$PSScriptRoot\STEP_INFO.txt" $LogDir -Force
try{Start-Transcript "$LogDir\run.log" -Force|Out-Null}catch{}

function PyPath{
 $p="LOCAL_PATH"
 if(Test-Path $p){return $p}
 $c=Get-Command python.exe -ErrorAction SilentlyContinue
 if($c){return $c.Source}
 throw "Python runtime not found"
}
function State([string]$Phase,[string]$Detail){
 & $Py "$PSScriptRoot\scripts\update_state.py" --root $Root --phase $Phase --detail $Detail
 if($LASTEXITCODE -ne 0){throw "state update failed"}
}

try{
 $Py=PyPath
 State "start" "Collecting existing compiled967 evidence; INT92 canary work stopped."
 Write-Host "[1/2] Collecting STEP066/064/39A evidence from PROJECT_ROOT..." -ForegroundColor Cyan

 $old=$ErrorActionPreference;$ErrorActionPreference="Continue"
 try{
  & $Py "$PSScriptRoot\scripts\collect_compiled967_evidence.py" --outdir $OutDir `
    1>"$LogDir\stdout.txt" 2>"$LogDir\stderr.txt"
  $ec=$LASTEXITCODE
 }finally{$ErrorActionPreference=$old}

 if($ec -ne 0){throw "compiled967 evidence preflight failed ExitCode=$ec"}

 $r=Get-Content "$OutDir\step072_report.json" -Raw -Encoding UTF8|ConvertFrom-Json
 if($r.status -ne "READY_FOR_GENERALIZED_PATCHER"){throw "Unexpected report status: $($r.status)"}

 State "success" "Existing evidence collected; ready to construct generalized 967 MDI patcher."
 Write-Host "[2/2] Evidence collection complete." -ForegroundColor Green
}catch{
 $Failed=$true
 ($_|Out-String)|Set-Content "$LogDir\FAILURE.txt" -Encoding UTF8
 try{if($Py){State "failure" "STEP072 evidence collection failed; no ISO modified."}}catch{}
}finally{
 try{Stop-Transcript|Out-Null}catch{}
 foreach($p in @("$Root\PROJECT_STATE.md","$LogRoot\steps\STEP_072.md")){
  if(Test-Path $p){Copy-Item $p $OutDir -Force -ErrorAction SilentlyContinue}
 }
 $zip=if($Failed){$FAIL}else{$OK}
 if(Test-Path $zip){Remove-Item $zip -Force}
 try{Compress-Archive "$LogDir\*" $zip -Force}catch{}
 if($Failed){
  Write-Host "STEP_072 FAILED" -ForegroundColor Red
  Write-Host "Upload: $FAIL"
 }else{
  Write-Host "STEP_072 VERIFIED (NO ISO CHANGE)" -ForegroundColor Green
  Write-Host "Upload: $OK"
 }
}
if($Failed){exit 1}
