$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)

$ProjectRoot = "PROJECT_ROOT"
$LegacyRoot = "LOCAL_PATH"
$LogsRoot = "PROJECT_ROOT\log"
$StepId = "STEP_044"
$StepLogDir = Join-Path $LogsRoot $StepId
$OutputsDir = Join-Path $StepLogDir "outputs"
$ScriptsUsed = Join-Path $StepLogDir "scripts_used"
$SuccessZip = Join-Path $LogsRoot "bia_STEP_044_campaign_next_batch_RESULT.zip"
$FailureZip = Join-Path $LogsRoot "fall_bia_STEP_044_campaign_next_batch_RESULT.zip"
$ExpectedTsv = Join-Path $ProjectRoot "translation\campaign_next_translation.tsv"

$Failed = $false
$LastSuccessfulAction = "PowerShell startup"
$PythonExitCode = $null

New-Item -ItemType Directory -Force -Path $LogsRoot,$StepLogDir,$OutputsDir,$ScriptsUsed | Out-Null

Copy-Item -LiteralPath $PSCommandPath -Destination (Join-Path $ScriptsUsed "run.ps1") -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot "STEP_INFO.txt") -Destination $StepLogDir -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot "scripts\discover_campaign_fix3.py") -Destination $ScriptsUsed -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot "scripts\update_state.py") -Destination $ScriptsUsed -Force

$Transcript = Join-Path $StepLogDir "run.log"
try { Start-Transcript -LiteralPath $Transcript -Force | Out-Null } catch {}

function Find-Python {
    $Bundled = "LOCAL_PATH"
    if (Test-Path $Bundled) { return $Bundled }
    $Cmd = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($Cmd) { return $Cmd.Source }
    throw "Python runtime not found"
}

function Run-PythonCaptured {
    param(
        [string]$Script,
        [string[]]$Arguments,
        [string]$Stdout,
        [string]$Stderr
    )
    $argList = @($Script) + $Arguments
    $P = Start-Process -FilePath $Python -ArgumentList $argList `
        -Wait -PassThru -NoNewWindow `
        -RedirectStandardOutput $Stdout -RedirectStandardError $Stderr
    return $P.ExitCode
}

function Update-State([string]$Phase,[string]$Detail) {
    $ec = Run-PythonCaptured `
        -Script (Join-Path $PSScriptRoot "scripts\update_state.py") `
        -Arguments @("--root",$ProjectRoot,"--phase",$Phase,"--detail",$Detail) `
        -Stdout (Join-Path $StepLogDir "state_${Phase}_stdout.txt") `
        -Stderr (Join-Path $StepLogDir "state_${Phase}_stderr.txt")
    if ($ec -ne 0) { throw "update_state.py failed in phase=$Phase ExitCode=$ec" }
}

function Write-Failure {
    param([string]$Reason)
    @"
PROJECT: bia
STEP: STEP_044
RETRY: FIX3
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
Do not manually edit discovered translation files before review.
"@ | Set-Content -LiteralPath (Join-Path $StepLogDir "FAILURE.txt") -Encoding UTF8
}

try {
    $Python = Find-Python

    Update-State "start" "FIX3 started: full PROJECT_ROOT + legacy structured-data scan; ISO untouched."
    $LastSuccessfulAction = "PROJECT_STATE.md / STEP_044.md marked IN_PROGRESS"

    if (-not (Test-Path $ProjectRoot)) { throw "Project root missing: $ProjectRoot" }
    $BaseIso = Join-Path $ProjectRoot "BIA_STAGE43T_TITLE_PROMPT_FIX.iso"
    if (-not (Test-Path $BaseIso)) { throw "Stage43T baseline missing: $BaseIso" }

    @"
TIME=$(Get-Date -Format o)
PROJECT_ROOT=$ProjectRoot
LEGACY_ROOT=$LegacyRoot
LOG_ROOT=$LogsRoot
BASE_ISO=$BaseIso
PYTHON=$Python
"@ | Set-Content -LiteralPath (Join-Path $StepLogDir "environment.txt") -Encoding UTF8

    $h = Get-FileHash -Algorithm SHA256 -LiteralPath $BaseIso
    "$($h.Hash)`t$BaseIso" | Set-Content -LiteralPath (Join-Path $StepLogDir "hashes.txt") -Encoding UTF8
    $LastSuccessfulAction = "Baseline existence/hash validated"

    $PythonExitCode = Run-PythonCaptured `
        -Script (Join-Path $PSScriptRoot "scripts\discover_campaign_fix3.py") `
        -Arguments @("--project-root",$ProjectRoot,"--legacy-root",$LegacyRoot,"--out-dir",$OutputsDir) `
        -Stdout (Join-Path $StepLogDir "stdout.txt") `
        -Stderr (Join-Path $StepLogDir "stderr.txt")

    if ($PythonExitCode -ne 0) {
        throw "discover_campaign_fix3.py failed. ExitCode=$PythonExitCode. See stderr.txt and candidate_inventory.json."
    }
    $LastSuccessfulAction = "Next untranslated campaign group selected and TSV generated"

    if (-not (Test-Path $ExpectedTsv)) { throw "Expected TSV missing: $ExpectedTsv" }
    if ((Get-Item $ExpectedTsv).Length -eq 0) { throw "Expected TSV is empty: $ExpectedTsv" }

    $ReportPath = Join-Path $OutputsDir "campaign_discovery_report.json"
    if (-not (Test-Path $ReportPath)) { throw "campaign_discovery_report.json missing" }
    $Report = Get-Content -LiteralPath $ReportPath -Raw -Encoding UTF8 | ConvertFrom-Json

    Copy-Item -LiteralPath $ExpectedTsv -Destination $OutputsDir -Force
    if (Test-Path (Join-Path $ProjectRoot "translation\text_master.tsv")) {
        Copy-Item -LiteralPath (Join-Path $ProjectRoot "translation\text_master.tsv") -Destination $OutputsDir -Force
    }

    $Detail = "FIX3 selected $($Report.selected_source_file), $($Report.selected_unit_count) units; translation TSV created; ISO untouched."
    Update-State "success" $Detail
    $LastSuccessfulAction = "STEP_044 discovery/export marked VERIFIED"

} catch {
    $Failed = $true
    $Reason = ($_ | Out-String)
    $Reason | Set-Content -LiteralPath (Join-Path $StepLogDir "stderr_powershell.txt") -Encoding UTF8
    try { Write-Failure $Reason } catch {}
    try { Update-State "failure" ("FIX3 failed after: " + $LastSuccessfulAction) } catch {}
} finally {
    try { Stop-Transcript | Out-Null } catch {}

    try {
        if (Test-Path (Join-Path $ProjectRoot "PROJECT_STATE.md")) {
            Copy-Item -LiteralPath (Join-Path $ProjectRoot "PROJECT_STATE.md") -Destination $StepLogDir -Force
        }
        if (Test-Path (Join-Path $LogsRoot "steps\STEP_044.md")) {
            Copy-Item -LiteralPath (Join-Path $LogsRoot "steps\STEP_044.md") -Destination $StepLogDir -Force
        }
    } catch {
        ($_ | Out-String) | Set-Content -LiteralPath (Join-Path $StepLogDir "collection_error.txt") -Encoding UTF8
    }

    $ZipPath = if ($Failed) { $FailureZip } else { $SuccessZip }
    try {
        if (Test-Path $ZipPath) { Remove-Item $ZipPath -Force }
        Compress-Archive -Path (Join-Path $StepLogDir "*") -DestinationPath $ZipPath -Force
        if (-not (Test-Path $ZipPath)) { throw "Result ZIP creation failed" }
        if ((Get-Item $ZipPath).Length -eq 0) { throw "Result ZIP is empty" }
    } catch {
        @"
STEP=STEP_044
WORK_FAILED=$Failed
ZIP_TARGET=$ZipPath
ZIP_ERROR=$($_ | Out-String)
LOG_FOLDER=$StepLogDir
"@ | Set-Content -LiteralPath (Join-Path $LogsRoot "fall_STEP_044_ZIP_CREATION_FAILED.txt") -Encoding UTF8
    }

    Write-Host ""
    if ($Failed) {
        Write-Host "STEP_044 FIX3 FAILED" -ForegroundColor Red
        Write-Host "Upload: $FailureZip"
    } else {
        Write-Host "STEP_044 VERIFIED (discovery/export only)" -ForegroundColor Green
        Write-Host "TSV: $ExpectedTsv"
        Write-Host "Upload: $SuccessZip"
    }
}

if ($Failed) { exit 1 }
