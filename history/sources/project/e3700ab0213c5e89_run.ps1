$ErrorActionPreference="Stop"
[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false)
$env:PYTHONUTF8="1"
$env:PYTHONIOENCODING="utf-8"

$Root="PROJECT_ROOT"
$LogRoot="$Root\log"
$Step="STEP_081"
$LogDir="$LogRoot\$Step"
$Out="$LogDir\outputs"
$Used="$LogDir\scripts_used"
$Iso="$Root\BIA_STAGE79_COMPILED967_STRUCTURAL_TEST.iso"
$Exe="LOCAL_PATH"
$ExpectedIsoSha="CA320D514C32D34767E7255EA3079F7449783CDB2B98EC49797A87BDD69544D9"
$SuccessZip="$LogRoot\bia_STEP_081_stage79_story_navigation_RESULT.zip"
$FailureZip="$LogRoot\fall_bia_STEP_081_stage79_story_navigation_RESULT.zip"
$Py="LOCAL_PATH"
$Failed=$false
$Port=$null
$ConfigPath=$null
$Memstick=$null
$LaunchPID=$null
$VerifiedListenerPID=$null
$Phase="preflight"

New-Item -ItemType Directory -Force $LogRoot | Out-Null
if(Test-Path $LogDir){
    $stamp=Get-Date -Format yyyyMMdd_HHmmss
    $old="$LogRoot\old\STEP_081_$stamp"
    New-Item -ItemType Directory -Force (Split-Path $old -Parent)|Out-Null
    Move-Item -LiteralPath $LogDir -Destination $old
}
New-Item -ItemType Directory -Force $LogDir,$Out,$Used,(Join-Path $LogRoot "steps")|Out-Null
Copy-Item "$PSScriptRoot\scripts\*" $Used -Force
Copy-Item "$PSScriptRoot\reference\*" $Used -Force
Copy-Item "$PSScriptRoot\evidence\*" $Used -Force
Copy-Item $PSCommandPath "$Used\run.ps1" -Force
Copy-Item "$PSScriptRoot\README.md" $LogDir -Force
try{Start-Transcript -Path "$LogDir\run.log" -Force|Out-Null}catch{}

function State([string]$mode,[string]$detail){
    $old=$ErrorActionPreference;$ErrorActionPreference='Continue'
    try{
        & $Py "$PSScriptRoot\scripts\update_state.py" --root $Root --phase $mode --detail $detail
        $r=$LASTEXITCODE
    }finally{$ErrorActionPreference=$old}
    if($r -ne 0){throw "State update failed: $mode ($r)"}
}
function PortFree([int]$p){
    try{
        $sock=[Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback,$p)
        $sock.Start();$sock.Stop();return $true
    }catch{return $false}
}
function ChoosePort{
    foreach($p in 26420..26439){if(PortFree $p){return [int]$p}}
    throw "No free dedicated BIA port in 26420..26439"
}
function ListenerPID([int]$p){
    try{
        $conn=Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue|Select-Object -First 1
        if($conn){return [int]$conn.OwningProcess}
    }catch{}
    foreach($line in (& netstat.exe -ano -p tcp)){
        if($line -match "^\s*TCP\s+\S+:$p\s+\S+\s+LISTENING\s+(\d+)\s*$"){
            return [int]$Matches[1]
        }
    }
    return $null
}
function ProvenOwner([int]$p){
    if(!$p -or !$ConfigPath -or !$Memstick){return $false}
    try{$x=Get-CimInstance Win32_Process -Filter "ProcessId=$p" -ErrorAction Stop}catch{return $false}
    if(!$x){return $false}
    $path=[string]$x.ExecutablePath
    $cmd=[string]$x.CommandLine
    if([string]::IsNullOrWhiteSpace($path) -or [string]::IsNullOrWhiteSpace($cmd)){return $false}
    return (
        [string]::Equals($path,$Exe,[StringComparison]::OrdinalIgnoreCase) -and
        $cmd.IndexOf($Iso,[StringComparison]::OrdinalIgnoreCase) -ge 0 -and
        $cmd.IndexOf($ConfigPath,[StringComparison]::OrdinalIgnoreCase) -ge 0 -and
        $cmd.IndexOf($Memstick,[StringComparison]::OrdinalIgnoreCase) -ge 0
    )
}
function WriteFailure([string]$reason){
@"
STEP: STEP_081
STATUS: FAILED
CHECKPOINT: $Phase
TIME: $(Get-Date -Format o)
LAUNCH_PID: $LaunchPID
VERIFIED_LISTENER_PID: $VerifiedListenerPID
DEDICATED_PORT: $Port
ISOLATED_MEMSTICK: $Memstick
ISO: $Iso
REASON:
$reason
"@|Set-Content "$LogDir\FAILURE.txt" -Encoding UTF8
}

try{
    if(!(Test-Path $Py)){throw "Python runtime missing: $Py"}
    if(!(Test-Path $Exe)){throw "PPSSPP executable missing: $Exe"}
    if(!(Test-Path $Iso)){throw "Stage79 ISO missing: $Iso"}
    $sha=(Get-FileHash -LiteralPath $Iso -Algorithm SHA256).Hash.ToUpperInvariant()
    if($sha -ne $ExpectedIsoSha){throw "Stage79 ISO hash mismatch: actual=$sha expected=$ExpectedIsoSha"}
    @{iso=$Iso;sha256=$sha;expected=$ExpectedIsoSha}|ConvertTo-Json -Depth 3|Set-Content "$Out\iso_identity.json" -Encoding UTF8
    State start "Stage79 SHA verified, preparing isolated PPSSPP memstick."
    Write-Host "[1/5] Stage79 ISO SHA-256 verified" -ForegroundColor Cyan

    $Phase="config_and_memstick"
    $Port=ChoosePort
    $ConfigPath="$LogDir\ppsspp_step081_append.ini"
    $Memstick="$LogDir\STEP_081_ISOLATED_MEMSTICK"
    if(Test-Path $Memstick){throw "Refusing to reuse existing test memstick: $Memstick"}
    New-Item -ItemType Directory -Force "$Memstick\PSP\SYSTEM","$Memstick\PSP\SAVEDATA"|Out-Null
@"
[General]
RemoteISOPort = $Port
RemoteDebuggerOnStartup = True
RemoteDebuggerLocal = True
[Graphics]
SoftwareRenderer = True
"@|Set-Content $ConfigPath -Encoding ASCII
    Write-Host "[2/5] Dedicated port $Port; separate PSP save directory" -ForegroundColor Cyan

    $Phase="launch"
    # --memstick is a PPSSPP core command-line setting, separate from
    # --appendconfig, ensuring new-game cannot use the normal save directory.
    $arguments=@("--memstick=`"$Memstick`"","--appendconfig=`"$ConfigPath`"","`"$Iso`"")
    $Launched=Start-Process -FilePath $Exe -ArgumentList $arguments -PassThru
    $LaunchPID=[int]$Launched.Id
    Write-Host "[3/5] Launched PPSSPP PID=$LaunchPID with isolated memstick" -ForegroundColor Cyan

    $Phase="verify_listener"
    $listener=$null
    for($i=0;$i -lt 120;$i++){
        $listener=ListenerPID $Port
        if($listener){break}
        if($Launched.HasExited){throw "PPSSPP exited before debugger listener appeared"}
        Start-Sleep -Milliseconds 500
    }
    if(!$listener){throw "No listener on exact dedicated debugger port: $Port"}
    if(!(ProvenOwner ([int]$listener))){throw "Listener PID=$listener ownership/isolated memstick mismatch. Refusing WebSocket control"}
    $VerifiedListenerPID=[int]$listener
    @{port=$Port;launch_pid=$LaunchPID;verified_listener_pid=$VerifiedListenerPID;
      iso=$Iso;isolated_memstick=$Memstick;config=$ConfigPath;ownership_verified=$true}|
      ConvertTo-Json -Depth 4|Set-Content "$Out\ppsspp_ownership.json" -Encoding UTF8
    Write-Host "[4/5] Verified exact debugger executable, ISO, config and save isolation" -ForegroundColor Cyan

    $Phase="story_navigation"
    $old=$ErrorActionPreference;$ErrorActionPreference='Continue'
    try{
        & $Py "$PSScriptRoot\scripts\stage081_story_navigation.py" `
          --port $Port --outdir $Out `
          --signatures "$PSScriptRoot\reference\screen_signatures.json" `
          --canaries "$PSScriptRoot\reference\compiled967_runtime_canaries.json" `
          --step079-evidence "$PSScriptRoot\evidence\step079_report.json" `
          --isolated-memstick $Memstick `
          1> "$LogDir\stdout.txt" 2> "$LogDir\stderr.txt"
        $rc=$LASTEXITCODE
    }finally{$ErrorActionPreference=$old}
    if($rc -ne 0){throw "Stage081 Python navigation failed ($rc)"}

    $r=Get-Content "$Out\step081_runtime_report.json" -Raw -Encoding UTF8|ConvertFrom-Json
    if(!$r.story_submenu_verified -or !$r.new_game_selected_by_verified_story_submenu){
        throw "Story submenu / New Game selection proof missing"
    }
    if($r.status -eq 'NEW_GAME_SELECTED_BUT_SUBMENU_NOT_LEFT'){
        throw "New Game selection did not progress. Captured evidence saved; no further blind inputs"
    }
    $Phase="complete"
    State success ("Story submenu independently verified; isolated New Game selected; status="+$r.status+"; 967 visual unverified")
    Write-Host "[5/5] Story submenu and New Game entry captured; visual review pending" -ForegroundColor Green
}catch{
    $Failed=$true
    $reason=$_|Out-String
    WriteFailure $reason
    $reason|Set-Content "$LogDir\powershell_exception.txt" -Encoding UTF8
    try{if(Test-Path $Py){State failure "STEP081 at $Phase failed. See report/screenshots/FAILURE.txt"}}catch{}
}finally{
    # Never terminate a PPSSPP process by name. Close only a PID whose
    # executable/ISO/unique config/unique memstick still match THIS session.
    foreach($pid0 in @($VerifiedListenerPID,$LaunchPID)|Select-Object -Unique){
        if($pid0){
            try{if(ProvenOwner ([int]$pid0)){
                Stop-Process -Id ([int]$pid0) -Force -ErrorAction SilentlyContinue
            }}catch{}
        }
    }
    try{Stop-Transcript|Out-Null}catch{}
    foreach($p in @("$Root\PROJECT_STATE.md","$LogRoot\steps\STEP_081.md")){
        if(Test-Path $p){Copy-Item $p $Out -Force -ErrorAction SilentlyContinue}
    }
    # Do not include the entire temporary memstick in the result archive. Save
    # a file manifest only, because in-game SAVEDATA can contain private data.
    if($Memstick -and (Test-Path $Memstick)){
        try{
            Get-ChildItem -LiteralPath $Memstick -Recurse -File -ErrorAction Stop|
              Select-Object @{n='relative_path';e={$_.FullName.Substring($Memstick.Length)}},Length|
              ConvertTo-Json -Depth 4|Set-Content "$Out\isolated_memstick_manifest.json" -Encoding UTF8
        }catch{}
    }
    $Result=if($Failed){$FailureZip}else{$SuccessZip}
    if(Test-Path $Result){Remove-Item $Result -Force}
    $TempArchiveDir="$LogDir\packable"
    New-Item -ItemType Directory -Force $TempArchiveDir | Out-Null
    foreach($f in @('README.md','run.log','stdout.txt','stderr.txt','FAILURE.txt','powershell_exception.txt','ppsspp_step081_append.ini')){
        if(Test-Path "$LogDir\$f"){Copy-Item "$LogDir\$f" "$TempArchiveDir\$f" -Force}
    }
    Copy-Item "$LogDir\outputs" "$TempArchiveDir\outputs" -Recurse -Force
    Copy-Item "$LogDir\scripts_used" "$TempArchiveDir\scripts_used" -Recurse -Force
    try{
        Compress-Archive -Path "$TempArchiveDir\*" -DestinationPath $Result -CompressionLevel Optimal -Force
    }catch{
        ($_|Out-String)|Set-Content "$LogRoot\fall_STEP_081_ZIP_ERROR.txt" -Encoding UTF8
        throw
    }
    if($Failed){
        Write-Host "STEP081 FAILED; upload $FailureZip" -ForegroundColor Red
    }else{
        Write-Host "STEP081 CAPTURE VERIFIED; upload $SuccessZip" -ForegroundColor Green
    }
}
if($Failed){exit 1}
