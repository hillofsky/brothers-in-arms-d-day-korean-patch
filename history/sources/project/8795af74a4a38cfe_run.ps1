$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

$ProjectRoot = "PROJECT_ROOT"
$LegacyRoot = "LOCAL_PATH"
$LogsRoot = "PROJECT_ROOT\log"
$Attempt = "STEP_044_FIX6"
$StepLogDir = Join-Path $LogsRoot $Attempt
$OutputsDir = Join-Path $StepLogDir "outputs"
$ScriptsUsed = Join-Path $StepLogDir "scripts_used"

$SuccessZip = Join-Path $LogsRoot "bia_STEP_044_campaign_next_batch_RESULT.zip"
$FailureZip = Join-Path $LogsRoot "fall_bia_STEP_044_campaign_next_batch_RESULT.zip"
$ExpectedTsv = "PROJECT_ROOT\translation\campaign_next_translation.tsv"

$Failed = $false
$LastSuccessfulAction = "PowerShell startup"
$PythonExitCode = $null

# Fresh attempt folder. Never mix retry logs.
if (Test-Path $StepLogDir) {
    $stamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $old = Join-Path $LogsRoot "old\$stamp"
    New-Item -ItemType Directory -Force -Path $old | Out-Null
    Move-Item -LiteralPath $StepLogDir -Destination (Join-Path $old $Attempt)
}

New-Item -ItemType Directory -Force -Path `
    $LogsRoot,$StepLogDir,$OutputsDir,$ScriptsUsed,(Join-Path $LogsRoot "steps") | Out-Null

Copy-Item -LiteralPath $PSCommandPath `
    -Destination (Join-Path $ScriptsUsed "run.ps1") -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot "STEP_INFO.txt") `
    -Destination $StepLogDir -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot "scripts\discover_campaign_fix6.py") `
    -Destination $ScriptsUsed -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot "scripts\update_state.py") `
    -Destination $ScriptsUsed -Force

try { Start-Transcript -LiteralPath (Join-Path $StepLogDir "run.log") -Force | Out-Null } catch {}

function Find-Python {
    $bundled = "LOCAL_PATH"
    if (Test-Path $bundled) { return $bundled }
    $cmd = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    throw "Python runtime not found"
}

function Update-State {
    param(
        [string]$Phase,
        [string]$Detail
    )

    # ASCII-only detail avoids Windows PowerShell 5 encoding ambiguity.
    $oldEap = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & $Python (Join-Path $PSScriptRoot "scripts\update_state.py") `
            --root $ProjectRoot `
            --phase $Phase `
            --detail $Detail `
            1> (Join-Path $StepLogDir "state_${Phase}_stdout.txt") `
            2> (Join-Path $StepLogDir "state_${Phase}_stderr.txt")
        $ec = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $oldEap
    }

    if ($null -eq $ec) { $ec = 0 }
    if ($ec -ne 0) {
        throw "update_state.py failed phase=$Phase ExitCode=$ec"
    }
}

function Write-FailureFile {
    param([string]$Reason)

@"
PROJECT: bia
STEP: STEP_044
RETRY: FIX6
TIME: $(Get-Date -Format o)
STATUS: FAILED

FAILURE_REASON:
$Reason

PYTHON_EXIT_CODE:
$PythonExitCode

LAST_SUCCESSFUL_ACTION:
$LastSuccessfulAction

EXPECTED_OUTPUT:
$ExpectedTsv

PARTIAL_OUTPUTS:
$OutputsDir

NEXT_RECOMMENDED_ACTION:
Upload PROJECT_ROOT\log\fall_bia_STEP_044_campaign_next_batch_RESULT.zip.
"@ | Set-Content -LiteralPath (Join-Path $StepLogDir "FAILURE.txt") -Encoding UTF8
}

try {
    $Python = Find-Python

    Update-State `
        -Phase "start" `
        -Detail "FIX6_start_full_campaign_discovery_ISO_untouched"
    $LastSuccessfulAction = "PROJECT_STATE and STEP_044 marked IN_PROGRESS"

    $BaseIso = "PROJECT_ROOT\BIA_STAGE43T_TITLE_PROMPT_FIX.iso"
    if (-not (Test-Path $BaseIso)) {
        throw "Missing baseline ISO: $BaseIso"
    }

    $hash = Get-FileHash -Algorithm SHA256 -LiteralPath $BaseIso
    "$($hash.Hash)`t$BaseIso" |
        Set-Content -LiteralPath (Join-Path $StepLogDir "hashes.txt") -Encoding UTF8

@"
TIME=$(Get-Date -Format o)
PROJECT_ROOT=$ProjectRoot
LEGACY_ROOT=$LegacyRoot
BASE_ISO=$BaseIso
PYTHON=$Python
"@ | Set-Content -LiteralPath (Join-Path $StepLogDir "environment.txt") -Encoding UTF8

    $LastSuccessfulAction = "Baseline validated"

    # IMPORTANT:
    # Do not use a PowerShell function parameter named $Args.
    # Call Python directly with explicit arguments so every required argv item is present.
    $oldEap = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & $Python (Join-Path $PSScriptRoot "scripts\discover_campaign_fix6.py") `
            --project-root $ProjectRoot `
            --legacy-root $LegacyRoot `
            --out-dir $OutputsDir `
            1> (Join-Path $StepLogDir "stdout.txt") `
            2> (Join-Path $StepLogDir "stderr.txt")

        $PythonExitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $oldEap
    }

    if ($null -eq $PythonExitCode) { $PythonExitCode = 0 }

    if ($PythonExitCode -ne 0) {
        throw "Campaign discovery failed ExitCode=$PythonExitCode. Inspect outputs\candidate_inventory.json, source_code_hits.tsv and source_evidence."
    }

    $LastSuccessfulAction = "Campaign discovery script completed"

    if (-not (Test-Path $ExpectedTsv)) {
        throw "Expected TSV missing: $ExpectedTsv"
    }
    if ((Get-Item $ExpectedTsv).Length -eq 0) {
        throw "Expected TSV is empty: $ExpectedTsv"
    }

    $ReportPath = Join-Path $OutputsDir "campaign_discovery_report.json"
    if (-not (Test-Path $ReportPath)) {
        throw "Missing campaign_discovery_report.json"
    }

    $Report = Get-Content -LiteralPath $ReportPath -Raw -Encoding UTF8 | ConvertFrom-Json

    Update-State `
        -Phase "success" `
        -Detail ("FIX6_selected_" + $Report.selected_source_file + "_units_" + $Report.selected_unit_count)

    $LastSuccessfulAction = "STEP_044 discovery/export VERIFIED"
}
catch {
    $Failed = $true
    $reason = ($_ | Out-String)

    $reason |
        Set-Content -LiteralPath (Join-Path $StepLogDir "stderr_powershell.txt") -Encoding UTF8

    try { Write-FailureFile -Reason $reason } catch {}

    try {
        Update-State `
            -Phase "failure" `
            -Detail "FIX6_failed_discovery_evidence_collected"
    }
    catch {}
}
finally {
    try { Stop-Transcript | Out-Null } catch {}

    # Collect state and all partial results even after discovery failure.
    try {
        if (Test-Path "PROJECT_ROOT\PROJECT_STATE.md") {
            Copy-Item "PROJECT_ROOT\PROJECT_STATE.md" $StepLogDir -Force
        }
        if (Test-Path "PROJECT_ROOT\log\steps\STEP_044.md") {
            Copy-Item "PROJECT_ROOT\log\steps\STEP_044.md" $StepLogDir -Force
        }
        if (Test-Path $ExpectedTsv) {
            Copy-Item $ExpectedTsv $OutputsDir -Force
        }
        if (Test-Path "PROJECT_ROOT\translation\text_master.tsv") {
            Copy-Item "PROJECT_ROOT\translation\text_master.tsv" $OutputsDir -Force
        }
    }
    catch {
        ($_ | Out-String) |
            Set-Content -LiteralPath (Join-Path $StepLogDir "collection_error.txt") -Encoding UTF8
    }

    $zipPath = if ($Failed) { $FailureZip } else { $SuccessZip }

    try {
        if (Test-Path $zipPath) {
            Remove-Item $zipPath -Force
        }

        Compress-Archive `
            -Path (Join-Path $StepLogDir "*") `
            -DestinationPath $zipPath `
            -Force

        if (-not (Test-Path $zipPath)) {
            throw "Result ZIP missing"
        }
        if ((Get-Item $zipPath).Length -eq 0) {
            throw "Result ZIP empty"
        }
    }
    catch {
@"
STEP=STEP_044_FIX6
WORK_FAILED=$Failed
ZIP_TARGET=$zipPath
ZIP_ERROR=$($_ | Out-String)
LOG_FOLDER=$StepLogDir
"@ | Set-Content `
        -LiteralPath (Join-Path $LogsRoot "fall_STEP_044_FIX6_ZIP_CREATION_FAILED.txt") `
        -Encoding UTF8
    }

    Write-Host ""
    if ($Failed) {
        Write-Host "STEP_044 FIX6 FAILED" -ForegroundColor Red
        Write-Host "Upload: $FailureZip"
    }
    else {
        Write-Host "STEP_044 VERIFIED (discovery/export only)" -ForegroundColor Green
        Write-Host "TSV: $ExpectedTsv"
        Write-Host "Upload: $SuccessZip"
    }
}

if ($Failed) { exit 1 }
