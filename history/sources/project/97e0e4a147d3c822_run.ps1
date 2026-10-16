$ErrorActionPreference="Stop"
[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false)
$env:PYTHONUTF8="1";$env:PYTHONIOENCODING="utf-8"
$Root="PROJECT_ROOT";$Log="$Root\log";$Step="STEP_082"
$StepDir="$Log\$Step";$Out="$StepDir\outputs";$Used="$StepDir\scripts_used"
$OK="$Log\bia_STEP_082_localization_fault_audit_RESULT.zip"
$FAIL="$Log\fall_bia_STEP_082_localization_fault_audit_RESULT.zip"
$Py="LOCAL_PATH"
$Failed=$false;$Checkpoint="preflight"
New-Item -ItemType Directory -Force $Log | Out-Null
if(Test-Path $StepDir){
    $stamp=Get-Date -Format yyyyMMdd_HHmmss
    $old="$Log\old\STEP_082_$stamp"
    New-Item -ItemType Directory -Force (Split-Path $old -Parent)|Out-Null
    Move-Item -LiteralPath $StepDir -Destination $old
}
New-Item -ItemType Directory -Force $StepDir,$Out,$Used,"$Log\steps" | Out-Null
Copy-Item "$PSScriptRoot\scripts\*" $Used -Force
Copy-Item "$PSScriptRoot\evidence\*" $Used -Force
Copy-Item "$PSScriptRoot\reference\*" $Used -Force
Copy-Item $PSCommandPath "$Used\run.ps1" -Force
Copy-Item "$PSScriptRoot\README.md" "$StepDir\README.md" -Force
try{Start-Transcript -Path "$StepDir\run.log" -Force|Out-Null}catch{}
function State([string]$phase,[string]$detail){
    & $Py "$PSScriptRoot\scripts\update_state.py" --root $Root --phase $phase --detail $detail
    if($LASTEXITCODE -ne 0){throw "State update failed"}
}
try{
    if(!(Test-Path $Py)){throw "Missing Python runtime: $Py"}
    foreach($f in @(
        "$Root\BIA_STAGE69_FIX2_NONMDI_INT92_TEST.iso",
        "$Root\BIA_STAGE79_COMPILED967_STRUCTURAL_TEST.iso",
        "$Root\Brothers in Arms - D-Day (USA) (v1.01).iso"
    )){if(!(Test-Path $f)){throw "Missing input ISO: $f"}}
    State start "User-reported mission1 residual English and mission2 > font failure. Read-only raw binary capture."
    $Checkpoint="capture_mdi_dsl_and_fonts"
    Write-Host "[STEP082] Collecting exact mission 1/2 resource differences and font evidence (ISO read-only)..." -ForegroundColor Cyan
    $prev=$ErrorActionPreference;$ErrorActionPreference="Continue"
    try{
        & $Py "$PSScriptRoot\scripts\audit_localization_failures.py" `
            --pkg $PSScriptRoot --out $Out `
            1>"$StepDir\stdout.txt" 2>"$StepDir\stderr.txt"
        $code=$LASTEXITCODE
    }finally{$ErrorActionPreference=$prev}
    if($code -ne 0){throw "Audit exited with $code"}
    $rep=Get-Content "$Out\step082_report.json" -Raw -Encoding UTF8|ConvertFrom-Json
    if($rep.status -ne "VERIFIED_BINARY_EVIDENCE_EXPORTED" -or !$rep.source_isos_preserved){
        throw "Audit completion or original preservation failed"
    }
    State success "Exact mission2 Stage69/79 binary evidence + mission1 English search done, $($rep.resource_count) resources, runtime font defect remains UNRESOLVED."
    Write-Host "[STEP082] Collection complete, ISO files unchanged." -ForegroundColor Green
}catch{
    $Failed=$true
    @("CHECKPOINT=$Checkpoint",($_|Out-String))|Set-Content "$StepDir\FAILURE.txt" -Encoding UTF8
    try{if(Test-Path $Py){State failure "Failed at $Checkpoint; see error/report. No ISO modifications attempted."}}catch{}
}finally{
    try{Stop-Transcript|Out-Null}catch{}
    foreach($f in @("$Root\PROJECT_STATE.md","$Log\steps\STEP_082.md")){
        if(Test-Path $f){Copy-Item $f $Out -Force -ErrorAction SilentlyContinue}
    }
    $target=if($Failed){$FAIL}else{$OK}
    if(Test-Path $target){Remove-Item $target -Force}
    try{Compress-Archive -Path "$StepDir\*" -DestinationPath $target -CompressionLevel Optimal -Force}catch{
        ($_|Out-String)|Set-Content "$Log\fall_STEP_082_ZIP_ERROR.txt" -Encoding UTF8
        throw
    }
    Write-Host "UPLOAD RESULT: $target"
}
if($Failed){exit 1}
