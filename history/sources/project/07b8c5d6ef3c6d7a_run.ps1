# BIA STEP 083 FIX1 - diagnostic-only, no ISO mutation. Windows PowerShell 5.1.
# Every actual run produces an isolated log directory and an uploadable ZIP.
[CmdletBinding()]
param([switch]$NoSavedataCopy)
$ErrorActionPreference='Stop'
Set-StrictMode -Version 2.0
try { [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false) } catch {}
$env:PYTHONIOENCODING='utf-8'
$env:PYTHONUTF8='1'
$Root='PROJECT_ROOT'
$LogRoot=Join-Path $Root 'log'
$Step='STEP_083_FIX1'
$Exe='LOCAL_PATH'
$ISO=Join-Path $Root 'BIA_STAGE79_COMPILED967_STRUCTURAL_TEST.iso'
$ExpectedSha='CA320D514C32D34767E7255EA3079F7449783CDB2B98EC49797A87BDD69544D9'
$Py='LOCAL_PATH'
$RunId='{0}_{1}' -f (Get-Date -Format 'yyyyMMdd_HHmmss_fff'), $PID
$StepDir=Join-Path (Join-Path $LogRoot $Step) $RunId
$Out=Join-Path $StepDir 'outputs'
$Scripts=Join-Path $StepDir 'scripts_used'
$Phase='setup'; $Failed=$true; $Port=$null; $LaunchPid=$null; $ListenerPid=$null
$LaunchCreation=$null; $ConfigPath=$null; $Memstick=$null; $TranscriptStarted=$false
$FinalZip=$null; $ZipError=$null; $SourceShaAfter=$null

function IsPortFree([int]$Number) {
    $s=$null
    try { $s=[Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback,$Number); $s.Start(); return $true }
    catch { return $false }
    finally { if ($null -ne $s) { try { $s.Stop() } catch {} } }
}
function FindPort {
    foreach ($n in 26420..26439) { if (IsPortFree $n) { return [int]$n } }
    throw 'No free dedicated debugger port in 26420..26439'
}
function GetListener([int]$Number) {
    try {
        $rows=@(Get-NetTCPConnection -LocalPort $Number -State Listen -ErrorAction SilentlyContinue)
        $ids=@($rows | Where-Object { $_.LocalAddress -eq '127.0.0.1' -or $_.LocalAddress -eq '0.0.0.0' -or $_.LocalAddress -eq '::1' -or $_.LocalAddress -eq '::' } | Select-Object -ExpandProperty OwningProcess -Unique)
        if ($ids.Count -eq 1) { return [int]$ids[0] }
        if ($ids.Count -gt 1) { throw "Ambiguous debugger port listener IDs: $($ids -join ',')" }
    } catch { if ($_.Exception.Message -like 'Ambiguous*') { throw } }
    $ids=@()
    foreach ($line in (& netstat.exe -ano -p tcp)) {
        if ($line -match "^\s*TCP\s+\S+:$Number\s+\S+\s+LISTENING\s+(\d+)\s*$") { $ids+= [int]$Matches[1] }
    }
    $ids=@($ids | Select-Object -Unique)
    if ($ids.Count -gt 1) { throw 'Ambiguous debugger port listener detected by netstat' }
    if ($ids.Count -eq 1) { return [int]$ids[0] }
    return $null
}
function OwnerVerified([int]$CheckPid) {
    if ($CheckPid -le 0 -or !$ConfigPath -or !$Memstick -or !$LaunchCreation -or !$LaunchPid) { return $false }
    if ($CheckPid -ne $LaunchPid) { return $false } # never use another PPSSPP window
    try { $proc=Get-CimInstance Win32_Process -Filter "ProcessId=$CheckPid" -ErrorAction Stop }
    catch { return $false }
    if ($null -eq $proc) { return $false }
    $cmd=[string]$proc.CommandLine
    $path=[string]$proc.ExecutablePath
    if (!$path -or !$cmd) { return $false }
    $time=[string]$proc.CreationDate
    return (
        [string]::Equals($path,$Exe,[StringComparison]::OrdinalIgnoreCase) -and
        [string]::Equals($time,$LaunchCreation,[StringComparison]::OrdinalIgnoreCase) -and
        $cmd.IndexOf($ISO,[StringComparison]::OrdinalIgnoreCase) -ge 0 -and
        $cmd.IndexOf($ConfigPath,[StringComparison]::OrdinalIgnoreCase) -ge 0 -and
        $cmd.IndexOf($Memstick,[StringComparison]::OrdinalIgnoreCase) -ge 0
    )
}
function AssertOwnedListener {
    if (!$Port -or !$LaunchPid) { throw 'Debugger ownership not initialized' }
    $actual=GetListener ([int]$Port)
    if (!$actual -or [int]$actual -ne [int]$LaunchPid -or !(OwnerVerified ([int]$actual))) {
        throw "Debugger listener no longer owned: expected=$LaunchPid actual=$actual port=$Port"
    }
    $script:ListenerPid=[int]$actual
}
function State([string]$Mode,[string]$Detail) {
    if (!(Test-Path -LiteralPath $Py -PathType Leaf)) { return }
    & $Py (Join-Path $PSScriptRoot 'scripts\update_state.py') --root $Root --phase $Mode --detail $Detail --runid $RunId
    if ($LASTEXITCODE -ne 0) { throw "State updater failed: $Mode (exit=$LASTEXITCODE)" }
}
function AsJson($Object, [string]$File) {
    $Object | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $File -Encoding UTF8
}
try {
    New-Item -ItemType Directory -Path $Out,$Scripts -Force | Out-Null
    # Copy the scripts/reference that were really executed. Keep user saves outside the upload ZIP.
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'scripts\live_font_probe.py') -Destination $Scripts -Force
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'scripts\stage071_known_good.py') -Destination $Scripts -Force
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'scripts\update_state.py') -Destination $Scripts -Force
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'reference\stage79_mission2_expected.json') -Destination $Scripts -Force
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'reference\step082_report.json') -Destination $Scripts -Force
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'reference\second_mission_font_audit.json') -Destination $Scripts -Force
    Copy-Item -LiteralPath $PSCommandPath -Destination (Join-Path $Scripts 'run.ps1') -Force
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'README.md') -Destination $StepDir -Force
    try { Start-Transcript -Path (Join-Path $StepDir 'run.log') -Force | Out-Null; $TranscriptStarted=$true } catch {}
    Write-Host "BIA STEP083 FIX1: isolated diagnostic run $RunId" -ForegroundColor Cyan
    $Phase='preflight'
    if (!(Test-Path -LiteralPath $ISO -PathType Leaf)) { throw "Stage79 ISO missing: $ISO" }
    if (!(Test-Path -LiteralPath $Exe -PathType Leaf)) { throw "PPSSPP executable missing: $Exe" }
    if (!(Test-Path -LiteralPath $Py -PathType Leaf)) {
        $pythonCommand=Get-Command 'python.exe' -ErrorAction SilentlyContinue
        if ($null -eq $pythonCommand) { throw "Python missing: $Py" }
        $Py=$pythonCommand.Source
    }
    $sha=(Get-FileHash -LiteralPath $ISO -Algorithm SHA256).Hash.ToUpperInvariant()
    if ($sha -ne $ExpectedSha) { throw "Stage79 SHA-256 mismatch: actual=$sha expected=$ExpectedSha" }
    AsJson ([ordered]@{step=$Step;run_id=$RunId;iso=$ISO;iso_sha256=$sha;ppsspp_exe=$Exe;ppsspp_sha256=(Get-FileHash -LiteralPath $Exe -Algorithm SHA256).Hash;python=$Py;iso_mutation=$false}) (Join-Path $Out 'preflight_identity.json')
    State 'start' "Stage79 verified, collecting isolated mission2 repeated-angle-bracket evidence (run=$RunId)."

    $Phase='port_and_memstick'
    $Port=FindPort
    $ConfigPath=Join-Path $StepDir 'ppsspp_step083_fix1_append.ini'
    $Memstick=Join-Path $StepDir 'STEP_083_FIX1_ISOLATED_MEMSTICK'
    New-Item -ItemType Directory -Path (Join-Path $Memstick 'PSP\SAVEDATA'),(Join-Path $Memstick 'PSP\SYSTEM') -Force | Out-Null
    $SaveSource=$null
    if (!$NoSavedataCopy) {
        $Sources=@(
            "$env:USERPROFILE\Documents\PPSSPP\PSP\SAVEDATA",
            "$env:APPDATA\PPSSPP\PSP\SAVEDATA",
            "$(Split-Path -Parent $Exe)\memstick\PSP\SAVEDATA",
            "$env:USERPROFILE\Documents\PSP\SAVEDATA"
        )
        foreach ($candidate in $Sources) {
            if (Test-Path -LiteralPath $candidate -PathType Container) {
                $dirs=@(Get-ChildItem -LiteralPath $candidate -Directory -ErrorAction SilentlyContinue)
                if ($dirs.Count -gt 0) { $SaveSource=$candidate; break }
            }
        }
        if ($SaveSource) {
            Copy-Item -Path (Join-Path $SaveSource '*') -Destination (Join-Path $Memstick 'PSP\SAVEDATA') -Recurse -Force
            Write-Host 'Existing save data copied into isolated test memstick (original untouched).' -ForegroundColor Cyan
        }
    }
    AsJson ([ordered]@{source_savedata=$SaveSource;destination=$Memstick;savedata_copied=[bool]$SaveSource}) (Join-Path $Out 'save_isolation.json')
    @"
[General]
RemoteISOPort = $Port
RemoteDebuggerOnStartup = True
RemoteDebuggerLocal = True
[Graphics]
SoftwareRenderer = False
"@ | Set-Content -LiteralPath $ConfigPath -Encoding ASCII

    $Phase='launch'
    $arguments=@("--memstick=`"$Memstick`"", "--appendconfig=`"$ConfigPath`"", "`"$ISO`"")
    $child=Start-Process -FilePath $Exe -ArgumentList $arguments -PassThru
    $LaunchPid=[int]$child.Id
    $p0=Get-CimInstance Win32_Process -Filter "ProcessId=$LaunchPid" -ErrorAction Stop
    if (!$p0) { throw 'Could not read launched PPSSPP process identity' }
    $LaunchCreation=[string]$p0.CreationDate
    Write-Host "Dedicated PPSSPP launch PID=$LaunchPid PORT=$Port" -ForegroundColor Green
    $Phase='ownership'
    for ($i=0; $i -lt 120; $i++) {
        $listener=GetListener ([int]$Port)
        if ($listener) { break }
        $child.Refresh()
        if ($child.HasExited) { throw 'Isolated PPSSPP exited before debugger startup' }
        Start-Sleep -Milliseconds 500
    }
    AssertOwnedListener
    AsJson ([ordered]@{dedicated_port=$Port;launch_pid=$LaunchPid;verified_listener_pid=$ListenerPid;launch_creation=$LaunchCreation;owned=$true;exe=$Exe;iso=$ISO;iso_sha256=$sha;appendconfig=$ConfigPath;memstick=$Memstick;verified_at=(Get-Date -Format o)}) (Join-Path $Out 'session_provenance.json')

    Write-Host ''
    Write-Host '==============================================================' -ForegroundColor Cyan
    Write-Host 'Use ONLY the newly launched PPSSPP window.' -ForegroundColor Cyan
    Write-Host 'Navigate MANUALLY to mission 2 where Korean renders as > > >.' -ForegroundColor Yellow
    Write-Host 'When the broken text is clearly visible, return to this window.' -ForegroundColor Yellow
    Write-Host 'Press Enter to pause/capture RAM (32 MiB) and VRAM (2 previews).' -ForegroundColor Yellow
    Write-Host 'Type CANCEL to abort. Other PPSSPP instances are not touched.' -ForegroundColor Yellow
    Write-Host '==============================================================' -ForegroundColor Cyan
    $choice=Read-Host 'Capture the broken mission 2 frame [Enter/CANCEL]'
    if ($choice -match '^(?i:CANCEL|EXIT|Q)$') { throw 'USER_CANCELLED_BEFORE_SNAPSHOT' }

    $Phase='snapshot'
    AssertOwnedListener
    $oldPref=$ErrorActionPreference; $ErrorActionPreference='Continue'
    try {
        & $Py (Join-Path $PSScriptRoot 'scripts\live_font_probe.py') --port $Port --outdir $Out --expected (Join-Path $PSScriptRoot 'reference\stage79_mission2_expected.json') --expected-pid $ListenerPid 1> (Join-Path $StepDir 'stdout.txt') 2> (Join-Path $StepDir 'stderr.txt')
        $PythonExitCode=$LASTEXITCODE
    } finally { $ErrorActionPreference=$oldPref }
    if ($PythonExitCode -ne 0) { throw "Python live snapshot failed with code $PythonExitCode" }
    $Report=Get-Content -LiteralPath (Join-Path $Out 'step083_live_font_report.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($Report.status -ne 'VERIFIED_LIVE_SNAPSHOT_COLLECTED') { throw "Unexpected snapshot report status: $($Report.status)" }
    AssertOwnedListener
    $Phase='postflight'
    $SourceShaAfter=(Get-FileHash -LiteralPath $ISO -Algorithm SHA256).Hash.ToUpperInvariant()
    if ($SourceShaAfter -ne $ExpectedSha) { throw "SOURCE_ISO_CHANGED unexpected hash $SourceShaAfter" }
    State 'success' "32MiB live PSP RAM + 2 VRAM previews captured (run=$RunId). No glyph-render fix applied; analyze report and screenshot next."
    $Phase='complete'; $Failed=$false
    Write-Host 'Snapshot captured. This is diagnostic evidence, NOT a verified Korean-font fix.' -ForegroundColor Green
} catch {
    $Failed=$true
    $msg=$_ | Out-String
    $failure="STEP: STEP_083_FIX1`r`nSTATUS: FAILED`r`nTIME: $(Get-Date -Format o)`r`nPHASE: $Phase`r`nPORT: $Port`r`nLAUNCH_PID: $LaunchPid`r`nLISTENER_PID: $ListenerPid`r`nREASON:`r`n$msg"
    try { New-Item -ItemType Directory -Path $StepDir -Force | Out-Null; Set-Content -LiteralPath (Join-Path $StepDir 'FAILURE.txt') -Value $failure -Encoding UTF8 } catch { Write-Host $failure -ForegroundColor Red }
    try { State 'failure' "FIX1 failed at $Phase (run=$RunId), original Stage79 ISO unchanged unless hash postflight flags otherwise." } catch { Write-Host "State update failed: $_" -ForegroundColor Yellow }
} finally {
    # Stop ONLY the newly launched exact process. No process-name-wide termination.
    if ($LaunchPid) {
        try {
            if (OwnerVerified ([int]$LaunchPid)) { Stop-Process -Id ([int]$LaunchPid) -Force -ErrorAction SilentlyContinue }
            else { Write-Host "Not terminating unverified process PID=$LaunchPid" -ForegroundColor Yellow }
        } catch { Write-Host "Cleanup warning: $_" -ForegroundColor Yellow }
    }
    try { if (Test-Path -LiteralPath $ISO -PathType Leaf) { $SourceShaAfter=(Get-FileHash -LiteralPath $ISO -Algorithm SHA256).Hash.ToUpperInvariant() } } catch {}
    if ($null -ne $SourceShaAfter -and $SourceShaAfter -ne $ExpectedSha) {
        $Failed=$true
        try { Add-Content -LiteralPath (Join-Path $StepDir 'FAILURE.txt') -Value "`r`nSOURCE_ISO_HASH_MISMATCH postflight=$SourceShaAfter" -Encoding UTF8 } catch {}
    }
    try { AsJson ([ordered]@{expected_iso_sha256=$ExpectedSha;postflight_iso_sha256=$SourceShaAfter;unchanged=($SourceShaAfter -eq $ExpectedSha);checked_at=(Get-Date -Format o);iso_write_attempted=$false}) (Join-Path $Out 'postflight_identity.json') } catch {}
    try {
        if ($Memstick -and (Test-Path -LiteralPath $Memstick)) {
            $manifest=@(Get-ChildItem -LiteralPath $Memstick -Recurse -File -ErrorAction SilentlyContinue | ForEach-Object { [ordered]@{relative_path=$_.FullName.Substring($Memstick.Length);length=$_.Length} })
            AsJson $manifest (Join-Path $Out 'test_memstick_manifest.json')
        }
    } catch {}
    try {
        foreach ($file in @((Join-Path $Root 'PROJECT_STATE.md'), (Join-Path $LogRoot 'steps\STEP_083_FIX1.md'))) {
            if (Test-Path -LiteralPath $file -PathType Leaf) { Copy-Item -LiteralPath $file -Destination $Out -Force }
        }
    } catch {}
    if ($TranscriptStarted) { try { Stop-Transcript | Out-Null } catch {} }
    try {
        $Phase='zip_results'
        $ZipName=if ($Failed) { "fall_bia_STEP_083_FIX1_live_font_probe_$RunId.zip" } else { "bia_STEP_083_FIX1_live_font_probe_$RunId.zip" }
        $FinalZip=Join-Path $LogRoot $ZipName
        $ZipContents=Join-Path $StepDir 'zip_contents'
        New-Item -ItemType Directory -Path (Join-Path $ZipContents 'outputs'), (Join-Path $ZipContents 'scripts_used') -Force | Out-Null
        Copy-Item -Path (Join-Path $Out '*') -Destination (Join-Path $ZipContents 'outputs') -Recurse -Force -ErrorAction SilentlyContinue
        Copy-Item -Path (Join-Path $Scripts '*') -Destination (Join-Path $ZipContents 'scripts_used') -Recurse -Force -ErrorAction SilentlyContinue
        foreach ($name in @('README.md','run.log','stdout.txt','stderr.txt','FAILURE.txt','PROJECT_STATE_BEFORE_FIX1.md','ppsspp_step083_fix1_append.ini')) {
            $src=Join-Path $StepDir $name
            if (Test-Path -LiteralPath $src -PathType Leaf) { Copy-Item -LiteralPath $src -Destination $ZipContents -Force }
        }
        Compress-Archive -Path (Join-Path $ZipContents '*') -DestinationPath $FinalZip -CompressionLevel Optimal -Force
        Write-Host "RESULT ZIP TO UPLOAD: $FinalZip" -ForegroundColor $(if ($Failed) {'Red'} else {'Green'})
    } catch {
        $ZipError=$_ | Out-String
        Write-Host "ZIP creation failed: $ZipError" -ForegroundColor Red
        try { Set-Content -LiteralPath (Join-Path $StepDir 'ZIP_FAILURE.txt') -Value $ZipError -Encoding UTF8 } catch {}
    }
}
if ($Failed -or $ZipError) { exit 1 }
exit 0
