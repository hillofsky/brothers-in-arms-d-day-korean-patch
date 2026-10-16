$ErrorActionPreference="Stop"
[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false)
$env:PYTHONUTF8="1"
$env:PYTHONIOENCODING="utf-8"

$Root="PROJECT_ROOT"
$LogRoot="$Root\log"
$Step="STEP_073"
$LogDir="$LogRoot\$Step"
$Out="$LogDir\outputs"
$Scripts="$LogDir\scripts_used"
$OK="$LogRoot\bia_STEP_073_exact_builder_source_recovery_RESULT.zip"
$FAIL="$LogRoot\fall_bia_STEP_073_exact_builder_source_recovery_RESULT.zip"
$Failed=$false

if(Test-Path $LogDir){
    $s=Get-Date -Format yyyyMMdd_HHmmss
    New-Item -ItemType Directory -Force "$LogRoot\old\$s"|Out-Null
    Move-Item $LogDir "$LogRoot\old\$s\$Step"
}

New-Item -ItemType Directory -Force $LogDir,$Out,$Scripts,(Join-Path $LogRoot "steps")|Out-Null
Copy-Item $PSCommandPath "$Scripts\run.ps1" -Force
Copy-Item "$PSScriptRoot\scripts\*" $Scripts -Force
Copy-Item "$PSScriptRoot\STEP_INFO.txt" $LogDir -Force
try{Start-Transcript "$LogDir\run.log" -Force|Out-Null}catch{}

$Py="LOCAL_PATH"

function State($Phase,$Detail){
    & $Py "$PSScriptRoot\scripts\update_state.py" --root $Root --phase $Phase --detail $Detail
    if($LASTEXITCODE -ne 0){throw "state update failed"}
}

try{
    if(!(Test-Path $Py)){throw "Python runtime missing"}
    State start "Recovering exact Stage43A source from verified STEP064 archive."

    Write-Host "[1/2] Recovering exact historical builder sources..." -ForegroundColor Cyan
    $old=$ErrorActionPreference
    $ErrorActionPreference="Continue"
    try{
        & $Py "$PSScriptRoot\scripts\recover_builder_sources.py" --outdir $Out `
          1>"$LogDir\stdout.txt" 2>"$LogDir\stderr.txt"
        $ec=$LASTEXITCODE
    }finally{
        $ErrorActionPreference=$old
    }
    if($ec -ne 0){throw "source recovery failed ExitCode=$ec"}

    $r=Get-Content "$Out\step073_report.json" -Raw -Encoding UTF8|ConvertFrom-Json
    if($r.status -ne "VERIFIED_SOURCE_RECOVERY"){
        throw "Unexpected source recovery status: $($r.status)"
    }

    State success ("campaign43a="+$r.exact_campaign43a_recovered+" manifest="+$r.manifest_count)
    Write-Host "[2/2] Historical builder sources recovered." -ForegroundColor Green
}catch{
    $Failed=$true
    ($_|Out-String)|Set-Content "$LogDir\FAILURE.txt" -Encoding UTF8
    try{State failure "STEP073 source recovery failed; no ISO modified."}catch{}
}finally{
    try{Stop-Transcript|Out-Null}catch{}

    foreach($p in @("$Root\PROJECT_STATE.md","$LogRoot\steps\STEP_073.md")){
        if(Test-Path $p){Copy-Item $p $Out -Force -ErrorAction SilentlyContinue}
    }

    $zip=if($Failed){$FAIL}else{$OK}
    if(Test-Path $zip){Remove-Item $zip -Force}
    try{Compress-Archive "$LogDir\*" $zip -Force}catch{}

    if($Failed){
        Write-Host "STEP_073 FAILED" -ForegroundColor Red
        Write-Host "Upload: $FAIL"
    }else{
        Write-Host "STEP_073 VERIFIED (NO ISO CHANGE)" -ForegroundColor Green
        Write-Host "Upload: $OK"
    }
}
if($Failed){exit 1}
