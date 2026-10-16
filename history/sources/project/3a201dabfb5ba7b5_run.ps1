$ErrorActionPreference='Stop'
[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false)
$env:PYTHONUTF8='1';$env:PYTHONIOENCODING='utf-8'
$Root='PROJECT_ROOT';$LogRoot="$Root\log";$Step='STEP_075';$LogDir="$LogRoot\$Step"
$Out="$LogDir\outputs";$Scripts="$LogDir\scripts_used"
$OK="$LogRoot\bia_STEP_075_dsl_variant_audit_RESULT.zip"
$FAIL="$LogRoot\fall_bia_STEP_075_dsl_variant_audit_RESULT.zip"
$Py='LOCAL_PATH'
$Failed=$false
New-Item -ItemType Directory -Force -Path $LogRoot,(Join-Path $LogRoot 'steps')|Out-Null
if(Test-Path $LogDir){
 $s=Get-Date -Format 'yyyyMMdd_HHmmss';$d="$LogRoot\old\$s"
 New-Item -ItemType Directory -Force -Path $d|Out-Null
 Move-Item $LogDir (Join-Path $d $Step)
}
New-Item -ItemType Directory -Force -Path $LogDir,$Out,$Scripts|Out-Null
Copy-Item $PSCommandPath "$Scripts\run.ps1" -Force
Copy-Item "$PSScriptRoot\scripts\*" $Scripts -Force
Copy-Item "$PSScriptRoot\evidence\*" $Scripts -Force
Copy-Item "$PSScriptRoot\STEP_INFO.txt" $LogDir -Force
try{Start-Transcript -LiteralPath "$LogDir\run.log" -Force|Out-Null}catch{}
function State([string]$Phase,[string]$Detail){
 & $Py "$PSScriptRoot\scripts\update_state.py" --root $Root --phase $Phase --detail $Detail
 if($LASTEXITCODE -ne 0){throw "state update failed ($Phase)"}
}
try{
 if(!(Test-Path $Py)){throw "Python runtime missing: $Py"}
 foreach($p in @("$Root\BIA_STAGE69_FIX2_NONMDI_INT92_TEST.iso", "$Root\Brothers in Arms - D-Day (USA) (v1.01).iso")){
  if(!(Test-Path $p)){throw "Missing ISO: $p"}
 }
 State start 'Characterizing 32 DSL variant patterns; NO ISO modification.'
 Write-Host '[1/3] Reading each original/Stage69 DSL + validating DSX...' -ForegroundColor Cyan
 $old=$ErrorActionPreference;$ErrorActionPreference='Continue'
 try{
  & $Py "$PSScriptRoot\scripts\audit_dsl_variants.py" --package-root $PSScriptRoot --outdir $Out 1>"$LogDir\stdout.txt" 2>"$LogDir\stderr.txt"
  $ec=$LASTEXITCODE
 }finally{$ErrorActionPreference=$old}
 if($ec -ne 0){throw "DSL audit failed exit=$ec"}
 $r=Get-Content "$Out\step075_report.json" -Raw -Encoding UTF8|ConvertFrom-Json
 if($r.status -ne 'VERIFIED_DSL_VARIANT_AUDIT' -or $r.target_mdi_count -ne 32 -or !$r.source_iso_preserved){throw 'Incomplete DSL audit report'}
 State success '32 MDI DSL variants recorded; no ISO changed; next determine per-MDI texture binding.'
 Write-Host '[2/3] 32 DSL reports completed and Stage69 preserved.' -ForegroundColor Green
}catch{
 $Failed=$true;($_|Out-String)|Set-Content "$LogDir\FAILURE.txt" -Encoding UTF8
 try{if(Test-Path $Py){State failure 'DSL audit failed; no ISO touched.'}}catch{}
}finally{
 try{Stop-Transcript|Out-Null}catch{}
 foreach($p in @("$Root\PROJECT_STATE.md","$LogRoot\steps\STEP_075.md")){
  if(Test-Path $p){Copy-Item $p $Out -Force -ErrorAction SilentlyContinue}
 }
 $zip=if($Failed){$FAIL}else{$OK}
 if(Test-Path $zip){Remove-Item $zip -Force}
 try{Compress-Archive -Path "$LogDir\*" -DestinationPath $zip -Force}catch{
  ($_|Out-String)|Set-Content "$LogRoot\fall_STEP_075_ZIP_CREATION_FAILED.txt" -Encoding UTF8
 }
 Write-Host '[3/3] Result packaged.' -ForegroundColor Cyan
 if($Failed){Write-Host "FAILED: $FAIL" -ForegroundColor Red}else{Write-Host "Upload: $OK" -ForegroundColor Green}
}
if($Failed){exit 1}
