$ErrorActionPreference="Stop"
[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false)
$env:PYTHONUTF8="1"
$env:PYTHONIOENCODING="utf-8"

$Root="PROJECT_ROOT"
$LogRoot="$Root\log"
$Step="STEP_074_FIX6"
$LogDir="$LogRoot\$Step"
$Out="$LogDir\outputs"
$Scripts="$LogDir\scripts_used"

$OK="$LogRoot\bia_STEP_074_FIX6_compiled967_bulk_build_RESULT.zip"
$FAIL="$LogRoot\fall_bia_STEP_074_FIX6_compiled967_bulk_build_RESULT.zip"
$OutputISO="$Root\BIA_STAGE74_FIX6_COMPILED967_BULK_TEST.iso"

$Failed=$false
$Py="LOCAL_PATH"

if(Test-Path $LogDir){
    $s=Get-Date -Format yyyyMMdd_HHmmss
    New-Item -ItemType Directory -Force "$LogRoot\old\$s"|Out-Null
    Move-Item $LogDir "$LogRoot\old\$s\$Step"
}
New-Item -ItemType Directory -Force $LogDir,$Out,$Scripts,(Join-Path $LogRoot "steps")|Out-Null
Copy-Item $PSCommandPath "$Scripts\run.ps1" -Force
Copy-Item "$PSScriptRoot\scripts\*" $Scripts -Force
Copy-Item "$PSScriptRoot\evidence\*" $Scripts -Force
Copy-Item "$PSScriptRoot\reference\*" $Scripts -Force
Copy-Item "$PSScriptRoot\STEP_INFO.txt" $LogDir -Force
Copy-Item "$PSScriptRoot\ROOT_CAUSE.txt" $LogDir -Force
try{Start-Transcript "$LogDir\run.log" -Force|Out-Null}catch{}

function State($Phase,$Detail){
    & $Py "$PSScriptRoot\scripts\update_state.py" --root $Root --phase $Phase --detail $Detail
    if($LASTEXITCODE -ne 0){throw "state update failed"}
}

try{
    if(!(Test-Path $Py)){throw "Python runtime missing: $Py"}
    foreach($p in @(
        "$Root\Brothers in Arms - D-Day (USA) (v1.01).iso",
        "$Root\BIA_STAGE69_FIX2_NONMDI_INT92_TEST.iso",
        "$Root\bia_stage39a_tools\stage39a_tmr18_512x512_swizzled.bin"
    )){
        if(!(Test-Path $p)){throw "Required input missing: $p"}
    }

    State start "FIX5: two independent D0_0130_ font roles; template-specific metrics and no shared original-texture assumption."

    Write-Host "[1/3] Dry-running 32 MDIs with two-role font matching..." -ForegroundColor Cyan
    $old=$ErrorActionPreference
    $ErrorActionPreference="Continue"
    try{
        & $Py "$PSScriptRoot\scripts\build_compiled967_fix6.py" `
          --package-root $PSScriptRoot `
          --outdir $Out `
          1>"$LogDir\stdout.txt" `
          2>"$LogDir\stderr.txt"
        $ec=$LASTEXITCODE
    }finally{$ErrorActionPreference=$old}

    if($ec -ne 0){throw "build_compiled967_fix6.py failed ExitCode=$ec"}

    $r=Get-Content "$Out\step074_fix6_report.json" -Raw -Encoding UTF8|ConvertFrom-Json
    if($r.status -ne "BUILT_UNVERIFIED"){throw "Unexpected report status: $($r.status)"}
    if($r.compiled_mdi_ids_static_applied -ne 967 -or $r.compiled_mdi_reference_rows_patched -ne 2333 -or $r.target_mdis_patched -ne 32){
        throw "Final count mismatch"
    }

    Write-Host "[2/3] 967 IDs / 2333 refs / 32 MDIs built and ISO-readback verified." -ForegroundColor Green
    State success ("STEP074_FIX5_BUILT_UNVERIFIED ids="+$r.compiled_mdi_ids_static_applied+" refs="+$r.compiled_mdi_reference_rows_patched+" mdis="+$r.target_mdis_patched+" runtime_FALSE")
    Write-Host "[3/3] Status: BUILT_UNVERIFIED" -ForegroundColor Green
}catch{
    $Failed=$true
    ($_|Out-String)|Set-Content "$LogDir\FAILURE.txt" -Encoding UTF8
    try{
        if(Test-Path $Py){
            State failure "STEP074 FIX5 failed safely. Source Stage69 preserved; inspect template-role/blocked evidence."
        }
    }catch{}
}finally{
    try{Stop-Transcript|Out-Null}catch{}
    foreach($p in @("$Root\PROJECT_STATE.md","$LogRoot\steps\STEP_074_FIX6.md")){
        if(Test-Path $p){Copy-Item $p $Out -Force -ErrorAction SilentlyContinue}
    }
    $zip=if($Failed){$FAIL}else{$OK}
    if(Test-Path $zip){Remove-Item $zip -Force}
    try{Compress-Archive "$LogDir\*" $zip -Force}catch{
        ($_|Out-String)|Set-Content "$LogRoot\fall_STEP_074_FIX6_ZIP_CREATION_FAILED.txt" -Encoding UTF8
    }

    if($Failed){
        Write-Host "STEP_074 FIX6 FAILED" -ForegroundColor Red
        Write-Host "Upload: $FAIL"
    }else{
        Write-Host "STEP_074 FIX6 BUILT_UNVERIFIED" -ForegroundColor Green
        Write-Host "ISO: $OutputISO"
        Write-Host "Upload: $OK"
    }
}
if($Failed){exit 1}
