$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)

$ProjectRoot = "PROJECT_ROOT"
$GameRoot = "PROJECT_ROOT"
$StepId = "STEP_044"
$LogsRoot = "PROJECT_ROOT\log"
$StepLogDir = Join-Path $LogsRoot $StepId
$PackagesDir = $LogsRoot
$ScriptsUsed = Join-Path $StepLogDir "scripts_used"
$OutputsDir = Join-Path $StepLogDir "outputs"
$SuccessZip = Join-Path $PackagesDir "bia_STEP_044_campaign_next_batch_RESULT.zip"
$FailureZip = Join-Path $PackagesDir "fall_bia_STEP_044_campaign_next_batch_RESULT.zip"
$ExpectedOutput = Join-Path $ProjectRoot "translation\campaign_next_translation.tsv"
$Failed = $false
$LastSuccessfulAction = "PowerShell startup"
$Python = $null

# Create logs before validating any input.
New-Item -ItemType Directory -Force -Path $LogsRoot,$StepLogDir,$PackagesDir,$ScriptsUsed,$OutputsDir | Out-Null
Copy-Item -LiteralPath $PSCommandPath -Destination (Join-Path $ScriptsUsed "run.ps1") -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot "STEP_INFO.txt") -Destination $StepLogDir -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot "scripts\update_state.py") -Destination $ScriptsUsed -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot "scripts\discover_campaign.py") -Destination $ScriptsUsed -Force
try { Start-Transcript -LiteralPath (Join-Path $StepLogDir "run.log") -Force | Out-Null } catch {}

function Find-Python {
    $Bundled = "LOCAL_PATH"
    if (Test-Path $Bundled) { return $Bundled }
    $P = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($P) { return $P.Source }
    throw "Python runtime not found"
}
function Update-State([string]$Phase,[string]$Detail) {
    & $Python (Join-Path $PSScriptRoot "scripts\update_state.py") --project-root $ProjectRoot --phase $Phase --detail $Detail
    if ($LASTEXITCODE -ne 0) { throw "update_state.py failed. ExitCode=$LASTEXITCODE" }
}
function Write-Failure([string]$Reason) {
@"
PROJECT: bia
STEP: STEP_044
TIME: $(Get-Date -Format o)
STATUS: FAILED

FAILED_COMMAND:
See run.log / stderr.txt / stderr_powershell.txt

EXIT_CODE:
$LASTEXITCODE

FAILURE_REASON:
$Reason

LAST_SUCCESSFUL_ACTION:
$LastSuccessfulAction

EXPECTED_OUTPUT:
$ExpectedOutput

PARTIAL_OUTPUTS:
$OutputsDir
$ProjectRoot\translation\text_master.tsv
$ProjectRoot\translation\campaign_next_translation.tsv

NEXT_RECOMMENDED_ACTION:
Upload the fall_ RESULT ZIP. Do not manually edit the project files before review.
"@ | Set-Content -LiteralPath (Join-Path $StepLogDir "FAILURE.txt") -Encoding UTF8
}

try {
    $Python = Find-Python
    Update-State "start" "STEP_044 started. ISO untouched. Remaining six movie validations remain deferred."
    $LastSuccessfulAction = "PROJECT_STATE.md / STEP_044.md marked IN_PROGRESS"

@"
TIME=$(Get-Date -Format o)
PROJECT_ROOT=$ProjectRoot
GAME_ROOT=$GameRoot
BASE_ISO=$GameRoot\BIA_STAGE43T_TITLE_PROMPT_FIX.iso
PYTHON=$Python
"@ | Set-Content -LiteralPath (Join-Path $StepLogDir "environment.txt") -Encoding UTF8

    $BaseIso = Join-Path $GameRoot "BIA_STAGE43T_TITLE_PROMPT_FIX.iso"
    if (-not (Test-Path $BaseIso)) { throw "Stage43T baseline missing: $BaseIso" }
    # PROJECT_ROOT is authoritative. If a required handoff input is not there yet,
    # import ONLY that missing file from the legacy Codex work tree.
    # New state/log/results remain under PROJECT_ROOT.
    $LegacyRoot = "LOCAL_PATH"
    $Required = @(
        "work\campaign_first_ko.json",
        "work\first_campaign_units.json",
        "work\campaign_first_reference_audit.json",
        "work\campaign_second_ko.json",
        "work\campaign_second_units.json",
        "work\campaign_second_reference_audit.json"
    )

    foreach ($Rel in $Required) {
        $DstInput = Join-Path $ProjectRoot $Rel
        if (-not (Test-Path $DstInput)) {
            $LegacyInput = Join-Path $LegacyRoot $Rel
            if (Test-Path $LegacyInput) {
                New-Item -ItemType Directory -Force -Path (Split-Path $DstInput -Parent) | Out-Null
                Copy-Item -LiteralPath $LegacyInput -Destination $DstInput -Force
                Add-Content -LiteralPath (Join-Path $StepLogDir "imported_legacy_inputs.txt") `
                    -Value "$LegacyInput`t=>`t$DstInput"
            }
        }
    }

    $Required = @(
        "work\campaign_first_ko.json",
        "work\first_campaign_units.json",
        "work\campaign_first_reference_audit.json",
        "work\campaign_second_ko.json",
        "work\campaign_second_units.json",
        "work\campaign_second_reference_audit.json"
    )
    foreach ($Rel in $Required) {
        $P = Join-Path $ProjectRoot $Rel
        if (-not (Test-Path $P)) { throw "Required handoff input missing: $P" }
    }
    $LastSuccessfulAction = "Required campaign handoff files validated"

    $HashInputs = @(
        $BaseIso,
        (Join-Path $ProjectRoot "work\campaign_first_ko.json"),
        (Join-Path $ProjectRoot "work\campaign_second_ko.json"),
        (Join-Path $ProjectRoot "work\first_campaign_units.json"),
        (Join-Path $ProjectRoot "work\campaign_second_units.json")
    )
    $HL = foreach ($P in $HashInputs) {
        $H = Get-FileHash -Algorithm SHA256 -LiteralPath $P
        "$($H.Hash)`t$P"
    }
    $HL | Set-Content -LiteralPath (Join-Path $StepLogDir "hashes.txt") -Encoding UTF8

    & $Python (Join-Path $PSScriptRoot "scripts\discover_campaign.py") --project-root $ProjectRoot --out-dir $OutputsDir `
        1> (Join-Path $StepLogDir "stdout.txt") 2> (Join-Path $StepLogDir "stderr.txt")
    if ($LASTEXITCODE -ne 0) { throw "discover_campaign.py failed. ExitCode=$LASTEXITCODE" }
    $LastSuccessfulAction = "Next untranslated campaign mission discovered and TSV exported"

    if (-not (Test-Path $ExpectedOutput)) { throw "Expected output missing: $ExpectedOutput" }
    if ((Get-Item $ExpectedOutput).Length -eq 0) { throw "Expected output empty: $ExpectedOutput" }
    $ReportPath = Join-Path $OutputsDir "campaign_discovery_report.json"
    if (-not (Test-Path $ReportPath)) { throw "Missing discovery report" }
    $R = Get-Content -LiteralPath $ReportPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if (-not $R.validation.batch_nonempty) { throw "Discovered batch is empty" }
    if ($R.validation.duplicate_ids.Count -gt 0) { throw "Duplicate text IDs detected" }
    if ($R.validation.blank_source_ids.Count -gt 0) { throw "Blank source rows detected" }

    $Detail = "Selected $($R.selected_source_file), $($R.selected_unit_count) units. TSV ready for translation. No ISO modification."
    Update-State "success" $Detail
    $LastSuccessfulAction = "STEP_044 extraction/discovery marked VERIFIED"

    Copy-Item -LiteralPath (Join-Path $ProjectRoot "PROJECT_STATE.md") -Destination $StepLogDir -Force
    Copy-Item -LiteralPath (Join-Path $ProjectRoot "logs\steps\STEP_044.md") -Destination $StepLogDir -Force
    Copy-Item -LiteralPath (Join-Path $ProjectRoot "translation\text_master.tsv") -Destination $OutputsDir -Force
    Copy-Item -LiteralPath $ExpectedOutput -Destination $OutputsDir -Force
}
catch {
    $Failed = $true
    $Reason = ($_ | Out-String)
    $Reason | Set-Content -LiteralPath (Join-Path $StepLogDir "stderr_powershell.txt") -Encoding UTF8
    try { Write-Failure $Reason } catch {}
    try {
        if (-not $Python) { $Python = Find-Python }
        Update-State "failure" ("STEP_044 failed after: " + $LastSuccessfulAction)
    } catch {}
}
finally {
    try { Stop-Transcript | Out-Null } catch {}
    try {
        if (Test-Path (Join-Path $ProjectRoot "PROJECT_STATE.md")) { Copy-Item -LiteralPath (Join-Path $ProjectRoot "PROJECT_STATE.md") -Destination $StepLogDir -Force }
        if (Test-Path (Join-Path $ProjectRoot "logs\steps\STEP_044.md")) { Copy-Item -LiteralPath (Join-Path $ProjectRoot "logs\steps\STEP_044.md") -Destination $StepLogDir -Force }
        if (Test-Path (Join-Path $ProjectRoot "translation\text_master.tsv")) { Copy-Item -LiteralPath (Join-Path $ProjectRoot "translation\text_master.tsv") -Destination $OutputsDir -Force }
        if (Test-Path $ExpectedOutput) { Copy-Item -LiteralPath $ExpectedOutput -Destination $OutputsDir -Force }
    } catch {
        ($_ | Out-String) | Set-Content -LiteralPath (Join-Path $StepLogDir "log_collection_error.txt") -Encoding UTF8
    }

    $ZipPath = if ($Failed) { $FailureZip } else { $SuccessZip }
    $ZipFailed = $false
    try {
        if (Test-Path $ZipPath) { Remove-Item $ZipPath -Force }
        Compress-Archive -Path (Join-Path $StepLogDir "*") -DestinationPath $ZipPath -Force
        if (-not (Test-Path $ZipPath)) { throw "RESULT ZIP not created" }
        if ((Get-Item $ZipPath).Length -eq 0) { throw "RESULT ZIP is empty" }
    } catch {
        $ZipFailed = $true
@"
STEP=STEP_044
TIME=$(Get-Date -Format o)
WORK_FAILED=$Failed
ZIP_TARGET=$ZipPath
ZIP_ERROR=$($_ | Out-String)
LOG_FOLDER=$StepLogDir
UPLOAD_ALTERNATIVE=$StepLogDir
"@ | Set-Content -LiteralPath (Join-Path $LogsRoot "fall_STEP_044_ZIP_CREATION_FAILED.txt") -Encoding UTF8
    }

    Write-Host ""
    if ($ZipFailed) {
        Write-Host "RESULT ZIP creation failed; logs preserved at $StepLogDir" -ForegroundColor Red
    } elseif ($Failed) {
        Write-Host "STEP_044 FAILED" -ForegroundColor Red
        Write-Host "Upload: $FailureZip"
    } else {
        Write-Host "STEP_044 VERIFIED (discovery/export only)" -ForegroundColor Green
        Write-Host "Translation TSV: $ExpectedOutput"
        Write-Host "Upload: $SuccessZip"
    }
}
if ($Failed) { exit 1 }
