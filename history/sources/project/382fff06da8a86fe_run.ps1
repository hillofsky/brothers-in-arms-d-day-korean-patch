# BIA STEP084: one-ZIP offline RAM forensics; Windows PowerShell 5.1.
# Does NOT launch/control PPSSPP, modify an ISO, or include RAM/saves in result.
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2
try { [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false) } catch {}
$env:PYTHONUTF8='1'
$env:PYTHONIOENCODING='utf-8'
$Root='PROJECT_ROOT'
$LogRoot=Join-Path $Root 'log'
$Downloads=Join-Path $env:USERPROFILE 'Downloads'
$SourceName='bia_STEP_083_FIX1_live_font_probe_20261008_181126_131_15568.zip'
$ExpectedZipSha='0398fced4d6d2923edda750f47924cfcc37652045d511daf890ccaf468c98e18'
$RunId=('{0}_{1}' -f (Get-Date -Format 'yyyyMMdd_HHmmss_fff'), $PID)
$Folder=Join-Path (Join-Path $LogRoot 'STEP_084') $RunId
$Outputs=Join-Path $Folder 'outputs'
$Used=Join-Path $Folder 'scripts_used'
$TempPackage=Join-Path $Folder 'zip_contents'
$Phase='initialization'
$Failure=$true
$Source=$null
$FinalZip=$null
$TranscriptStarted=$false
$BackupCreated=$false
try {
    if(!(Test-Path -LiteralPath $Root -PathType Container)) { throw "BIA project directory missing: $Root" }
    New-Item -ItemType Directory -Path $Outputs,$Used -Force | Out-Null
    Copy-Item -LiteralPath $PSCommandPath -Destination (Join-Path $Used 'run.ps1') -Force
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'scripts\forensics.py') -Destination $Used -Force
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'scripts\update_state.py') -Destination $Used -Force
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'reference\stage79_mission2_expected.json') -Destination $Used -Force
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'README.md') -Destination $Folder -Force
    try { Start-Transcript -Path (Join-Path $Folder 'run.log') -Force | Out-Null; $TranscriptStarted=$true } catch {}
    Write-Host 'BIA STEP084: offline-only RAM forensic analysis' -ForegroundColor Cyan
    $Phase='locate_result_zip'
    $Candidates=@((Join-Path $LogRoot $SourceName),(Join-Path $Downloads $SourceName))
    foreach($item in $Candidates) { if(Test-Path -LiteralPath $item -PathType Leaf){$Source=$item;break} }
    if(!$Source) { throw "STEP083 FIX1 result ZIP not found in PROJECT_ROOT\log or Downloads: $SourceName" }
    $Phase='verify_source_zip'
    $GotSha=(Get-FileHash -LiteralPath $Source -Algorithm SHA256).Hash.ToLowerInvariant()
    if($GotSha -ne $ExpectedZipSha){throw "STEP083 evidence SHA256 mismatch, refusing wrong ZIP: $GotSha"}
    $pythonPinned='LOCAL_PATH'
    $Py=$pythonPinned
    if(!(Test-Path -LiteralPath $Py -PathType Leaf)){
        $PyCmd=Get-Command 'python.exe' -ErrorAction SilentlyContinue
        if(!$PyCmd){throw "Python not found at pinned path or PATH. Expected: $pythonPinned"}
        $Py=$PyCmd.Source
    }
    $Phase='analyze_ram'
    & $Py (Join-Path $PSScriptRoot 'scripts\forensics.py') --input $Source --expected (Join-Path $PSScriptRoot 'reference\stage79_mission2_expected.json') --outdir $Outputs 1> (Join-Path $Folder 'stdout.txt') 2> (Join-Path $Folder 'stderr.txt')
    if($LASTEXITCODE -ne 0){throw "Forensics failed (Python exit $LASTEXITCODE). Check stdout/stderr."}
    $Report=Get-Content -LiteralPath (Join-Path $Outputs 'step084_offline_report.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    if($Report.status -ne 'VERIFIED_OFFLINE_MEMORY_CONSISTENCY'){throw "Unexpected offline report status: $($Report.status)"}
    $Phase='append_state'
    & $Py (Join-Path $PSScriptRoot 'scripts\update_state.py') --root $Root --runid $RunId --phase success --run-dir $Folder
    if($LASTEXITCODE -ne 0){throw "Could not safely update PROJECT_STATE.md"}
    Copy-Item -LiteralPath (Join-Path $Root 'PROJECT_STATE.md') -Destination (Join-Path $Outputs 'PROJECT_STATE.md') -Force
    $StepFile=Join-Path $LogRoot 'steps\STEP_084.md'
    if(Test-Path -LiteralPath $StepFile){Copy-Item -LiteralPath $StepFile -Destination (Join-Path $Outputs 'STEP_084.md') -Force}
    $Phase='completed'
    $Failure=$false
    Write-Host 'STEP084: offline evidence checks completed. Rendering defect remains UNRESOLVED.' -ForegroundColor Green
} catch {
    $Reason=$_ | Out-String
    Write-Host "STEP084 error at ${Phase}: $Reason" -ForegroundColor Red
    try{
        New-Item -ItemType Directory -Path $Folder -Force | Out-Null
        "STEP: STEP_084`r`nSTATUS: FAILED`r`nPHASE: $Phase`r`nTIME: $(Get-Date -Format o)`r`nSOURCE: $Source`r`nREASON:`r`n$Reason" | Set-Content -LiteralPath (Join-Path $Folder 'FAILURE.txt') -Encoding UTF8
    }catch{}
    if($Phase -eq 'append_state'){
        # State update failure should never be misreported as visual verification.
        Write-Host 'Forensic report may exist; state update failed. No ISO changes.' -ForegroundColor Yellow
    }
} finally {
    if($TranscriptStarted){try{Stop-Transcript | Out-Null}catch{}}
    try{
        $Phase='package_result'
        New-Item -ItemType Directory -Path (Join-Path $TempPackage 'outputs'),(Join-Path $TempPackage 'scripts_used') -Force | Out-Null
        if(Test-Path -LiteralPath $Outputs){Copy-Item -Path (Join-Path $Outputs '*') -Destination (Join-Path $TempPackage 'outputs') -Recurse -Force -ErrorAction SilentlyContinue}
        if(Test-Path -LiteralPath $Used){Copy-Item -Path (Join-Path $Used '*') -Destination (Join-Path $TempPackage 'scripts_used') -Recurse -Force -ErrorAction SilentlyContinue}
        foreach($file in @('README.md','FAILURE.txt','stdout.txt','stderr.txt','run.log','PROJECT_STATE_BEFORE_STEP084.md')){
            $Here=Join-Path $Folder $file
            if(Test-Path -LiteralPath $Here -PathType Leaf){Copy-Item -LiteralPath $Here -Destination $TempPackage -Force}
        }
        $ZipName=if($Failure){'fall_bia_STEP_084_offline_font_forensics_'+$RunId+'.zip'}else{'bia_STEP_084_offline_font_forensics_'+$RunId+'.zip'}
        $FinalZip=Join-Path $LogRoot $ZipName
        Compress-Archive -Path (Join-Path $TempPackage '*') -DestinationPath $FinalZip -Force -CompressionLevel Optimal
        Write-Host "UPLOAD THIS RESULT ZIP: $FinalZip" -ForegroundColor $(if($Failure){'Yellow'}else{'Green'})
    }catch{
        Write-Host "Result ZIP creation failed: $_" -ForegroundColor Red
        $Failure=$true
        try{Set-Content -LiteralPath (Join-Path $Folder 'ZIP_FAILURE.txt') -Value ($_|Out-String) -Encoding UTF8}catch{}
    }
}
if($Failure){exit 1}
exit 0
