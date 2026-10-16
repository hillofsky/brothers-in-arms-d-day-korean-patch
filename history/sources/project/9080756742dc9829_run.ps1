$ErrorActionPreference="Stop"
[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false)
$env:PYTHONUTF8="1"
$env:PYTHONIOENCODING="utf-8"

$Root="PROJECT_ROOT"
$Legacy="LOCAL_PATH"
$LogRoot="PROJECT_ROOT\log"
$Attempt="STEP_044_FIX7"
$LogDir=Join-Path $LogRoot $Attempt
$OutDir=Join-Path $LogDir "outputs"
$ScriptsUsed=Join-Path $LogDir "scripts_used"
$SuccessZip=Join-Path $LogRoot "bia_STEP_044_campaign_next_batch_RESULT.zip"
$FailureZip=Join-Path $LogRoot "fall_bia_STEP_044_campaign_next_batch_RESULT.zip"
$Expected="PROJECT_ROOT\translation\campaign_next_translation.tsv"

$Failed=$false
$LastSuccessfulAction="PowerShell startup"
$PythonExit=$null

if(Test-Path $LogDir){
    $stamp=Get-Date -Format "yyyyMMdd_HHmmss"
    $archive=Join-Path $LogRoot "old\$stamp"
    New-Item -ItemType Directory -Force -Path $archive|Out-Null
    Move-Item -LiteralPath $LogDir -Destination (Join-Path $archive $Attempt)
}
New-Item -ItemType Directory -Force -Path $LogRoot,$LogDir,$OutDir,$ScriptsUsed,(Join-Path $LogRoot "steps")|Out-Null

Copy-Item $PSCommandPath (Join-Path $ScriptsUsed "run.ps1") -Force
Copy-Item (Join-Path $PSScriptRoot "STEP_INFO.txt") $LogDir -Force
Copy-Item (Join-Path $PSScriptRoot "scripts\extract_next_campaign.py") $ScriptsUsed -Force
Copy-Item (Join-Path $PSScriptRoot "scripts\update_state.py") $ScriptsUsed -Force
try{Start-Transcript -LiteralPath (Join-Path $LogDir "run.log") -Force|Out-Null}catch{}

function Find-Python{
    $p="LOCAL_PATH"
    if(Test-Path $p){return $p}
    $c=Get-Command python.exe -ErrorAction SilentlyContinue
    if($c){return $c.Source}
    throw "Python runtime not found"
}
function State([string]$Phase,[string]$Detail){
    $old=$ErrorActionPreference;$ErrorActionPreference="Continue"
    try{
        & $Python (Join-Path $PSScriptRoot "scripts\update_state.py") `
          --root $Root --phase $Phase --detail $Detail
        $ec=$LASTEXITCODE
    }finally{$ErrorActionPreference=$old}
    if($ec -ne 0){throw "update_state.py failed: $Phase exit=$ec"}
}
function Failure([string]$Reason){
@"
PROJECT: bia
STEP: STEP_044
RETRY: FIX7
TIME: $(Get-Date -Format o)
STATUS: FAILED
FAILURE_REASON:
$Reason
PYTHON_EXIT_CODE: $PythonExit
LAST_SUCCESSFUL_ACTION: $LastSuccessfulAction
EXPECTED_OUTPUT: $Expected
PARTIAL_OUTPUTS: $OutDir
NEXT_RECOMMENDED_ACTION:
Upload PROJECT_ROOT\log\fall_bia_STEP_044_campaign_next_batch_RESULT.zip.
"@|Set-Content -LiteralPath (Join-Path $LogDir "FAILURE.txt") -Encoding UTF8
}

try{
    $Python=Find-Python
    State "start" "FIX7_started_canonical_stage38_campaign_export"
    $LastSuccessfulAction="PROJECT_STATE and STEP log marked IN_PROGRESS"

    $source="PROJECT_ROOT\analysis\stage38_translation_worklist\stage38_translation_units.tsv"
    $iso="PROJECT_ROOT\BIA_STAGE43T_TITLE_PROMPT_FIX.iso"
    if(!(Test-Path $source)){throw "Missing canonical Stage38 worklist: $source"}
    if(!(Test-Path $iso)){throw "Missing Stage43T baseline: $iso"}

    $hashes=@()
    foreach($p in @($source,$iso)){
        $h=Get-FileHash -Algorithm SHA256 -LiteralPath $p
        $hashes+="$($h.Hash)`t$p"
    }
    $hashes|Set-Content -LiteralPath (Join-Path $LogDir "hashes.txt") -Encoding UTF8
    $LastSuccessfulAction="Canonical worklist and Stage43T baseline validated"

    $old=$ErrorActionPreference;$ErrorActionPreference="Continue"
    try{
        & $Python (Join-Path $PSScriptRoot "scripts\extract_next_campaign.py") `
          --root $Root --legacy-root $Legacy --out $OutDir
        $PythonExit=$LASTEXITCODE
    }finally{$ErrorActionPreference=$old}
    if($null -eq $PythonExit){$PythonExit=0}
    if($PythonExit -ne 0){throw "extract_next_campaign.py failed ExitCode=$PythonExit"}

    $LastSuccessfulAction="Canonical campaign master imported and next mission batch exported"
    if(!(Test-Path $Expected)){throw "Expected TSV missing: $Expected"}
    if((Get-Item $Expected).Length -eq 0){throw "Expected TSV empty: $Expected"}

    $report=Get-Content (Join-Path $OutDir "campaign_next_selection.json") -Raw -Encoding UTF8|ConvertFrom-Json
    State "success" ("FIX7_selected_D0_"+$report.selected_mission_code+"_units_"+$report.selected_unit_count)
    $LastSuccessfulAction="STEP_044 VERIFIED discovery/export"
}catch{
    $Failed=$true
    $reason=$_|Out-String
    $reason|Set-Content -LiteralPath (Join-Path $LogDir "stderr_powershell.txt") -Encoding UTF8
    try{Failure $reason}catch{}
    try{State "failure" "FIX7_failed"}catch{}
}finally{
    try{Stop-Transcript|Out-Null}catch{}
    try{
        foreach($p in @(
            "PROJECT_ROOT\PROJECT_STATE.md",
            "PROJECT_ROOT\log\steps\STEP_044.md",
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
STEP=STEP_044_FIX7
WORK_FAILED=$Failed
ZIP_TARGET=$zip
ZIP_ERROR=$($_|Out-String)
LOG_FOLDER=$LogDir
"@|Set-Content (Join-Path $LogRoot "fall_STEP_044_FIX7_ZIP_CREATION_FAILED.txt") -Encoding UTF8
    }

    Write-Host ""
    if($Failed){
        Write-Host "STEP_044 FIX7 FAILED" -ForegroundColor Red
        Write-Host "Upload: $FailureZip"
    }else{
        Write-Host "STEP_044 VERIFIED (campaign discovery/export)" -ForegroundColor Green
        Write-Host "Translation TSV: $Expected"
        Write-Host "Upload: $SuccessZip"
    }
}
if($Failed){exit 1}
