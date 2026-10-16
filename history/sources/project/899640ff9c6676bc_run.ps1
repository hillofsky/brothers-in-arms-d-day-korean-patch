# BIA STEP 095 FIX2: PASSIVE no-breakpoint owner field probe, no ISO/RAM writes.
# Windows PowerShell 5.1, read-only ISO, dedicated PPSSPP process only.
[CmdletBinding()]
param([switch]$NoSavedataCopy,[string]$RunIdOverride='')
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0
try { [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false) } catch {}
$env:PYTHONUTF8='1'
$env:PYTHONIOENCODING='utf-8'
$Root='PROJECT_ROOT'
$LogRoot=Join-Path $Root 'log'
$Step='STEP_095_FIX2'
$PatchLabel='owner_font_passive_probe'
$ISO=Join-Path $Root 'BIA_STAGE79_COMPILED967_STRUCTURAL_TEST.iso'
$ExpectedSha='CA320D514C32D34767E7255EA3079F7449783CDB2B98EC49797A87BDD69544D9'
$Exe='LOCAL_PATH'
$RunId=if($RunIdOverride){$RunIdOverride}else{('{0}_{1}' -f (Get-Date -Format 'yyyyMMdd_HHmmss_fff'),$PID)}
$Folder=Join-Path (Join-Path $LogRoot $Step) $RunId
$Out=Join-Path $Folder 'outputs'
$Used=Join-Path $Folder 'scripts_used'
$ZipContents=Join-Path $Folder 'zip_contents'
$Phase='init'
$Failed=$true
$Port=$null
$LaunchPid=$null
$LaunchCreation=$null
$ConfigPath=$null
$Memstick=$null
$ListenerPid=$null
$ShotDirs=@()
$ShotBaseline=@{}
$TriggerImagePath=$null
$ZipError=$null
$IsoPostflight=$null
$TranscriptStarted=$false
$Py=$null
$TraceProcess=$null
$TraceStop=$null
$TraceReady=$null
$Shot=$null
$child=$null

function WriteJson($Data,[string]$Path) {
    $Data | ConvertTo-Json -Depth 14 | Set-Content -LiteralPath $Path -Encoding UTF8
}
function PortFree([int]$Number) {
    $socket=$null
    try {
        $socket=New-Object System.Net.Sockets.TcpListener([Net.IPAddress]::Loopback,$Number)
        $socket.Start()
        return $true
    } catch { return $false }
    finally { if($null -ne $socket){try{$socket.Stop()}catch{}} }
}
function PickPort {
    foreach($num in 26420..26459){if(PortFree $num){return [int]$num}}
    throw 'No free local debugger port in 26420..26459'
}
function Listener([int]$Number) {
    try {
        $rows=@(Get-NetTCPConnection -LocalPort $Number -State Listen -ErrorAction SilentlyContinue)
        $ips=@($rows | Where-Object { $_.LocalAddress -in @('127.0.0.1','0.0.0.0','::1','::') } | Select-Object -ExpandProperty OwningProcess -Unique)
        if($ips.Count -gt 1){throw 'AMBIGUOUS_PORT_LISTENERS'}
        if($ips.Count -eq 1){return [int]$ips[0]}
    } catch {if($_.Exception.Message -eq 'AMBIGUOUS_PORT_LISTENERS'){throw}}
    $ips=@()
    foreach($line in (& netstat.exe -ano -p tcp)){
        if($line -match "^\s*TCP\s+\S+:$Number\s+\S+\s+LISTENING\s+(\d+)\s*$"){$ips += [int]$Matches[1]}
    }
    $ips=@($ips | Select-Object -Unique)
    if($ips.Count -gt 1){throw 'Ambiguous local debugger port PID by netstat'}
    if($ips.Count -eq 1){return [int]$ips[0]}
    return $null
}
function IsOurs([int]$CheckPid) {
    if(!$LaunchPid -or !$LaunchCreation -or !$ConfigPath -or !$Memstick){return $false}
    if($CheckPid -ne [int]$LaunchPid){return $false}
    $p=$null
    try {$p=Get-CimInstance Win32_Process -Filter "ProcessId=$CheckPid" -ErrorAction Stop}catch{return $false}
    if($null -eq $p){return $false}
    $cmd=[string]$p.CommandLine
    $path=[string]$p.ExecutablePath
    $creation=[string]$p.CreationDate
    if(!$path -or !$cmd -or !$creation){return $false}
    return ([string]::Equals($path,$Exe,[StringComparison]::OrdinalIgnoreCase) -and
        [string]::Equals($creation,$LaunchCreation,[StringComparison]::OrdinalIgnoreCase) -and
        $cmd.IndexOf($ISO,[StringComparison]::OrdinalIgnoreCase) -ge 0 -and
        $cmd.IndexOf($ConfigPath,[StringComparison]::OrdinalIgnoreCase) -ge 0 -and
        $cmd.IndexOf($Memstick,[StringComparison]::OrdinalIgnoreCase) -ge 0)
}
function AssertListener {
    if(!$Port -or !$LaunchPid){throw 'Missing unique PPSSPP owner information'}
    $actual=Listener ([int]$Port)
    if(!$actual -or [int]$actual -ne [int]$LaunchPid -or !(IsOurs ([int]$actual))){
        throw "PPSSPP ownership check failed: expected $LaunchPid, listener $actual, port $Port"
    }
    $script:ListenerPid=[int]$actual
}
function State([string]$Mode,[string]$Detail) {
    if(!$Py -or !(Test-Path -LiteralPath $Py -PathType Leaf)){return}
    & $Py (Join-Path $PSScriptRoot 'scripts\update_state.py') --root $Root --runid $RunId --phase $Mode --run-dir $Folder --detail $Detail
    if($LASTEXITCODE -ne 0){throw "Could not update PROJECT_STATE, phase=$Mode"}
}
try {
    New-Item -ItemType Directory -Force -Path $Out,$Used | Out-Null
    Copy-Item -LiteralPath $PSCommandPath -Destination (Join-Path $Used 'run.ps1') -Force
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'LAUNCH.ps1') -Destination $Used -Force
    foreach($item in @('passive_owner_watch.py','ws_readonly.py','update_state.py')){
        Copy-Item -LiteralPath (Join-Path $PSScriptRoot ('scripts\'+$item)) -Destination $Used -Force
    }
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'reference\stage79_mission2_expected.json') -Destination $Used -Force
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'reference\step090_findings.json') -Destination $Used -Force
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'reference\step092_confirmed.json') -Destination $Used -Force
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'reference\step093_confirmed.json') -Destination $Used -Force
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'README.md') -Destination $Folder -Force
    # Recover only small text diagnostics from failed STEP095 runs. Never copy
    # ISO, 32MiB RAM dumps, SAVEDATA or screenshots from old runs.
    try {
        $priorRoot=Join-Path $LogRoot 'STEP_095'
        if(Test-Path -LiteralPath $priorRoot -PathType Container){
            $recent=@(Get-ChildItem -LiteralPath $priorRoot -Directory -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 2)
            $oldOut=Join-Path $Out 'previous_STEP095_partial_logs'
            New-Item -ItemType Directory -Path $oldOut -Force | Out-Null
            foreach($oldFolder in $recent){
                $oldDest=Join-Path $oldOut $oldFolder.Name
                New-Item -ItemType Directory -Path $oldDest -Force | Out-Null
                foreach($rel in @('FAILURE.txt','ZIP_FAILURE.txt','run.log','stdout.txt','stderr.txt','outputs\preflight.json','outputs\owned_session.json','outputs\control_mapping_copy.json','outputs\ppsspp_exit_status.json','outputs\step095_owner_writer_report.json')){
                    $oldSrc=Join-Path $oldFolder.FullName $rel
                    if((Test-Path -LiteralPath $oldSrc -PathType Leaf) -and (Get-Item -LiteralPath $oldSrc).Length -le 1048576){
                        Copy-Item -LiteralPath $oldSrc -Destination (Join-Path $oldDest (($rel -replace '[\\/]','_'))) -Force
                    }
                }
            }
        }
    } catch { Write-Host "Old STEP095 partial log recovery skipped: $_" -ForegroundColor Yellow }
    try {Start-Transcript -Path (Join-Path $Folder 'run.log') -Force | Out-Null; $TranscriptStarted=$true}catch{}
    Write-Host "BIA STEP095 FIX2 passive font-owner field watch: $RunId" -ForegroundColor Cyan
    $Phase='preflight'
    if(!(Test-Path -LiteralPath $ISO -PathType Leaf)){throw "ISO missing: $ISO"}
    if(!(Test-Path -LiteralPath $Exe -PathType Leaf)){throw "PPSSPP missing: $Exe"}
    $got=(Get-FileHash -LiteralPath $ISO -Algorithm SHA256).Hash.ToUpperInvariant()
    if($got -ne $ExpectedSha){throw "Unexpected Stage79 ISO SHA256: $got"}
    $Py='LOCAL_PATH'
    if(!(Test-Path -LiteralPath $Py -PathType Leaf)){
        $pc=Get-Command 'python.exe' -ErrorAction SilentlyContinue
        if(!$pc){throw 'Python is missing at pinned path and PATH'}
        $Py=$pc.Source
    }
# FIX2: fail before launching PPSSPP if the WebSocket request API contract regresses.
$Phase='python_prelaunch_contract_tests'
foreach($testRelative in @('tests\test_ws_contract.py','tests\test_passive.py','tests\test_passive_main_mock.py')){
    $testPath=Join-Path $PSScriptRoot $testRelative
    if(!(Test-Path -LiteralPath $testPath -PathType Leaf)){throw "MISSING_TEST: $testPath"}
    & $Py -B $testPath
    if($LASTEXITCODE -ne 0){throw "PYTHON_PREFLIGHT_TEST_FAILED: $testRelative (exit=$LASTEXITCODE)"}
}
Write-Host 'Python contract and fake-PPSSPP tests PASS before emulator launch.' -ForegroundColor Green
    WriteJson ([ordered]@{step=$Step;runid=$RunId;original_iso=$ISO;iso_sha256=$got;ppsspp=$Exe;ppsspp_sha256=(Get-FileHash -LiteralPath $Exe -Algorithm SHA256).Hash;no_iso_writes=$true;python=$Py}) (Join-Path $Out 'preflight.json')
    $driveInfo=New-Object System.IO.DriveInfo -ArgumentList @('D')
    WriteJson ([ordered]@{drive='D';free_bytes_before=$driveInfo.AvailableFreeSpace;time=(Get-Date -Format o);new_iso_created=$false;large_ram_dump_created=$false;cleanup_policy='After ZIP CRC validation remove only this run duplicate outputs/scripts_used/staging; preserve isolated SAVEDATA, ISO, evidence ZIP and PROJECT_STATE.'}) (Join-Path $Out 'space_cleanup_plan.json')
    $Phase='safe_window_hotkey_setup'
    Add-Type -ReferencedAssemblies 'System.Drawing' -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
using System.Drawing;
using System.Drawing.Imaging;
public static class BiaStep085Window {
    [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left,Top,Right,Bottom; }
    [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint processId);
    [DllImport("user32.dll")] public static extern short GetAsyncKeyState(int virtualKey);
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT rect);
    public static string SaveForegroundWindow(IntPtr hWnd,string file) {
        RECT r; if (!GetWindowRect(hWnd, out r)) throw new Exception("GetWindowRect failed");
        int w=r.Right-r.Left, h=r.Bottom-r.Top;
        if(w<100 || h<100 || w>8192 || h>8192) throw new Exception("Unexpected window dimensions");
        using (Bitmap bmp=new Bitmap(w,h)) {
            using(Graphics g=Graphics.FromImage(bmp)) {g.CopyFromScreen(r.Left,r.Top,0,0,new Size(w,h));}
            bmp.Save(file,ImageFormat.Png);
        }
        return w.ToString()+"x"+h.ToString();
    }
}
'@
    $Phase='prepare_isolated_memstick'
    $Port=PickPort
    $ConfigPath=Join-Path $Folder 'ppsspp_step095_append.ini'
    $Memstick=Join-Path $Folder 'STEP_095_FIX2_ISOLATED_MEMSTICK'
    New-Item -ItemType Directory -Path (Join-Path $Memstick 'PSP\SAVEDATA'),(Join-Path $Memstick 'PSP\SYSTEM'),(Join-Path $Memstick 'PSP\SCREENSHOT') -Force | Out-Null
    $SaveSource=$null
    if(!$NoSavedataCopy){
        $Sources=@("$env:USERPROFILE\Documents\PPSSPP\PSP\SAVEDATA", "$env:APPDATA\PPSSPP\PSP\SAVEDATA", "$(Split-Path -Parent $Exe)\memstick\PSP\SAVEDATA", "$env:USERPROFILE\Documents\PSP\SAVEDATA")
        foreach($src in $Sources){
            if((Test-Path -LiteralPath $src -PathType Container) -and @(Get-ChildItem -LiteralPath $src -Directory -ErrorAction SilentlyContinue).Count -gt 0){$SaveSource=$src;break}
        }
        if($SaveSource){
            # Disk safe: only copy saves likely belonging to this title; never all PSP saves.
            $gameSaves=@(Get-ChildItem -LiteralPath $SaveSource -Directory -ErrorAction SilentlyContinue | Where-Object { $_.Name -match 'ULUS10193|BROTHERS|BIA' })
            $sizeEstimate=[int64]0
            foreach($sd in $gameSaves){
                $sizeEstimate += [int64](Get-ChildItem -LiteralPath $sd.FullName -File -Recurse -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum
            }
            if($sizeEstimate -gt 268435456){throw 'BIA_SAVE_COPY_TOO_LARGE_OVER_256M; source data untouched'}
            foreach($sd in $gameSaves){Copy-Item -LiteralPath $sd.FullName -Destination (Join-Path $Memstick 'PSP\SAVEDATA') -Recurse -Force}
            if($gameSaves.Count -eq 0){Write-Host 'No ULUS10193/BIA savedata directory identified; original saves remain untouched.' -ForegroundColor Yellow}
        }
    }
    WriteJson ([ordered]@{savedata_source=$SaveSource;copy_scope='ULUS10193/BROTHERS/BIA directories only, <=256MiB';test_memstick=$Memstick;original_savedata_untouched=$true}) (Join-Path $Out 'savedata_copy.json')
    # Reuse the USER'S existing screenshot key mapping without changing their original controls.ini.
    # A unique memstick otherwise starts with default controls: the configured '1' could be lost.
    $exeDir=Split-Path -Parent $Exe
    $ControlSource=$null
    $controlRoots=@(
        (Join-Path $exeDir 'memstick\PSP\SYSTEM'),
        (Join-Path $env:USERPROFILE 'Documents\PPSSPP\PSP\SYSTEM'),
        (Join-Path $env:APPDATA 'PPSSPP\PSP\SYSTEM'),
        (Join-Path $exeDir 'PSP\SYSTEM'),
        (Join-Path $env:USERPROFILE 'Documents\PSP\SYSTEM')
    )
    if($SaveSource){
        $controlRoots=@((Join-Path (Split-Path -Parent $SaveSource) 'SYSTEM')) + $controlRoots
    }
    foreach($parent in $controlRoots){
        $tryFile=Join-Path $parent 'controls.ini'
        if(Test-Path -LiteralPath $tryFile -PathType Leaf){$ControlSource=$tryFile;break}
    }
    $CopiedControls=$null
    if($ControlSource){
        $CopiedControls=Join-Path $Memstick 'PSP\SYSTEM\controls.ini'
        Copy-Item -LiteralPath $ControlSource -Destination $CopiedControls -Force
    }
    WriteJson ([ordered]@{original_controls_ini=$ControlSource;copied_controls_ini=$CopiedControls;original_unchanged=$true;key_1_mapping_assumed_from_user=$true;mapping_not_programmatically_rewritten=$true}) (Join-Path $Out 'control_mapping_copy.json')
    if(!$ControlSource){Write-Host 'WARN: controls.ini not found. If key 1 does not screenshot in NEW PPSSPP, map it in that window.' -ForegroundColor Yellow}
    # PPSSPP usually writes <memstick>\PSP\SCREENSHOT, but the user's install may use a shared location.
    # Watch both isolated and known standard screenshot locations; NEVER delete or modify originals.
    $ShotDirs=@(
        (Join-Path $Memstick 'PSP\SCREENSHOT'),
        (Join-Path $exeDir 'memstick\PSP\SCREENSHOT'),
        (Join-Path $env:USERPROFILE 'Documents\PPSSPP\PSP\SCREENSHOT'),
        (Join-Path $env:APPDATA 'PPSSPP\PSP\SCREENSHOT'),
        (Join-Path $exeDir 'PSP\SCREENSHOT'),
        $exeDir,
        (Join-Path $env:USERPROFILE 'Documents\PPSSPP')
    ) | Select-Object -Unique
    foreach($dir in $ShotDirs){
        if(!(Test-Path -LiteralPath $dir -PathType Container)){continue}
        foreach($f in @(Get-ChildItem -LiteralPath $dir -File -Filter 'ULUS10193_*' -ErrorAction SilentlyContinue)){
            if($f.Extension -notin @('.jpg','.jpeg','.png')){continue}
            $ShotBaseline[$f.FullName.ToLowerInvariant()]=$f.LastWriteTimeUtc.Ticks
        }
    }
    WriteJson ([ordered]@{watch_dirs=$ShotDirs;baseline_count=$ShotBaseline.Count;key='1';accept_extensions=@('.jpg','.jpeg','.png');created_at=(Get-Date -Format o)}) (Join-Path $Out 'screenshot_watch_setup.json')
    @"
[General]
RemoteISOPort = $Port
RemoteDebuggerOnStartup = True
RemoteDebuggerLocal = True
[Graphics]
SoftwareRenderer = False
"@ | Set-Content -LiteralPath $ConfigPath -Encoding ASCII
    $Phase='launch_owned_ppsspp'
    $arguments=@('-i', "--memstick=`"$Memstick`"", "--appendconfig=`"$ConfigPath`"", "`"$ISO`"")
    $child=Start-Process -FilePath $Exe -ArgumentList $arguments -PassThru
    $LaunchPid=[int]$child.Id
    $launched=Get-CimInstance Win32_Process -Filter "ProcessId=$LaunchPid" -ErrorAction Stop
    if(!$launched){throw 'Launched PID unavailable'}
    $LaunchCreation=[string]$launched.CreationDate
    $Phase='verify_port_pid_exclusive'
    for($i=0;$i -lt 120;$i++){
        $listener=Listener ([int]$Port)
        if($listener){break}
        $child.Refresh()
        if($child.HasExited){throw 'Dedicated PPSSPP terminated before WebSocket startup'}
        Start-Sleep -Milliseconds 500
    }
    AssertListener
    WriteJson ([ordered]@{pid=$LaunchPid;listener_pid=$ListenerPid;port=$Port;created=$LaunchCreation;exe=$Exe;iso=$ISO;config=$ConfigPath;memstick=$Memstick;owned=$true;verified_at=(Get-Date -Format o)}) (Join-Path $Out 'owned_session.json')
    # Passive polling only. No PSP breakpoints, no cpu.pause, no write commands.
    $Phase='arm_passive_owner_observer_before_mission'
    AssertListener
    $TraceReady=Join-Path $Folder 'STEP095_FIX2_ARMED.signal'
    $TraceStop=Join-Path $Folder 'STEP095_FIX2_STOP.signal'
    $traceScript=Join-Path $PSScriptRoot 'scripts\passive_owner_watch.py'
    $traceArgs=@('-u',('"'+$traceScript+'"'),'--port',[string]$Port,
        '--output',('"'+$Out+'"'),'--listener-pid',[string]$ListenerPid,
        '--ready-file',('"'+$TraceReady+'"'),'--stop-file',('"'+$TraceStop+'"'),'--timeout','900')
    $TraceProcess=Start-Process -FilePath $Py -ArgumentList $traceArgs -PassThru -WindowStyle Hidden -RedirectStandardOutput (Join-Path $Folder 'stdout.txt') -RedirectStandardError (Join-Path $Folder 'stderr.txt')
    $armEnd=(Get-Date).AddSeconds(45)
    while(!(Test-Path -LiteralPath $TraceReady -PathType Leaf) -and (Get-Date) -lt $armEnd){
        $TraceProcess.Refresh()
        if($TraceProcess.HasExited){throw "STEP095 FIX2 passive observer exited before it could arm; exit $($TraceProcess.ExitCode)"}
        Start-Sleep -Milliseconds 200
    }
    if(!(Test-Path -LiteralPath $TraceReady -PathType Leaf)){throw 'STEP095 FIX2 passive observer did not arm in 45 seconds'}
    Write-Host 'PASSIVE OBSERVER ARMED (NO BREAKPOINTS). START should work normally.' -ForegroundColor Green
    $Phase='wait_for_ppsspp_native_screenshot_key'
    Write-Host ''
    Write-Host 'In the NEW PPSSPP window, go to Mission 2 when the Korean text is shown as >.' -ForegroundColor Cyan
    Write-Host 'Press the key 1 ONCE to take a PPSSPP screenshot (your existing binding).' -ForegroundColor Yellow
    Write-Host 'Do not press Ctrl+Shift+F8, and do not switch to PowerShell.' -ForegroundColor Yellow
    Write-Host 'Read-only owner field polling is active. Key 1 finalizes collection.' -ForegroundColor Yellow
    Write-Host '15-minute timeout. Only the dedicated PPSSPP window is accepted.' -ForegroundColor Yellow
    Write-Host "PID=$LaunchPid   PORT=$Port" -ForegroundColor Gray
    $Pressed=$false
    $wasDown=$false
    $HitHwnd=[IntPtr]::Zero
    $keyTime=[datetime]::MinValue
    $lastOwnerCheck=(Get-Date).AddSeconds(-3)
    $stopAt=(Get-Date).AddMinutes(15)
    while((Get-Date) -lt $stopAt){
        if((Get-Date) -gt $lastOwnerCheck.AddSeconds(2)){
            if(!(IsOurs ([int]$LaunchPid))){throw 'Owned PPSSPP process changed/exited during wait'}
            $lastOwnerCheck=Get-Date
        }
        $hwnd=[BiaStep085Window]::GetForegroundWindow()
        [uint32]$foregroundPid=0
        [void][BiaStep085Window]::GetWindowThreadProcessId($hwnd,[ref]$foregroundPid)
        $isFocused=([int]$foregroundPid -eq [int]$LaunchPid)
        $down=$isFocused -and (([BiaStep085Window]::GetAsyncKeyState(0x31) -lt 0) -or ([BiaStep085Window]::GetAsyncKeyState(0x61) -lt 0))
        if($down -and !$wasDown){
            $Pressed=$true
            $HitHwnd=$hwnd
            $keyTime=[datetime]::UtcNow
            break
        }
        $wasDown=$down
        Start-Sleep -Milliseconds 40
    }
    if(!$Pressed){throw 'TIMED_OUT_NO_KEY_1_ON_OWNED_PPSSPP'}
    $Phase='await_native_screenshot_file'
    Write-Host 'Key 1 detected in owned PPSSPP; waiting for screenshot, then finalizing owner-writer trace...' -ForegroundColor Cyan
    $found=@()
    $shotEnd=(Get-Date).AddSeconds(7)
    while((Get-Date) -lt $shotEnd){
        $found=@()
        foreach($dir in $ShotDirs){
            if(!(Test-Path -LiteralPath $dir -PathType Container)){continue}
            foreach($f in @(Get-ChildItem -LiteralPath $dir -File -Filter 'ULUS10193_*' -ErrorAction SilentlyContinue)){
                if($f.Extension -notin @('.jpg','.jpeg','.png')){continue}
                # Files might be timestamped with coarse resolution. The baseline guards against pre-run files.
                if($f.LastWriteTimeUtc -lt $keyTime.AddSeconds(-2)){continue}
                if($f.Length -le 1024){continue}
                $lower=$f.FullName.ToLowerInvariant()
                if($ShotBaseline.ContainsKey($lower) -and [long]$ShotBaseline[$lower] -ge $f.LastWriteTimeUtc.Ticks){continue}
                $found+=,$f
            }
        }
        if($found.Count -gt 0){
            # Give the encoder time to finish writing the JPG/PNG.
            Start-Sleep -Milliseconds 200
            $ready=@()
            foreach($f in $found){
                try {
                    $chk=Get-Item -LiteralPath $f.FullName -ErrorAction Stop
                    if($chk.Length -gt 1024 -and $chk.Length -eq $f.Length){$ready+=,$chk}
                } catch {}
            }
            if($ready.Count -gt 0){$found=$ready;break}
        }
        Start-Sleep -Milliseconds 80
    }
    if($found.Count -eq 0){throw 'KEY_1_DETECTED_BUT_NO_NEW_ULUS10193_SCREENSHOT: verify screenshot binding and PPSSPP screenshot directory'}
    # Prefer this run's unique screenshot directory. A shared screenshot is corroboration only.
    $isolatedPrefix=(Join-Path $Memstick 'PSP\SCREENSHOT') + '\'
    $ours=@($found | Where-Object { $_.FullName.StartsWith($isolatedPrefix,[StringComparison]::OrdinalIgnoreCase) })
    if($ours.Count -gt 0){$found=$ours}
    $found=@($found | Sort-Object -Property LastWriteTimeUtc -Descending)
    if($found.Count -gt 1){throw 'AMBIGUOUS_MULTIPLE_NATIVE_SCREENSHOTS; refusing mismatched frame'}
    $Shot=$found[0]
    $isIsolated=$Shot.FullName.StartsWith($isolatedPrefix,[StringComparison]::OrdinalIgnoreCase)
    $Phase='copy_native_screenshot_and_host_window'
    $destination=Join-Path $Out ('ppsspp_native_screen_at_key1' + $Shot.Extension.ToLowerInvariant())
    Copy-Item -LiteralPath $Shot.FullName -Destination $destination -Force
    $TriggerImagePath=$destination
    $dims=$null
    $hostImage=$null
    $hostError=$null
    try {
        $dims=[BiaStep085Window]::SaveForegroundWindow($HitHwnd,(Join-Path $Out 'host_window_at_key1.png'))
        $hostImage='host_window_at_key1.png'
    } catch {
        $hostError=($_ | Out-String)
        Write-Host 'Host window PNG failed but native PPSSPP screenshot succeeded; continuing.' -ForegroundColor Yellow
    }
    WriteJson ([ordered]@{hotkey='1';detected_utc=$keyTime.ToString('o');foreground_pid=$LaunchPid;original_screenshot=$Shot.FullName;copied_screenshot=(Split-Path -Leaf $destination);screenshot_sha256=(Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash;screenshot_memstick_isolated=$isIsolated;shared_path_cannot_prove_file_owner=(!$isIsolated);host_window_dimensions=$dims;host_window=$hostImage;host_window_error=$hostError;visual_confirmation='PENDING_REVIEW'}) (Join-Path $Out 'native_screenshot_trigger.json')
    Write-Host "Native PPSSPP image captured: $($Shot.Name) (isolated memstick: $isIsolated)" -ForegroundColor Green
    $Phase='finalize_passive_observer'
    AssertListener
    Set-Content -LiteralPath $TraceStop -Value 'screenshot_saved' -Encoding ASCII
    if(!$TraceProcess.WaitForExit(30000)){throw 'STEP095 FIX2 passive observer did not stop after screenshot; see partial report'}
    if($TraceProcess.ExitCode -ne 0){throw "STEP095 FIX2 passive observer returned $($TraceProcess.ExitCode); see stderr.txt and diagnostic JSON"}
    $reportPath=Join-Path $Out 'step095_fix2_passive_report.json'
    if(!(Test-Path -LiteralPath $reportPath -PathType Leaf)){throw 'STEP095 FIX2 passive report not generated'}
    $report=Get-Content -LiteralPath $reportPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if($report.status -ne 'PASSIVE_CAPTURE_COMPLETE_NO_PATCH'){throw "Passive collector did not complete: $($report.status)"}
    Write-Host "STEP095 FIX2 passive observation: $($report.status); change events: $($report.field_change_count)" -ForegroundColor Green
    AssertListener
    $Phase='postflight_hash'
    $IsoPostflight=(Get-FileHash -LiteralPath $ISO -Algorithm SHA256).Hash.ToUpperInvariant()
    if($IsoPostflight -ne $ExpectedSha){throw "POSTFLIGHT ISO SHA MISMATCH $IsoPostflight"}
    $Failed=$false
    Write-Host 'STEP095 FIX2 passive field trace finished. Korean font fix NOT applied.' -ForegroundColor Green
} catch {
    $Failed=$true
    $why=$_ | Out-String
    Write-Host "STEP095 FIX2 FAILED at ${Phase}: $why" -ForegroundColor Red
    try { New-Item -ItemType Directory -Path $Folder -Force | Out-Null; "STEP: STEP_095_FIX2`r`nSTATUS: FAILED`r`nPHASE: $Phase`r`nTIME: $(Get-Date -Format o)`r`nPID: $LaunchPid`r`nPORT: $Port`r`nREASON:`r`n$why" | Set-Content -LiteralPath (Join-Path $Folder 'FAILURE.txt') -Encoding UTF8 } catch {}
} finally {
    # Cooperative stop of only the Python tracer process started in this run.
    if($TraceStop -and !(Test-Path -LiteralPath $TraceStop -PathType Leaf)){
        try{Set-Content -LiteralPath $TraceStop -Value 'launcher_exit' -Encoding ASCII}catch{}
    }
    if($TraceProcess){
        try{
            $TraceProcess.Refresh()
            if(!$TraceProcess.HasExited){
                if(!$TraceProcess.WaitForExit(15000)){
                    Write-Host 'Warning: dedicated STEP095 FIX2 passive observer still active. Stopping only its own process.' -ForegroundColor Yellow
                    Stop-Process -Id $TraceProcess.Id -Force -ErrorAction SilentlyContinue
                }
            }
        }catch{}
    }
    # IMPORTANT: Never kill PPSSPP on script failure or normal completion.
    # STEP095 previously force-closed its emulator in finally, masking actual cause.
    # Leave only the owned emulator running for inspection; never touch others.
    if($LaunchPid){
        try {
            $pp = Get-Process -Id $LaunchPid -ErrorAction SilentlyContinue
            WriteJson ([ordered]@{pid=$LaunchPid;still_running=[bool]$pp;exit_code= $(if($child -and $child.HasExited){$child.ExitCode}else{$null});not_force_stopped=$true;time=(Get-Date -Format o)}) (Join-Path $Out 'ppsspp_exit_status.json')
            if($pp){Write-Host "PPSSPP PID $LaunchPid remains open for diagnosis (NOT auto-terminated)." -ForegroundColor Yellow}
        } catch { Write-Host "PPSSPP exit status read failed: $_" -ForegroundColor Yellow }
    }
    try{if(Test-Path -LiteralPath $ISO -PathType Leaf){$IsoPostflight=(Get-FileHash -LiteralPath $ISO -Algorithm SHA256).Hash.ToUpperInvariant()}}catch{}
    if($IsoPostflight -and $IsoPostflight -ne $ExpectedSha){
        $Failed=$true
        try { Add-Content -LiteralPath (Join-Path $Folder 'FAILURE.txt') -Value "`r`nISO HASH CHANGED: $IsoPostflight" -Encoding UTF8 } catch {}
    }
    try {New-Item -ItemType Directory -Force -Path $Out | Out-Null; WriteJson ([ordered]@{expected_sha256=$ExpectedSha;actual_sha256=$IsoPostflight;unchanged=($IsoPostflight -eq $ExpectedSha);checked_at=(Get-Date -Format o);iso_write_attempted=$false}) (Join-Path $Out 'postflight_iso.json')} catch {}
    try {
        $afterDrive=New-Object System.IO.DriveInfo -ArgumentList @('D')
        $beforeSpace=Get-Content -LiteralPath (Join-Path $Out 'space_cleanup_plan.json') -Raw -Encoding UTF8 | ConvertFrom-Json
        WriteJson ([ordered]@{drive='D';free_bytes_before=$beforeSpace.free_bytes_before;free_bytes_before_result_zip=$afterDrive.AvailableFreeSpace;delta_bytes_before_zip=([int64]$afterDrive.AvailableFreeSpace-[int64]$beforeSpace.free_bytes_before);new_iso_created=$false;full_ram_dump_created=$false;automatic_cleanup='Only duplicated run outputs/scripts_used/staging after ZIP validation; isolated memstick retained if it may hold saves';preserve_original_iso=$true;preserve_known_good_iso=$true;preserve_saves=$true}) (Join-Path $Out 'space_cleanup_report.json')
    } catch { Write-Host "Space report unavailable: $_" -ForegroundColor Yellow }
    try {
        if($Py -and (Test-Path -LiteralPath $Py -PathType Leaf) -and (Test-Path -LiteralPath (Join-Path $Root 'PROJECT_STATE.md') -PathType Leaf)){
            State $(if($Failed){'failure'}else{'success'}) "run=$RunId; phase=$Phase; PASSIVE no-breakpoint owner+0x28 polling; key1 screenshot; ISO/RAM unchanged; Korean render not fixed"
        }
    } catch { $Failed=$true; Write-Host "STATE_UPDATE_FAILED $_" -ForegroundColor Red; try{Add-Content -LiteralPath (Join-Path $Folder 'FAILURE.txt') -Value "STATE_UPDATE_FAILED $_"}catch{} }
    try {
        foreach($item in @((Join-Path $Root 'PROJECT_STATE.md'),(Join-Path $LogRoot 'steps\STEP_095_FIX2.md'))){
            if(Test-Path -LiteralPath $item -PathType Leaf){Copy-Item -LiteralPath $item -Destination $Out -Force}
        }
    } catch {}
    if($TranscriptStarted){try{Stop-Transcript | Out-Null}catch{}}
    try {
        New-Item -ItemType Directory -Force -Path (Join-Path $ZipContents 'outputs'),(Join-Path $ZipContents 'scripts_used') | Out-Null
        if(Test-Path -LiteralPath $Out -PathType Container){Copy-Item -Path (Join-Path $Out '*') -Destination (Join-Path $ZipContents 'outputs') -Recurse -Force -ErrorAction SilentlyContinue}
        if(Test-Path -LiteralPath $Used -PathType Container){Copy-Item -Path (Join-Path $Used '*') -Destination (Join-Path $ZipContents 'scripts_used') -Recurse -Force -ErrorAction SilentlyContinue}
        foreach($item in @('README.md','FAILURE.txt','run.log','stdout.txt','stderr.txt','PROJECT_STATE_BEFORE_STEP095_FIX2.md','ppsspp_step095_append.ini')){
            $src=Join-Path $Folder $item
            if(Test-Path -LiteralPath $src -PathType Leaf){Copy-Item -LiteralPath $src -Destination $ZipContents -Force}
        }
        WriteJson ([ordered]@{policy='Verified ZIP preserves exact scripts/results. On CRC success delete temporary staging, duplicate outputs and scripts_used; keep isolated memstick to avoid deleting possible new SAVEDATA.'; pre_existing_results='Never deleted'; iso_deleted=$false; any_savedata_deleted=$false; cleanup_verified_after_compression='PENDING_ZIP_CRC'; runid=$RunId}) (Join-Path $ZipContents 'cleanup_policy.json')
        $name=if($Failed){'fall_bia_STEP_095_FIX2_passive_owner_probe_'+$RunId+'.zip'}else{'bia_STEP_095_FIX2_passive_owner_probe_'+$RunId+'.zip'}
        $zip=Join-Path $LogRoot $name
        Compress-Archive -Path (Join-Path $ZipContents '*') -DestinationPath $zip -CompressionLevel Optimal -Force
        # Free ONLY temporary zip_contents when its full archived copy passes CRC.
        try {
            Add-Type -AssemblyName System.IO.Compression.FileSystem -ErrorAction SilentlyContinue
            $zf=[System.IO.Compression.ZipFile]::OpenRead($zip)
            try {
                $entries=@($zf.Entries)
                if($entries.Count -eq 0){throw 'Result ZIP is empty'}
                foreach($ent in $entries){
                    if($ent.FullName.EndsWith('/')){continue}
                    $stream=$ent.Open()
                    try {$buf=New-Object byte[] 65536; while($stream.Read($buf,0,$buf.Length) -gt 0){}}
                    finally {$stream.Dispose()}
                }
            } finally {$zf.Dispose()}
            if(Test-Path -LiteralPath $ZipContents){Remove-Item -LiteralPath $ZipContents -Recurse -Force -ErrorAction Stop}
            # Reclaim only the native screenshot from OUR isolated memstick when its exact
            # byte-identical copy is already inside the verified result ZIP. Never delete
            # native screenshots in shared PPSSPP folders or any SAVEDATA.
            try {
                if($TriggerImagePath -and $Shot -and $Memstick){
                    $isolatedShots=(Join-Path $Memstick 'PSP\SCREENSHOT')+'\'
                    if($Shot.FullName.StartsWith($isolatedShots,[StringComparison]::OrdinalIgnoreCase) -and
                       (Test-Path -LiteralPath $Shot.FullName -PathType Leaf) -and
                       (Test-Path -LiteralPath $TriggerImagePath -PathType Leaf)){
                        $h1=(Get-FileHash -LiteralPath $Shot.FullName -Algorithm SHA256).Hash
                        $h2=(Get-FileHash -LiteralPath $TriggerImagePath -Algorithm SHA256).Hash
                        if($h1 -eq $h2){
                            Remove-Item -LiteralPath $Shot.FullName -Force -ErrorAction Stop
                            Write-Host 'Removed duplicate screenshot from owned isolated memstick; saves untouched.' -ForegroundColor Green
                        }
                    }
                }
            } catch {Write-Host "Isolated duplicate screenshot retained: $_" -ForegroundColor Yellow}
            # Only redundant archival source trees. The isolated memstick may contain NEW saves,
            # so DO NOT automatically delete it. Keep original ISO / saves / all ZIPs safe.
            foreach($duplicate in @($Out,$Used)){
                if((Test-Path -LiteralPath $duplicate -PathType Container) -and
                   $duplicate.StartsWith(($Folder+'\'),[StringComparison]::OrdinalIgnoreCase)){
                    Remove-Item -LiteralPath $duplicate -Recurse -Force -ErrorAction Stop
                }
            }
            Write-Host 'Verified result ZIP; removed duplicated zip staging, outputs, scripts_used. Isolated saves preserved.' -ForegroundColor Green
        } catch {Write-Host "ZIP staging retained after verification exception: $_" -ForegroundColor Yellow}
        Write-Host "UPLOAD THIS RESULT ZIP: $zip" -ForegroundColor $(if($Failed){'Red'}else{'Green'})
    } catch {
        $Failed=$true
        Write-Host "ZIP_CREATION_FAILED: $_" -ForegroundColor Red
        try{Set-Content -LiteralPath (Join-Path $Folder 'ZIP_FAILURE.txt') -Value ($_|Out-String) -Encoding UTF8}catch{}
    }
}
if($Failed){exit 1}
exit 0
