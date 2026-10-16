[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$RunDir,[Parameter(Mandatory=$true)][string]$RunId)
$ErrorActionPreference='Stop'; Set-StrictMode -Version 2.0
$root='PROJECT_ROOT'; $log=Join-Path $RunDir 'outputs'; $exe='LOCAL_PATH'
$iso=Join-Path $root 'BIA_STAGE79_COMPILED967_STRUCTURAL_TEST.iso'; $sha='CA320D514C32D34767E7255EA3079F7449783CDB2B98EC49797A87BDD69544D9'
$phase='init'; $failed=$true; $proc=$null; $port=0; $memstick=Join-Path $RunDir 'isolated_memstick'; $cfg=Join-Path $RunDir 'ppsspp_append.ini'; $stamp=(Get-Date).ToUniversalTime()
function J($v,[string]$p){$v | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $p -Encoding UTF8}
function heartbeat([string]$what){J ([ordered]@{utc=(Get-Date).ToUniversalTime().ToString('o');phase=$what;runid=$RunId;ppsspp_pid=$(if($proc){$proc.Id}else{$null})}) (Join-Path $RunDir 'HEARTBEAT.json')}
function PortOwner([int]$n){
    $rows=@(Get-NetTCPConnection -LocalPort $n -State Listen -ErrorAction SilentlyContinue)
    $ids=@($rows | Where-Object {$_.LocalAddress -in @('127.0.0.1','0.0.0.0','::1','::')} | Select-Object -ExpandProperty OwningProcess -Unique)
    if($ids.Count -gt 1){throw "Multiple listeners for port $n"}
    if($ids.Count -eq 1){return [int]$ids[0]}
    return 0
}
function PortFree([int]$n){$s=$null;try{$s=New-Object -TypeName System.Net.Sockets.TcpListener -ArgumentList @([Net.IPAddress]::Loopback,$n);$s.Start();return $true}catch{return $false}finally{if($s){$s.Stop()}}}
try {
    New-Item -ItemType Directory -Path $log -Force | Out-Null
    heartbeat 'preflight'
    if(!(Test-Path -LiteralPath $exe -PathType Leaf)){throw "PPSSPP not found: $exe"}
    if(!(Test-Path -LiteralPath $iso -PathType Leaf)){throw "ISO not found: $iso"}
    $actual=(Get-FileHash -LiteralPath $iso -Algorithm SHA256).Hash.ToUpperInvariant()
    if($actual -ne $sha){throw "SHA256 mismatch for base Stage79 ISO: $actual"}
    J ([ordered]@{iso=$iso;iso_sha256=$actual;exe=$exe;read_only_game=$true;no_breakpoints=$true;no_memory_poll_before_screenshot=$true;runid=$RunId}) (Join-Path $log 'preflight.json')
    $phase='prepare_isolated_environment';heartbeat $phase
    foreach($r in @('PSP\SAVEDATA','PSP\SYSTEM','PSP\SCREENSHOT')){New-Item -ItemType Directory -Force -Path (Join-Path $memstick $r) | Out-Null}
    $exeDir=Split-Path -Parent $exe
    $controlSources=@((Join-Path $exeDir 'memstick\PSP\SYSTEM\controls.ini'),(Join-Path $env:USERPROFILE 'Documents\PPSSPP\PSP\SYSTEM\controls.ini'),(Join-Path $env:APPDATA 'PPSSPP\PSP\SYSTEM\controls.ini'))
    $controlCopy=$null
    foreach($s in $controlSources){if(Test-Path -LiteralPath $s -PathType Leaf){Copy-Item -LiteralPath $s -Destination (Join-Path $memstick 'PSP\SYSTEM\controls.ini') -Force;$controlCopy=$s;break}}
    $saveSources=@((Join-Path $exeDir 'memstick\PSP\SAVEDATA'),(Join-Path $env:USERPROFILE 'Documents\PPSSPP\PSP\SAVEDATA'),(Join-Path $env:APPDATA 'PPSSPP\PSP\SAVEDATA'))
    $saveCopy=@()
    foreach($ss in $saveSources){
        if(!(Test-Path -LiteralPath $ss -PathType Container)){continue}
        $matching=@(Get-ChildItem -LiteralPath $ss -Directory -ErrorAction SilentlyContinue | Where-Object {$_.Name -match '^ULUS10193|^BIA|^BROTHERS'})
        if($matching.Count -eq 0){continue}
        $bytes=0L
        foreach($m in $matching){$stats=(Get-ChildItem -LiteralPath $m.FullName -File -Recurse -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum);$bytes += [long]$stats.Sum}
        if($bytes -gt 134217728){throw 'Save copy larger than 128MiB; originals untouched'}
        foreach($m in $matching){Copy-Item -LiteralPath $m.FullName -Destination (Join-Path $memstick 'PSP\SAVEDATA') -Recurse -Force; $saveCopy += $m.Name}
        break
    }
    J ([ordered]@{controls_source=$controlCopy;save_directories=$saveCopy;original_data_unchanged=$true;key_1_expected=$true}) (Join-Path $log 'control_and_save_setup.json')
    $shotDirs=@((Join-Path $memstick 'PSP\SCREENSHOT'),(Join-Path $exeDir 'memstick\PSP\SCREENSHOT'),(Join-Path $env:USERPROFILE 'Documents\PPSSPP\PSP\SCREENSHOT'),(Join-Path $env:APPDATA 'PPSSPP\PSP\SCREENSHOT'),(Join-Path $exeDir 'PSP\SCREENSHOT'),$exeDir) | Select-Object -Unique
    $baseline=@{}
    foreach($dir in $shotDirs){if(Test-Path -LiteralPath $dir -PathType Container){foreach($f in @(Get-ChildItem -LiteralPath $dir -File -Filter 'ULUS10193_*' -ErrorAction SilentlyContinue)){$baseline[$f.FullName.ToLowerInvariant()]=$f.LastWriteTimeUtc.Ticks}}}
    J ([ordered]@{watch_dirs=$shotDirs;baseline_count=$baseline.Count;date=(Get-Date).ToString('o')}) (Join-Path $log 'screenshot_baseline.json')
    for($n=26420;$n -le 26499;$n++){if((PortOwner $n) -eq 0 -and (PortFree $n)){$port=$n;break}}
    if($port -eq 0){throw 'No unique free WebSocket port in 26420..26499'}
    "[General]`r`nRemoteISOPort = $port`r`nRemoteDebuggerOnStartup = True`r`nRemoteDebuggerLocal = True`r`n[Graphics]`r`nSoftwareRenderer = False`r`n" | Set-Content -LiteralPath $cfg -Encoding ASCII
    $phase='start_ppsspp';heartbeat $phase
    $args=@('-i',"--memstick=`"$memstick`"","--appendconfig=`"$cfg`"","`"$iso`"")
    $proc=Start-Process -FilePath $exe -ArgumentList $args -PassThru
    $launched=Get-CimInstance Win32_Process -Filter "ProcessId=$($proc.Id)" -ErrorAction Stop
    if(!$launched){throw 'Dedicated PPSSPP missing after launch'}
    $creation=[string]$launched.CreationDate
    J ([ordered]@{pid=$proc.Id;port=$port;created=$creation;exe=$exe;iso=$iso;config=$cfg;memstick=$memstick;commandline=[string]$launched.CommandLine;launched_at=(Get-Date).ToString('o')}) (Join-Path $log 'owned_session.json')
    $readyAt=(Get-Date).AddSeconds(65)
    $listener=0
    while((Get-Date) -lt $readyAt){
        $proc.Refresh();if($proc.HasExited){throw "PPSSPP_EXITED_BEFORE_API_READY exit_code=$($proc.ExitCode)"}
        $listener=PortOwner $port
        if($listener -ne 0){break}
        Start-Sleep -Milliseconds 400
    }
    if($listener -ne [int]$proc.Id){throw "Wrong WebSocket owner: listener=$listener expected=$($proc.Id)"}
    $check=Get-CimInstance Win32_Process -Filter "ProcessId=$($proc.Id)" -ErrorAction Stop
    if(!$check -or [string]$check.CreationDate -ne $creation -or [string]$check.ExecutablePath -ne $exe){throw 'PPSSPP PID ownership mismatch'}
    $phase='waiting_for_native_screenshot';heartbeat $phase
    Write-Host "CAPTURE READY: PPSSPP PID=$($proc.Id), PORT=$port" -ForegroundColor Green
    Write-Host 'Go to mission 2. When the Korean is displayed as >>>, press your PPSSPP screenshot key 1 ONCE.' -ForegroundColor Yellow
    Write-Host 'No RAM polling/breakpoints/input automation is running while navigating menus.' -ForegroundColor Yellow
    $deadline=(Get-Date).AddMinutes(15);$shot=$null;$lastBeat=(Get-Date).AddSeconds(-3)
    while((Get-Date) -lt $deadline){
        if((Get-Date) -gt $lastBeat.AddSeconds(2)){heartbeat $phase;$lastBeat=Get-Date}
        $proc.Refresh();if($proc.HasExited){throw "PPSSPP_EXITED_BEFORE_SCREENSHOT exit_code=$($proc.ExitCode)"}
        $hits=@()
        foreach($dir in $shotDirs){
            if(!(Test-Path -LiteralPath $dir -PathType Container)){continue}
            foreach($f in @(Get-ChildItem -LiteralPath $dir -File -Filter 'ULUS10193_*' -ErrorAction SilentlyContinue)){
                if($f.Extension.ToLowerInvariant() -notin @('.jpg','.jpeg','.png') -or $f.Length -lt 2048){continue}
                if($f.LastWriteTimeUtc -lt $stamp.AddSeconds(-1)){continue}
                $key=$f.FullName.ToLowerInvariant()
                if($baseline.ContainsKey($key) -and [long]$baseline[$key] -ge $f.LastWriteTimeUtc.Ticks){continue}
                $hits += ,$f
            }
        }
        $hits=@($hits | Sort-Object FullName -Unique)
        $fromIsolated=@($hits | Where-Object {$_.FullName.StartsWith((Join-Path $memstick 'PSP\SCREENSHOT')+'\',[StringComparison]::OrdinalIgnoreCase)})
        if($fromIsolated.Count -gt 0){$hits=$fromIsolated}
        if($hits.Count -gt 0){
            $hits=@($hits | Sort-Object LastWriteTimeUtc -Descending)
            $shot=$hits[0]
            if($hits.Count -gt 1 -and $hits[0].LastWriteTimeUtc.Ticks -eq $hits[1].LastWriteTimeUtc.Ticks){throw 'Ambiguous screenshots saved simultaneously'}
            Start-Sleep -Milliseconds 250
            $chk=Get-Item -LiteralPath $shot.FullName
            if($chk.Length -ne $shot.Length){$shot=$null}else{break}
        }
        Start-Sleep -Milliseconds 250
    }
    if(!$shot){throw 'TIMEOUT_NO_PPSSPP_SCREENSHOT'}
    $phase='copy_native_screenshot';heartbeat $phase
    $copied=Join-Path $log ('mission2_at_key1'+$shot.Extension.ToLowerInvariant())
    Copy-Item -LiteralPath $shot.FullName -Destination $copied -Force
    J ([ordered]@{original=$shot.FullName;copied=$copied;sha256=(Get-FileHash -LiteralPath $copied -Algorithm SHA256).Hash;isolated=$shot.FullName.StartsWith((Join-Path $memstick 'PSP\SCREENSHOT')+'\',[StringComparison]::OrdinalIgnoreCase);capture_time=(Get-Date).ToString('o');visual_qa='NOT_YET_REVIEWED';note='A shared screenshot path cannot prove which of multiple PPSSPP processes wrote the file'}) (Join-Path $log 'capture.json')
    Write-Host "Native screenshot collected: $($shot.Name)" -ForegroundColor Green
    $phase='optional_small_ram_snapshot';heartbeat $phase
    $python=$null
    foreach($py in @('LOCAL_PATH','python.exe')){if($py -eq 'python.exe' -or (Test-Path -LiteralPath $py -PathType Leaf)){$python=$py;break}}
    try{
        & $python (Join-Path $PSScriptRoot 'small_snapshot.py') --port $port --out (Join-Path $log 'small_snapshot.json')
        if($LASTEXITCODE -ne 0){Write-Host "Small read-only snapshot unavailable, exit=$LASTEXITCODE" -ForegroundColor Yellow}
    }catch{Write-Host "Small snapshot skipped: $_" -ForegroundColor Yellow}
    $failed=$false;$phase='complete'; heartbeat $phase
    J ([ordered]@{complete=$true;step='STEP_095_FIX3';image=$copied;time=(Get-Date).ToString('o');iso_unchanged_expected=$true;full_ram_dump=$false;breakpoints=$false;ppsspp_was_not_force_closed=$true;fixed_font=$false}) (Join-Path $RunDir 'RUN_DONE.json')
} catch {
    $why=$_ | Out-String
    J ([ordered]@{complete=$false;phase=$phase;error=$why;time=(Get-Date).ToString('o');ppsspp_pid=$(if($proc){$proc.Id}else{$null});port=$port}) (Join-Path $RunDir 'RUN_ERROR.json')
    Write-Host "FAIL at $phase : $why" -ForegroundColor Red
} finally {
    try { if($proc){$proc.Refresh(); J ([ordered]@{pid=$proc.Id;still_running=(!$proc.HasExited);exit_code=$(if($proc.HasExited){$proc.ExitCode}else{$null});not_force_closed=$true;time=(Get-Date).ToString('o')}) (Join-Path $log 'ppsspp_at_child_end.json')} } catch {}
    try {if(Test-Path -LiteralPath $iso){ J ([ordered]@{expected=$sha;actual=(Get-FileHash -LiteralPath $iso -Algorithm SHA256).Hash.ToUpperInvariant();checked=(Get-Date).ToString('o')}) (Join-Path $log 'iso_postflight.json')}}catch{}
}
if($failed){exit 1}else{exit 0}
