# BIA STEP087 — evidence-backed cleanup only, read-only game/ISO diagnostic
# Windows PowerShell 5.1. All results (including failures) are zipped to PROJECT_ROOT\log.
[CmdletBinding()]
param()
$ErrorActionPreference='Stop'
Set-StrictMode -Version 2.0
try { [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false) } catch {}
$env:PYTHONUTF8='1'
$env:PYTHONIOENCODING='utf-8'
$Root='PROJECT_ROOT'; $LogRoot=Join-Path $Root 'log'
$RunId='{0}_{1}' -f (Get-Date -Format 'yyyyMMdd_HHmmss_fff'),$PID
$Folder=Join-Path (Join-Path $LogRoot 'STEP_087') $RunId
$Out=Join-Path $Folder 'outputs';$Used=Join-Path $Folder 'scripts_used'
$Phase='init';$Fail=$true;$Started=$false;$ErrorReport=$null
$ResultZip=$null;$Py=$null
try {
    New-Item -ItemType Directory -Force -Path $Out,$Used | Out-Null
    foreach($name in @('run.ps1','README.md')) {
        Copy-Item -LiteralPath (Join-Path $PSScriptRoot $name) -Destination (Join-Path $Used $name) -Force
    }
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'scripts\diagnose_and_clean.py') -Destination (Join-Path $Used 'diagnose_and_clean.py') -Force
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'reference\old_package_hashes.json') -Destination (Join-Path $Used 'old_package_hashes.json') -Force
    Start-Transcript -Path (Join-Path $Folder 'run.log') -Force | Out-Null;$Started=$true
    Write-Host "BIA STEP087: conservative disk cleanup + STEP086 offline analysis; run=$RunId" -ForegroundColor Cyan
    $Phase='preflight'
    if(!(Test-Path -LiteralPath $LogRoot -PathType Container)){throw "Missing BIA log folder: $LogRoot"}
    $Py='LOCAL_PATH'
    if(!(Test-Path -LiteralPath $Py -PathType Leaf)){
        $cmd=Get-Command 'python.exe' -ErrorAction SilentlyContinue
        if($null -eq $cmd){throw 'Python executable missing at the known location and PATH'}
        $Py=[string]$cmd.Source
    }
    $Phase='cleanup_and_trace_analysis'
    & $Py (Join-Path $PSScriptRoot 'scripts\diagnose_and_clean.py') --root $Root --manifest (Join-Path $PSScriptRoot 'reference\old_package_hashes.json') --out $Out 2>&1 | Tee-Object -FilePath (Join-Path $Folder 'stdout.txt')
    if($LASTEXITCODE -ne 0){throw "Python analysis exited with code $LASTEXITCODE"}
    $Phase='project_state_log'
    $md=Join-Path $Root 'PROJECT_STATE.md'
    if(Test-Path -LiteralPath $md -PathType Leaf){
        Copy-Item -LiteralPath $md -Destination (Join-Path $Folder 'PROJECT_STATE_BEFORE_STEP087.md')
        $marker='## STEP_087 Offline trace analysis and safe cleanup'
        $text=Get-Content -LiteralPath (Join-Path $Out 'STEP_087.md') -Raw -Encoding UTF8
        if(!((Get-Content -LiteralPath $md -Raw -Encoding UTF8).Contains($marker))){
            Add-Content -LiteralPath $md -Value ("`r`n<!-- STEP_087_MANAGED_BEGIN -->`r`n"+$marker+"`r`n"+$text+"`r`n<!-- STEP_087_MANAGED_END -->`r`n") -Encoding UTF8
        }
        Copy-Item -LiteralPath $md -Destination (Join-Path $Out 'PROJECT_STATE.md') -Force
    }
    $Phase='done'; $Fail=$false
} catch {
    $Fail=$true
    $ErrorReport = $_ | Out-String
    Write-Host "STEP087 FAILED at phase=$Phase`: $ErrorReport" -ForegroundColor Red
    try {
        "phase=$Phase`r`n$ErrorReport`r`n" | Set-Content -LiteralPath (Join-Path $Folder 'FAILURE.txt') -Encoding UTF8
    } catch {}
} finally {
    if($Started){try{Stop-Transcript | Out-Null}catch{}}
    try {
        if(!(Test-Path -LiteralPath $LogRoot -PathType Container)){
            New-Item -ItemType Directory -Force -Path $LogRoot | Out-Null
        }
        $zipName=if($Fail){"fall_bia_STEP_087_trace_cleanup_${RunId}.zip"}else{"bia_STEP_087_trace_cleanup_${RunId}.zip"}
        $ResultZip=Join-Path $LogRoot $zipName
        # Compress single run folder's files; no second large staging copy.
        $items=@(Get-ChildItem -LiteralPath $Folder -Force | Select-Object -ExpandProperty FullName)
        if($items.Count -gt 0){Compress-Archive -LiteralPath $items -DestinationPath $ResultZip -CompressionLevel Optimal -Force}
        # Verify ZIP entries and CRC with Python's standard library (available on success).
        if($Py -and (Test-Path -LiteralPath $Py -PathType Leaf)){
            & $Py -c 'import sys,zipfile; z=zipfile.ZipFile(sys.argv[1]); f=z.testzip(); z.close(); sys.exit(0 if f is None else 1)' $ResultZip
            if($LASTEXITCODE -ne 0){throw "Created result ZIP failed CRC check: $ResultZip"}
        }
        Write-Host "UPLOAD THIS ZIP: $ResultZip" -ForegroundColor $(if($Fail){'Red'}else{'Green'})
    } catch {
        Write-Host "ZIP CREATION/VALIDATION FAILED: $_" -ForegroundColor Red
        $Fail=$true
        try{Set-Content -LiteralPath (Join-Path $Folder 'ZIP_FAILURE.txt') -Value ($_|Out-String) -Encoding UTF8}catch{}
    }
}
if($Fail){exit 1}
exit 0
