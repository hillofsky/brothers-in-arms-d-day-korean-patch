$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

$Root = "PROJECT_ROOT"
$LogRoot = Join-Path $Root "log"
$Step = "STEP_077"
$LogDir = Join-Path $LogRoot $Step
$OutDir = Join-Path $LogDir "outputs"
$ScriptsUsed = Join-Path $LogDir "scripts_used"
$OK = Join-Path $LogRoot "bia_STEP_077_relocation_payload_binding_audit_RESULT.zip"
$FAIL = Join-Path $LogRoot "fall_bia_STEP_077_relocation_payload_binding_audit_RESULT.zip"
$Py = "LOCAL_PATH"
$Failed = $false
$LastAction = "startup"

try {
    New-Item -ItemType Directory -Force -Path $LogRoot,(Join-Path $LogRoot "old"),(Join-Path $LogRoot "steps") | Out-Null
    if (Test-Path -LiteralPath $LogDir) {
        $stamp = Get-Date -Format "yyyyMMdd_HHmmss_fff"
        $archive = Join-Path $LogRoot ("old\" + $stamp)
        New-Item -ItemType Directory -Force -Path $archive | Out-Null
        Move-Item -LiteralPath $LogDir -Destination (Join-Path $archive $Step)
    }
    New-Item -ItemType Directory -Force -Path $LogDir,$OutDir,$ScriptsUsed | Out-Null
    Copy-Item -LiteralPath $PSCommandPath -Destination (Join-Path $ScriptsUsed "run.ps1") -Force
    Copy-Item -Path (Join-Path $PSScriptRoot "scripts\*") -Destination $ScriptsUsed -Force
    Copy-Item -Path (Join-Path $PSScriptRoot "evidence\*") -Destination $ScriptsUsed -Force
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot "STEP_INFO.txt") -Destination $LogDir -Force
    $LastAction = "log directories created; executed scripts copied"
    try { Start-Transcript -LiteralPath (Join-Path $LogDir "run.log") -Force | Out-Null } catch {}

    if (-not (Test-Path -LiteralPath $Py)) { throw "Python executable not found: $Py" }
    & $Py (Join-Path $PSScriptRoot "scripts\update_state.py") --root $Root --phase start --detail "Step077 read-only DSL relocation payload correlation started."
    if ($LASTEXITCODE -ne 0) { throw "state start update failed" }
    $LastAction = "PROJECT_STATE marked IN_PROGRESS"
    Write-Host "[1/3] Collecting original DSL relocation payload fingerprints (32 MDIs)..." -ForegroundColor Cyan
    $oldErrorActionPreference=$ErrorActionPreference
    $ErrorActionPreference="Continue"
    try {
        & $Py (Join-Path $PSScriptRoot "scripts\audit_relocation_payloads.py") `
            --package-root $PSScriptRoot --outdir $OutDir `
            1> (Join-Path $LogDir "stdout.txt") `
            2> (Join-Path $LogDir "stderr.txt")
        $exitCode=$LASTEXITCODE
    } finally { $ErrorActionPreference=$oldErrorActionPreference }
    if ($exitCode -ne 0) { throw "relocation data correlation failed (exit $exitCode)" }
    $LastAction = "32 DSL payload analyses finished"

    $report = Get-Content -LiteralPath (Join-Path $OutDir "step077_report.json") -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($report.status -ne "VERIFIED_PAYLOAD_CORRELATION_DIAGNOSTIC" -or $report.target_mdis -ne 32 -or -not $report.source_iso_preserved) {
        throw "STEP077 report requirements failed"
    }
    & $Py (Join-Path $PSScriptRoot "scripts\update_state.py") --root $Root --phase success --detail ("Read-only 32-DSL payload correlation done; exact C128 matches in other MDIs="+$report.other_mdis_with_exact_c_128_match+"; semantic patch targets not yet verified.")
    if ($LASTEXITCODE -ne 0) { throw "state success update failed" }
    Write-Host "[2/3] Verified diagnostic completed (no ISO change)." -ForegroundColor Green
} catch {
    $Failed = $true
    $reason = $_ | Out-String
    try { New-Item -ItemType Directory -Force -Path $LogDir,$OutDir | Out-Null } catch {}
    @"
STEP=STEP_077
STATUS=FAILED
TIME=$(Get-Date -Format o)
LAST_SUCCESSFUL_ACTION=$LastAction
REASON=$reason
ISO_MODIFIED=NO
NEXT=Upload $FAIL
"@ | Set-Content -LiteralPath (Join-Path $LogDir "FAILURE.txt") -Encoding UTF8
    if (Test-Path -LiteralPath $Py) {
        try { & $Py (Join-Path $PSScriptRoot "scripts\update_state.py") --root $Root --phase failure --detail "STEP077 failed. Read-only; no ISO modification." } catch {}
    }
} finally {
    try { Stop-Transcript | Out-Null } catch {}
    foreach ($p in @((Join-Path $Root "PROJECT_STATE.md"),(Join-Path $LogRoot "steps\STEP_077.md"))) {
        try { if (Test-Path -LiteralPath $p) { Copy-Item -LiteralPath $p -Destination $OutDir -Force } } catch {}
    }
    $result = if ($Failed) { $FAIL } else { $OK }
    try {
        if (Test-Path -LiteralPath $result) { Remove-Item -LiteralPath $result -Force }
        Compress-Archive -Path (Join-Path $LogDir "*") -DestinationPath $result -Force
        if (-not (Test-Path -LiteralPath $result)) { throw "Result ZIP missing" }
    } catch {
        $Failed=$true
        (($_ | Out-String) + "`nLog source: $LogDir") | Set-Content -LiteralPath (Join-Path $LogRoot "fall_STEP_077_ZIP_CREATION_FAILED.txt") -Encoding UTF8
    }
    Write-Host "[3/3] Upload: $result" -ForegroundColor $(if($Failed){"Red"}else{"Green"})
}
if ($Failed) { exit 1 }
