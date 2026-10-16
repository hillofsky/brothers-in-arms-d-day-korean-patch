$ErrorActionPreference="Stop"
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
$env:PYTHONUTF8="1"
$env:PYTHONIOENCODING="utf-8"

$Root = "PROJECT_ROOT"
$Log = Join-Path $Root "log"
$Step = "STEP_078"
$StepDir = Join-Path $Log $Step
$Out = Join-Path $StepDir "outputs"
$Used = Join-Path $StepDir "scripts_used"
$Py = "LOCAL_PATH"

$SuccessZip=Join-Path $Log "bia_STEP_078_dsl_binary_evidence_export_RESULT.zip"
$FailZip=Join-Path $Log "fall_bia_STEP_078_dsl_binary_evidence_export_RESULT.zip"
$Fail=$false

New-Item -ItemType Directory -Force $Log | Out-Null
if (Test-Path $StepDir) {
    $archive = Join-Path $Log ("old\STEP_078_"+(Get-Date -Format "yyyyMMdd_HHmmss"))
    New-Item -ItemType Directory -Force (Split-Path $archive -Parent) | Out-Null
    Move-Item -LiteralPath $StepDir -Destination $archive
}
New-Item -ItemType Directory -Force $StepDir,$Out,$Used,(Join-Path $Log "steps") | Out-Null
Copy-Item "$PSScriptRoot\scripts\*" $Used -Force
Copy-Item "$PSScriptRoot\evidence\*" $Used -Force
Copy-Item $PSCommandPath "$Used\run.ps1" -Force
Copy-Item "$PSScriptRoot\README.md" "$StepDir\README.md" -Force

try { Start-Transcript -Path "$StepDir\run.log" -Force | Out-Null } catch {}

function Set-State([string]$phase,[string]$detail){
    & $Py "$PSScriptRoot\scripts\update_state.py" --phase $phase --root $Root --detail $detail
    if($LASTEXITCODE -ne 0){throw "Update state failed"}
}

try {
    if(!(Test-Path $Py)) { throw "Python runtime not found: $Py" }
    Set-State start "Exporting exact binary source samples; no ISO modification."

    $oldEA=$ErrorActionPreference
    $ErrorActionPreference="Continue"
    try {
        & $Py "$PSScriptRoot\scripts\export_binary_evidence.py" `
          --package-root $PSScriptRoot `
          --outdir $Out `
          1> "$StepDir\stdout.txt" 2> "$StepDir\stderr.txt"
        $ret=$LASTEXITCODE
    } finally { $ErrorActionPreference=$oldEA }
    if($ret -ne 0) {throw "Export failed. Exit code: $ret"}

    $rep=Get-Content "$Out\step078_report.json" -Raw -Encoding UTF8 | ConvertFrom-Json
    if($rep.status -ne "VERIFIED_BINARY_EVIDENCE_EXPORTED") {
        throw "Invalid completion status: $($rep.status)"
    }
    if(![bool]$rep.stage69_preserved -or ![bool]$rep.original_preserved){
        throw "ISO preservation validation failed"
    }

    Set-State success "Exported $($rep.captured_resources) exact binaries, byte identity and 6 DSX/DSL checks verified; no ISO modified."
} catch {
    $Fail=$true
    ($_ | Out-String) | Set-Content "$StepDir\FAILURE.txt" -Encoding UTF8
    try { if(Test-Path $Py) { Set-State failure "STEP078 evidence export failed. See FAILURE.txt and stdout/stderr." } } catch {}
} finally {
    try { Stop-Transcript | Out-Null } catch {}
    foreach($p in @("$Root\PROJECT_STATE.md", "$Log\steps\STEP_078.md")) {
        if(Test-Path $p) { Copy-Item $p $Out -Force -ErrorAction SilentlyContinue }
    }
    $result = if($Fail){$FailZip}else{$SuccessZip}
    if(Test-Path $result){Remove-Item $result -Force}
    try {
        Compress-Archive -Path "$StepDir\*" -DestinationPath $result -CompressionLevel Optimal -Force
    } catch {
        $msg=($_|Out-String)
        $msg | Set-Content "$Log\fall_STEP_078_ZIP_ERROR.txt" -Encoding UTF8
        throw
    }
    Write-Host ""
    if($Fail){
        Write-Host "STEP_078 FAILED. Upload: $FailZip" -ForegroundColor Red
    } else {
        Write-Host "STEP_078 VERIFIED. Upload: $SuccessZip" -ForegroundColor Green
    }
}
if($Fail){exit 1}
