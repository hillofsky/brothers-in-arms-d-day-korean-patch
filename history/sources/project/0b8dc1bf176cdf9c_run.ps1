$ErrorActionPreference="Stop"
[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false)
$env:PYTHONUTF8="1";$env:PYTHONIOENCODING="utf-8"
$Root="PROJECT_ROOT";$LogRoot="$Root\log";$Step="STEP_072_FIX1";$LogDir="$LogRoot\$Step";$Out="$LogDir\outputs";$Scripts="$LogDir\scripts_used"
$OK="$LogRoot\bia_STEP_072_FIX1_compiled967_preflight_RESULT.zip";$FAIL="$LogRoot\fall_bia_STEP_072_FIX1_compiled967_preflight_RESULT.zip"
$Failed=$false
if(Test-Path $LogDir){$s=Get-Date -Format yyyyMMdd_HHmmss;New-Item -ItemType Directory -Force "$LogRoot\old\$s"|Out-Null;Move-Item $LogDir "$LogRoot\old\$s\$Step"}
New-Item -ItemType Directory -Force $LogDir,$Out,$Scripts,(Join-Path $LogRoot "steps")|Out-Null
Copy-Item $PSCommandPath "$Scripts\run.ps1" -Force;Copy-Item "$PSScriptRoot\scripts\*" $Scripts -Force;Copy-Item "$PSScriptRoot\STEP_INFO.txt" $LogDir -Force
try{Start-Transcript "$LogDir\run.log" -Force|Out-Null}catch{}
$Py="LOCAL_PATH"
function State($Phase,$Detail){& $Py "$PSScriptRoot\scripts\update_state.py" --root $Root --phase $Phase --detail $Detail;if($LASTEXITCODE -ne 0){throw "state update failed"}}
try{
 if(!(Test-Path $Py)){throw "Python runtime missing"}
 State start "Recover archived Stage43A builder if available; independently validate generalized patch prerequisites."
 Write-Host "[1/2] Recovering archived campaign43a reference + validating 967/32-MDI evidence..." -ForegroundColor Cyan
 $old=$ErrorActionPreference;$ErrorActionPreference="Continue"
 try{& $Py "$PSScriptRoot\scripts\step072_fix1_recover_validate.py" --outdir $Out 1>"$LogDir\stdout.txt" 2>"$LogDir\stderr.txt";$ec=$LASTEXITCODE}
 finally{$ErrorActionPreference=$old}
 if($ec -ne 0){throw "STEP072 FIX1 validation failed ExitCode=$ec"}
 $r=Get-Content "$Out\step072_fix1_report.json" -Raw -Encoding UTF8|ConvertFrom-Json
 if($r.status -ne "VERIFIED_READY_FOR_GENERALIZED_PATCHER"){throw "Unexpected report status $($r.status)"}
 State success ("compiled967_ready refs="+$r.compiled967_validation.structural_reference_rows+" mdis="+$r.compiled967_validation.target_mdis+" historical43a="+$r.historical_43a_recovered)
 Write-Host "[2/2] VERIFIED: generalized 967 patcher prerequisites complete." -ForegroundColor Green
}catch{
 $Failed=$true;($_|Out-String)|Set-Content "$LogDir\FAILURE.txt" -Encoding UTF8
 try{State failure "STEP072_FIX1 failed; no ISO modified."}catch{}
}finally{
 try{Stop-Transcript|Out-Null}catch{}
 foreach($p in @("$Root\PROJECT_STATE.md","$LogRoot\steps\STEP_072_FIX1.md")){if(Test-Path $p){Copy-Item $p $Out -Force -ErrorAction SilentlyContinue}}
 $zip=if($Failed){$FAIL}else{$OK};if(Test-Path $zip){Remove-Item $zip -Force}
 try{Compress-Archive "$LogDir\*" $zip -Force}catch{}
 if($Failed){Write-Host "FAILED: $FAIL" -ForegroundColor Red}else{Write-Host "Upload: $OK" -ForegroundColor Green}
}
if($Failed){exit 1}
