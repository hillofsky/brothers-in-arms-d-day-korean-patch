$ErrorActionPreference="Stop"
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
$env:PYTHONUTF8="1"
$env:PYTHONIOENCODING="utf-8"

$Root="PROJECT_ROOT"
$LogRoot="$Root\log"
$Step="STEP_080"
$LogDir=Join-Path $LogRoot $Step
$Out=Join-Path $LogDir "outputs"
$Scripts=Join-Path $LogDir "scripts_used"

$ISO="$Root\BIA_STAGE79_COMPILED967_STRUCTURAL_TEST.iso"
$Exe="LOCAL_PATH"
$ExpectedHash="CA320D514C32D34767E7255EA3079F7449783CDB2B98EC49797A87BDD69544D9"
$SuccessZip="$LogRoot\bia_STEP_080_stage79_runtime_smoke_RESULT.zip"
$FailureZip="$LogRoot\fall_bia_STEP_080_stage79_runtime_smoke_RESULT.zip"

$Failed=$false
$Py=$null
$Launched=$null
$LaunchPID=$null
$ValidatedListenerPID=$null
$Port=$null
$Checkpoint="init"
$ConfigPath=$null

if(Test-Path $LogDir) {
    $stamp=Get-Date -Format yyyyMMdd_HHmmss
    $old=Join-Path $LogRoot "old\$stamp"
    New-Item -ItemType Directory -Force $old|Out-Null
    Move-Item -LiteralPath $LogDir -Destination (Join-Path $old $Step)
}
New-Item -ItemType Directory -Force $LogRoot,$LogDir,$Out,$Scripts,(Join-Path $LogRoot "steps")|Out-Null
Copy-Item $PSCommandPath "$Scripts\run.ps1" -Force
Copy-Item "$PSScriptRoot\scripts\*" $Scripts -Force
Copy-Item "$PSScriptRoot\reference\*" $Scripts -Force
Copy-Item "$PSScriptRoot\evidence\*" $Scripts -Force
Copy-Item "$PSScriptRoot\README.md" $LogDir -Force

try{ Start-Transcript -LiteralPath "$LogDir\run.log" -Force | Out-Null }catch{}

function FindPython {
    $p="LOCAL_PATH"
    if(Test-Path $p){return $p}
    $c=Get-Command python.exe -ErrorAction SilentlyContinue
    if($c){return $c.Source}
    throw "Python runtime not found"
}
function State([string]$phase,[string]$detail) {
    $old=$ErrorActionPreference
    $ErrorActionPreference="Continue"
    try {
        & $Py "$PSScriptRoot\scripts\update_state.py" --root $Root --phase $phase --detail $detail
        $code=$LASTEXITCODE
    } finally { $ErrorActionPreference=$old }
    if($code -ne 0) {throw "State update failed: $phase"}
}
function PortFree([int]$p) {
    try {
        $tcp=[Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback,$p)
        $tcp.Start(); $tcp.Stop()
        return $true
    }catch{return $false}
}
function FindPort {
    foreach($p in 26420..26439) {if(PortFree $p){return $p}}
    throw "All dedicated BIA debugger ports 26420..26439 are occupied"
}
function GetListenerPid([int]$p) {
    try {
        $c=Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
        if($c){return [int]$c.OwningProcess}
    }catch{}
    foreach($line in (& netstat.exe -ano -p tcp)){
        if($line -match "^\s*TCP\s+\S+:$p\s+\S+\s+LISTENING\s+(\d+)\s*$"){
            return [int]$Matches[1]
        }
    }
    return $null
}
function CheckOwner([int]$p) {
    $candidate=Get-CimInstance Win32_Process -Filter "ProcessId=$p" -ErrorAction Stop
    if(!$candidate){return $false}
    $cmd=[string]$candidate.CommandLine
    $path=[string]$candidate.ExecutablePath
    if([string]::IsNullOrEmpty($path) -or [string]::IsNullOrEmpty($cmd)){
        return $false
    }
    $pathMatches=[string]::Equals($path,$Exe,[StringComparison]::OrdinalIgnoreCase)
    $isoMatches=($cmd.IndexOf($ISO,[StringComparison]::OrdinalIgnoreCase) -ge 0)
    $cfgMatches=($cmd.IndexOf($ConfigPath,[StringComparison]::OrdinalIgnoreCase) -ge 0)
    if(!$pathMatches -or !$isoMatches -or !$cfgMatches){return $false}
    # PPSSPP versions may hand the debugger to a child process; require
    # exact exe + unique ISO + unique config, or refuse to control it.
    return $true
}
function FailureText([string]$reason) {
@"
PROJECT: bia
STEP: STEP_080
STATUS: FAILED
TIME: $(Get-Date -Format o)
CHECKPOINT: $Checkpoint
PORT: $Port
LAUNCH_PID: $LaunchPID
VALIDATED_LISTENER_PID: $ValidatedListenerPID
ISO: $ISO
CAUSE:
$reason
"@ | Set-Content "$LogDir\FAILURE.txt" -Encoding UTF8
}

try {
    $Py=FindPython
    if(!(Test-Path $Exe)){throw "Known PPSSPP executable missing: $Exe"}
    if(!(Test-Path $ISO)){throw "Built Stage79 ISO missing: $ISO"}

    $Checkpoint="iso_hash"
    $real=(Get-FileHash -Algorithm SHA256 -LiteralPath $ISO).Hash.ToUpperInvariant()
    if($real -ne $ExpectedHash){
        throw "Stage79 ISO hash mismatch. Expected=$ExpectedHash actual=$real"
    }
    @{"path"=$ISO;"sha256"=$real;"expected"=$ExpectedHash} |
        ConvertTo-Json -Depth 3 | Set-Content "$Out\iso_identity.json" -Encoding UTF8
    State start "Stage79 SHA256 verified. Awaiting isolated PPSSPP dedicated debugger port."
    Write-Host "[1/4] Stage79 ISO identity verified." -ForegroundColor Cyan

    $Checkpoint="port_selection"
    $Port=FindPort
    $ConfigPath=Join-Path $LogDir "ppsspp_step080_append.ini"
@"
[General]
RemoteISOPort = $Port
RemoteDebuggerOnStartup = True
RemoteDebuggerLocal = True

[Graphics]
SoftwareRenderer = True
"@|Set-Content -LiteralPath $ConfigPath -Encoding ASCII

    $Checkpoint="launch"
    $Launched=Start-Process -FilePath $Exe -ArgumentList @("--appendconfig=$ConfigPath",$ISO) -PassThru
    $LaunchPID=[int]$Launched.Id
    Write-Host "[2/4] Launched dedicated PPSSPP process $LaunchPID on $Port." -ForegroundColor Cyan

    $Checkpoint="listener_provenance"
    $Listener=$null
    for($i=0;$i -lt 90;$i++){
        $Listener=GetListenerPid $Port
        if($Listener){break}
        if($Launched.HasExited){throw "PPSSPP launch exited before debugger appeared"}
        Start-Sleep -Milliseconds 500
    }
    if(!$Listener){throw "Debugger did not start on selected dedicated port $Port"}
    $Listener=[int]$Listener

    if(!(CheckOwner $Listener)){
        throw "Debugger PID $Listener does not match launched exact executable/ISO/unique config. Refusing WebSocket control."
    }
    $ValidatedListenerPID=$Listener
    @{"port"=$Port;"launch_pid"=$LaunchPID;"verified_debugger_pid"=$ValidatedListenerPID;"iso"=$ISO;"config"=$ConfigPath} |
        ConvertTo-Json -Depth 4 | Set-Content "$Out\ppsspp_ownership.json" -Encoding UTF8
    Write-Host "[3/4] Verified debugger belongs to exact Stage79 PPSSPP session." -ForegroundColor Cyan

    $Checkpoint="runtime_capture"
    $old=$ErrorActionPreference;$ErrorActionPreference="Continue"
    try{
        & $Py "$PSScriptRoot\scripts\stage080_smoke.py" `
          --port $Port --outdir $Out `
          --signatures "$PSScriptRoot\reference\screen_signatures.json" `
          --canaries "$PSScriptRoot\reference\compiled967_runtime_canaries.json" `
          --step079-evidence "$PSScriptRoot\evidence\step079_report.json" `
          1> "$LogDir\stdout.txt" 2> "$LogDir\stderr.txt"
        $ec=$LASTEXITCODE
    }finally{$ErrorActionPreference=$old}
    if($ec -ne 0){throw "Stage080 runtime capture exited with $ec"}

    $r=Get-Content "$Out\step080_runtime_report.json" -Raw -Encoding UTF8|ConvertFrom-Json
    if(!$r.title_verified_by_known_signature -or !$r.main_menu_story_selected_verified){
        throw "Known title/menu signature verification failed"
    }
    if(!$r.status.StartsWith("TITLE_MENU_VERIFIED_")){
        throw "Unexpected runtime status: $($r.status)"
    }

    State success ("Stage79 verified title/menu; story_transition="+$r.story_entry_left_menu_at_least_once+"; compiled967 visual render still UNVERIFIED")
    $Checkpoint="complete"
    Write-Host "[4/4] Runtime title/menu verified. Story-entry evidence captured." -ForegroundColor Green
}catch{
    $Failed=$true
    $text=$_|Out-String
    FailureText $text
    $text|Set-Content "$LogDir\stderr_powershell.txt" -Encoding UTF8
    try{if($Py){State failure "Runtime STEP080 failed at $Checkpoint; do not promote compiled967 visual status"}}catch{}
}finally{
    # Only terminate the Start-Process PID or a listener already proven to be
    # this unique exact ISO/config session. Never enumerate or kill by name.
    if($ValidatedListenerPID){
        try{
            if(CheckOwner $ValidatedListenerPID){
                Stop-Process -Id $ValidatedListenerPID -Force -ErrorAction SilentlyContinue
            }
        }catch{}
    }
    if($LaunchPID) {
        try {
            $p=Get-Process -Id $LaunchPID -ErrorAction SilentlyContinue
            if($p){ Stop-Process -Id $LaunchPID -Force -ErrorAction SilentlyContinue }
        }catch{}
    }
    try{Stop-Transcript|Out-Null}catch{}
    foreach($p in @("$Root\PROJECT_STATE.md","$LogRoot\steps\STEP_080.md")){
        if(Test-Path $p){Copy-Item $p $Out -Force -ErrorAction SilentlyContinue}
    }

    $zip=if($Failed){$FailureZip}else{$SuccessZip}
    if(Test-Path $zip){Remove-Item $zip -Force}
    try{
        Compress-Archive -Path "$LogDir\*" -DestinationPath $zip -CompressionLevel Optimal -Force
    }catch{
        ($_|Out-String)|Set-Content "$LogRoot\fall_STEP_080_ZIP_ERROR.txt" -Encoding UTF8
        throw
    }

    if($Failed) {
        Write-Host "STEP080 FAILED. Upload: $FailureZip" -ForegroundColor Red
    }else{
        Write-Host "STEP080 BOOT/TITLE/MENU VERIFIED. Upload: $SuccessZip" -ForegroundColor Green
    }
}
if($Failed){exit 1}
