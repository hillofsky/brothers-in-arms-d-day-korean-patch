$ErrorActionPreference="Stop"
[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false)
$env:PYTHONIOENCODING="utf-8"
$env:PYTHONUTF8="1"
$Root="PROJECT_ROOT"
$LogRoot="$Root\log"
$Step="STEP_083"
$StepDir="$LogRoot\$Step"
$Out="$StepDir\outputs"
$Scripts="$StepDir\scripts_used"
$Exe="LOCAL_PATH"
$ISO="$Root\BIA_STAGE79_COMPILED967_STRUCTURAL_TEST.iso"
$ExpectedSha="CA320D514C32D34767E7255EA3079F7449783CDB2B98EC49797A87BDD69544D9"
$Py="LOCAL_PATH"
$Ok="$LogRoot\bia_STEP_083_second_mission_live_font_probe_RESULT.zip"
$FailZip="$LogRoot\fall_bia_STEP_083_second_mission_live_font_probe_RESULT.zip"
$Failed=$false
$Phase="preflight"
$Port=$null
$LaunchPid=$null
$ListenerPid=$null
$ConfigPath=$null
$Memstick=$null

function PortFree([int]$num) {
    try { $s=[Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback,$num);$s.Start();$s.Stop();return $true }
    catch{return $false}
}
function FindPort {foreach($num in 26420..26439){if(PortFree $num){return [int]$num}};throw "No free dedicated port (26420-26439)"}
function GetListener([int]$num){
    try { $x=Get-NetTCPConnection -LocalPort $num -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1;if($x){return [int]$x.OwningProcess} }catch{}
    foreach($line in (& netstat.exe -ano -p tcp)){
        if($line -match "^\s*TCP\s+\S+:$num\s+\S+\s+LISTENING\s+(\d+)\s*$"){return [int]$Matches[1]}
    }
    return $null
}
function OwnerVerified([int]$num){
    if(!$num -or !$ConfigPath -or !$Memstick){return $false}
    try{$p=Get-CimInstance Win32_Process -Filter "ProcessId=$num" -ErrorAction Stop}catch{return $false}
    if(!$p){return $false}
    $cmd=[string]$p.CommandLine;$path=[string]$p.ExecutablePath
    if(!$path -or !$cmd){return $false}
    return (
        [string]::Equals($path,$Exe,[StringComparison]::OrdinalIgnoreCase) -and
        $cmd.IndexOf($ISO,[StringComparison]::OrdinalIgnoreCase) -ge 0 -and
        $cmd.IndexOf($ConfigPath,[StringComparison]::OrdinalIgnoreCase) -ge 0 -and
        $cmd.IndexOf($Memstick,[StringComparison]::OrdinalIgnoreCase) -ge 0
    )
}
function State([string]$phase,[string]$detail){
    $prev=$ErrorActionPreference;$ErrorActionPreference='Continue'
    try {& $Py "$PSScriptRoot\scripts\update_state.py" --root $Root --phase $phase --detail $detail;$ec=$LASTEXITCODE}
    finally{$ErrorActionPreference=$prev}
    if($ec -ne 0){throw "State update failed: $phase"}
}

New-Item -ItemType Directory -Force $LogRoot | Out-Null
if(Test-Path $StepDir){
    $old="$LogRoot\old\STEP_083_$(Get-Date -Format yyyyMMdd_HHmmss)"
    New-Item -ItemType Directory -Force (Split-Path $old -Parent) | Out-Null
    Move-Item -LiteralPath $StepDir -Destination $old
}
New-Item -ItemType Directory -Force $StepDir,$Out,$Scripts,(Join-Path $LogRoot 'steps')|Out-Null
Copy-Item "$PSScriptRoot\scripts\*" $Scripts -Force
Copy-Item "$PSScriptRoot\reference\*" $Scripts -Force
Copy-Item "$PSScriptRoot\evidence\*" $Scripts -Force
Copy-Item $PSCommandPath "$Scripts\run.ps1" -Force
Copy-Item "$PSScriptRoot\README.md" $StepDir -Force
try{Start-Transcript -Path "$StepDir\run.log" -Force|Out-Null}catch{}

try{
    if(!(Test-Path $Exe)){throw "PPSSPP executable missing"}
    if(!(Test-Path $Py)){throw "Python runtime missing"}
    if(!(Test-Path $ISO)){throw "Stage79 ISO missing"}
    $sha=(Get-FileHash -Algorithm SHA256 -LiteralPath $ISO).Hash.ToUpperInvariant()
    if($sha -ne $ExpectedSha){throw "Stage79 SHA mismatch: $sha"}
    State start "Stage79 identity verified; preparing isolated dedicated PPSSPP GPU session."
    $Phase='port_and_memstick'
    $Port=FindPort
    $ConfigPath="$StepDir\ppsspp_step083_append.ini"
    $Memstick="$StepDir\STEP_083_ISOLATED_MEMSTICK"
    if(Test-Path $Memstick){throw 'Refusing to reuse an existing isolated memstick'}
    New-Item -ItemType Directory -Force "$Memstick\PSP\SAVEDATA","$Memstick\PSP\SYSTEM"|Out-Null

    # Copy existing user save files into this new temporary test memstick when
    # a standard PPSSPP savedata folder can be located. Originals untouched.
    $Sources=@(
      "$env:USERPROFILE\Documents\PPSSPP\PSP\SAVEDATA",
      "$env:APPDATA\PPSSPP\PSP\SAVEDATA",
      "$(Split-Path -Parent $Exe)\memstick\PSP\SAVEDATA",
      "$env:USERPROFILE\Documents\PSP\SAVEDATA"
    )
    $SaveSource=$null
    foreach($candidate in $Sources){
        if(Test-Path $candidate){
            $dirs=@(Get-ChildItem $candidate -Directory -ErrorAction SilentlyContinue)
            if($dirs.Count -gt 0){$SaveSource=$candidate;break}
        }
    }
    if($SaveSource){
        Copy-Item "$SaveSource\*" "$Memstick\PSP\SAVEDATA" -Recurse -Force
        Write-Host "Copied existing savedata into isolated test memstick. Originals not modified." -ForegroundColor Cyan
    }else{
        Write-Host "No existing PPSSPP savedata found in standard paths; new test memstick starts empty." -ForegroundColor Yellow
    }
    @{source_savedata=$SaveSource;destination=$Memstick;savedata_copied=!!$SaveSource} |
      ConvertTo-Json -Depth 4 | Set-Content "$Out\save_isolation.json" -Encoding UTF8

    @"
[General]
RemoteISOPort = $Port
RemoteDebuggerOnStartup = True
RemoteDebuggerLocal = True
[Graphics]
SoftwareRenderer = False
"@ | Set-Content $ConfigPath -Encoding ASCII

    $Phase='launch'
    $args=@("--memstick=`"$Memstick`"","--appendconfig=`"$ConfigPath`"","`"$ISO`"")
    $p=Start-Process -FilePath $Exe -ArgumentList $args -PassThru
    $LaunchPid=[int]$p.Id
    Write-Host "Launched isolated GPU-rendered PPSSPP. PID=$LaunchPid PORT=$Port" -ForegroundColor Green
    $Phase='ownership'
    $listener=$null
    for($i=0;$i -lt 120;$i++){
        $listener=GetListener $Port
        if($listener){break}
        if($p.HasExited){throw 'PPSSPP exited before debugger was available'}
        Start-Sleep -Milliseconds 500
    }
    if(!$listener){throw "No listener on dedicated port $Port"}
    if(!(OwnerVerified ([int]$listener))){throw "Refusing to control foreign/unverified PPSSPP debugger PID=$listener"}
    $ListenerPid=[int]$listener
    @{dedicated_port=$Port;launch_pid=$LaunchPid;verified_listener_pid=$ListenerPid;owned=true;iso=$ISO}|
      ConvertTo-Json -Depth 3 | Set-Content "$Out\session_provenance.json" -Encoding UTF8

    Write-Host "";Write-Host "====================================================" -ForegroundColor Cyan
    Write-Host "STEP_083: Use this NEW PPSSPP window to reach Mission 2" -ForegroundColor Cyan
    Write-Host "When the repeated > characters are VISIBLE, return here." -ForegroundColor Yellow
    Write-Host "Do not close PPSSPP until you press Enter." -ForegroundColor Yellow
    Write-Host "This will freeze that exact game moment, read memory, then resume." -ForegroundColor Yellow
    Write-Host "====================================================" -ForegroundColor Cyan
    $choice=Read-Host "Press Enter to capture the broken Mission 2 screen, or type CANCEL to stop"
    if($choice -match '^(?i:CANCEL|EXIT|Q)$'){throw "USER_CANCELLED_BEFORE_SNAPSHOT"}

    $Phase='snapshot'
    $prev=$ErrorActionPreference;$ErrorActionPreference='Continue'
    try{
        & $Py "$PSScriptRoot\scripts\live_font_probe.py" --port $Port --outdir $Out --expected "$PSScriptRoot\reference\stage79_mission2_expected.json" `
          1> "$StepDir\stdout.txt" 2> "$StepDir\stderr.txt"
        $rc=$LASTEXITCODE
    }finally{$ErrorActionPreference=$prev}
    if($rc -ne 0){throw "Snapshot capture failed: Python exit $rc"}
    $r=Get-Content "$Out\step083_live_font_report.json" -Raw -Encoding UTF8|ConvertFrom-Json
    if($r.status -ne 'VERIFIED_LIVE_SNAPSHOT_COLLECTED'){throw "Unexpected runtime report status $($r.status)"}
    State success "Coherent live 32MiB RAM/VRAM snapshot captured, Stage79 original ISO preserved; exact mission2 glyph render still unverified."
    $Phase='complete'
    Write-Host "STEP083 snapshot complete; preparing ZIP..." -ForegroundColor Green
}catch{
    $Failed=$true
    $reason=$_|Out-String
    @"
STEP: STEP_083
STATUS: FAILED
TIME: $(Get-Date -Format o)
PHASE: $Phase
PORT: $Port
LAUNCH_PID: $LaunchPid
LISTENER_PID: $ListenerPid
REASON:
$reason
"@|Set-Content "$StepDir\FAILURE.txt" -Encoding UTF8
    try{if(Test-Path $Py){State failure "STEP083 failed at $Phase; no ISO modified."}}catch{}
}finally{
    # Terminate only PIDs whose original command line still contains the exact
    # unique ISO/config/memstick. Never terminate by process name.
    foreach($pid0 in @($ListenerPid,$LaunchPid)|Select-Object -Unique){
        if($pid0){try{if(OwnerVerified ([int]$pid0)){Stop-Process -Id ([int]$pid0) -Force -ErrorAction SilentlyContinue}}catch{}}
    }
    try{Stop-Transcript|Out-Null}catch{}
    foreach($fp in @("$Root\PROJECT_STATE.md","$LogRoot\steps\STEP_083.md")){
        if(Test-Path $fp){Copy-Item $fp $Out -Force -ErrorAction SilentlyContinue}
    }
    # Avoid storing private test save copies in the upload. Only ZIP outputs,
    # manifest and scripts. The 32MiB live RAM snapshot is compressed in outputs.
    if($Memstick -and (Test-Path $Memstick)){
      try{
        Get-ChildItem -LiteralPath $Memstick -Recurse -File | Select-Object @{n='relative_path';e={$_.FullName.Substring($Memstick.Length)}},Length |
        ConvertTo-Json -Depth 5 | Set-Content "$Out\test_memstick_manifest.json" -Encoding UTF8
      }catch{}
    }
    $Zip=if($Failed){$FailZip}else{$Ok}
    $Pack="$StepDir\zip_inputs"
    New-Item -ItemType Directory -Force "$Pack\outputs","$Pack\scripts_used" |Out-Null
    Copy-Item "$Out\*" "$Pack\outputs" -Force -ErrorAction SilentlyContinue
    Copy-Item "$Scripts\*" "$Pack\scripts_used" -Force -ErrorAction SilentlyContinue
    foreach($f in @('README.md','run.log','stdout.txt','stderr.txt','FAILURE.txt','ppsspp_step083_append.ini')){
        if(Test-Path "$StepDir\$f"){Copy-Item "$StepDir\$f" "$Pack\$f" -Force}
    }
    if(Test-Path $Zip){Remove-Item $Zip -Force}
    Compress-Archive -Path "$Pack\*" -DestinationPath $Zip -CompressionLevel Optimal -Force
    Write-Host "Upload this result ZIP: $Zip" -ForegroundColor $(if($Failed){'Red'}else{'Green'})
}
if($Failed){exit 1}
