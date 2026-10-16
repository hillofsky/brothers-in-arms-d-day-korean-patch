$ErrorActionPreference="Stop"
[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false)
$env:PYTHONUTF8="1";$env:PYTHONIOENCODING="utf-8"

$Root="PROJECT_ROOT";$LogRoot="PROJECT_ROOT\log";$Attempt="STEP_070_FIX5"
$ISO="PROJECT_ROOT\BIA_STAGE69_FIX2_NONMDI_INT92_TEST.iso"
$Exe="LOCAL_PATH"
$LogDir=Join-Path $LogRoot $Attempt;$OutDir=Join-Path $LogDir "outputs";$ScriptsUsed=Join-Path $LogDir "scripts_used"
$SuccessZip=Join-Path $LogRoot "bia_STEP_070_FIX5_int92_runtime_route_RESULT.zip"
$FailureZip=Join-Path $LogRoot "fall_bia_STEP_070_FIX5_int92_runtime_route_RESULT.zip"
$Failed=$false;$Py=$null;$Proc=$null;$OwnPid=$null;$Port=$null;$LastSuccessfulAction="startup"

if(Test-Path $LogDir){
 $stamp=Get-Date -Format "yyyyMMdd_HHmmss";$archive=Join-Path $LogRoot "old\$stamp"
 New-Item -ItemType Directory -Force -Path $archive|Out-Null
 Move-Item $LogDir (Join-Path $archive $Attempt)
}
New-Item -ItemType Directory -Force -Path $LogRoot,$LogDir,$OutDir,$ScriptsUsed,(Join-Path $LogRoot "steps")|Out-Null
Copy-Item $PSCommandPath (Join-Path $ScriptsUsed "run.ps1") -Force
Copy-Item (Join-Path $PSScriptRoot "STEP_INFO.txt") $LogDir -Force
Copy-Item (Join-Path $PSScriptRoot "FIX5_DIAGNOSIS.txt") $LogDir -Force
Copy-Item (Join-Path $PSScriptRoot "scripts\runtime_route_discovery_fix5.py") $ScriptsUsed -Force
Copy-Item (Join-Path $PSScriptRoot "scripts\capture_ppsspp_window.ps1") $ScriptsUsed -Force
Copy-Item (Join-Path $PSScriptRoot "scripts\update_state.py") $ScriptsUsed -Force
try{Start-Transcript -LiteralPath (Join-Path $LogDir "run.log") -Force|Out-Null}catch{}

function FindPython{
 $p="LOCAL_PATH"
 if(Test-Path $p){return $p}
 $c=Get-Command python.exe -ErrorAction SilentlyContinue
 if($c){return $c.Source}
 throw "Python runtime not found"
}
function State([string]$Phase,[string]$Detail){
 $old=$ErrorActionPreference;$ErrorActionPreference="Continue"
 try{
  & $Py (Join-Path $PSScriptRoot "scripts\update_state.py") --root $Root --phase $Phase --detail $Detail
  $ec=$LASTEXITCODE
 }finally{$ErrorActionPreference=$old}
 if($ec -ne 0){throw "update_state failed phase=$Phase exit=$ec"}
}
function PortFree([int]$p){
 try{$l=[Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback,$p);$l.Start();$l.Stop();$true}catch{$false}
}
function FindPort{
 foreach($p in 26420..26439){if(PortFree $p){return $p}}
 throw "No free BIA debugger port 26420..26439"
}
function GetListenerPid([int]$p){
 try{
  $c=Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction Stop | Select-Object -First 1
  if($c){return [int]$c.OwningProcess}
 }catch{}
 $lines=& netstat.exe -ano -p tcp
 foreach($line in $lines){
  if($line -match "^\s*TCP\s+\S+:$p\s+\S+\s+LISTENING\s+(\d+)\s*$"){return [int]$Matches[1]}
 }
 return $null
}
function Failure([string]$Reason){
@"
PROJECT: bia
STEP: STEP_070_FIX5
TIME: $(Get-Date -Format o)
STATUS: FAILED
FAILURE_REASON:
$Reason
PPSSPP_EXE=$Exe
PORT=$Port
OWN_PID=$OwnPid
LAST_SUCCESSFUL_ACTION=$LastSuccessfulAction
"@|Set-Content (Join-Path $LogDir "FAILURE.txt") -Encoding UTF8
}

try{
 $Py=FindPython
 if(!(Test-Path -LiteralPath $Exe)){throw "Known PPSSPP path missing: $Exe"}
 if(!(Test-Path -LiteralPath $ISO)){throw "Stage69 FIX2 ISO missing: $ISO"}
 State "start" "STEP070_FIX3_started_exact_ppsspp_path"

 Write-Host "[1/5] PPSSPP exact path confirmed." -ForegroundColor Green
 Write-Host "      $Exe"
 $Port=FindPort
 Write-Host "      Dedicated port: $Port"

 $cfg=Join-Path $LogDir "ppsspp_step070_fix5_append.ini"
 @"
[General]
RemoteISOPort = $Port
RemoteDebuggerOnStartup = True
RemoteDebuggerLocal = True
"@|Set-Content -LiteralPath $cfg -Encoding ASCII

 Write-Host "[2/5] Launching dedicated PPSSPP..." -ForegroundColor Cyan
 $args=@("--appendconfig=$cfg",$ISO)
 $Proc=Start-Process -FilePath $Exe -ArgumentList $args -PassThru
 $OwnPid=$Proc.Id
 $LastSuccessfulAction="launched PID=$OwnPid port=$Port"
 Write-Host "      PID: $OwnPid"

 Write-Host "[3/5] Verifying listener owner and command line..." -ForegroundColor Cyan
 $listenerPid=$null
 for($i=0;$i -lt 60;$i++){
  $listenerPid=GetListenerPid $Port
  if($listenerPid){break}
  if($Proc.HasExited){throw "PPSSPP exited before debugger listener appeared. ExitCode=$($Proc.ExitCode)"}
  Start-Sleep -Milliseconds 500
 }
 if(-not $listenerPid){throw "Debugger listener did not appear on port $Port"}
 if([int]$listenerPid -ne [int]$OwnPid){
  throw "Port owner PID mismatch: listener=$listenerPid launched=$OwnPid"
 }

 $wmi=Get-CimInstance Win32_Process -Filter "ProcessId=$OwnPid" -ErrorAction Stop
 $cmd=[string]$wmi.CommandLine
 if([string]::IsNullOrWhiteSpace($cmd)){throw "Could not read PPSSPP command line"}
 if($cmd.IndexOf($ISO,[StringComparison]::OrdinalIgnoreCase) -lt 0){
  throw "Launched PPSSPP command line does not contain expected ISO. CMD=$cmd"
 }
 @"
PPSSPP_EXE=$Exe
PORT=$Port
OWN_PID=$OwnPid
LISTENER_PID=$listenerPid
COMMAND_LINE=$cmd
ISO=$ISO
"@|Set-Content (Join-Path $LogDir "launch_identity_verified.txt") -Encoding UTF8
 $LastSuccessfulAction="OS identity verified"

 Write-Host "[4/5] WebSocket capture..." -ForegroundColor Cyan
 $old=$ErrorActionPreference;$ErrorActionPreference="Continue"
 try{
  & $Py (Join-Path $PSScriptRoot "scripts\runtime_route_discovery_fix5.py") `
    --port $Port --outdir $OutDir --pid $OwnPid --capture-script (Join-Path $PSScriptRoot "scripts\capture_ppsspp_window.ps1") `
    1> (Join-Path $LogDir "stdout.txt") 2> (Join-Path $LogDir "stderr.txt")
  $ec=$LASTEXITCODE
 }finally{$ErrorActionPreference=$old}
 if($ec -ne 0){throw "runtime_route_discovery_fix5.py failed ExitCode=$ec"}

 $r=Get-Content (Join-Path $OutDir "step070_fix5_report.json") -Raw -Encoding UTF8|ConvertFrom-Json
 State "captured" ("STEP070_FIX3_CAPTURED_runtimeLoadedKO_"+$r.runtime_loaded_korean+"_renderVerified_FALSE")
 $LastSuccessfulAction="route discovery captured"
 Write-Host "[5/5] Capture complete." -ForegroundColor Green
}catch{
 $Failed=$true;$reason=$_|Out-String
 $reason|Set-Content (Join-Path $LogDir "stderr_powershell.txt") -Encoding UTF8
 try{Failure $reason}catch{}
 try{if($Py){State "failure" "STEP070_FIX3_failed_no_status_promotion"}}catch{}
}finally{
 # terminate only exact PPSSPP process launched here
 if($OwnPid){
  try{
   $p=Get-Process -Id $OwnPid -ErrorAction SilentlyContinue
   if($p){Stop-Process -Id $OwnPid -Force -ErrorAction SilentlyContinue}
  }catch{}
 }
 try{Stop-Transcript|Out-Null}catch{}
 foreach($p in @("PROJECT_ROOT\PROJECT_STATE.md","PROJECT_ROOT\log\steps\STEP_070_FIX5.md")){
  if(Test-Path $p){Copy-Item $p $OutDir -Force -ErrorAction SilentlyContinue}
 }
 $zip=if($Failed){$FailureZip}else{$SuccessZip}
 try{
  if(Test-Path $zip){Remove-Item $zip -Force}
  Compress-Archive -Path (Join-Path $LogDir "*") -DestinationPath $zip -Force
 }catch{
  ($_|Out-String)|Set-Content (Join-Path $LogRoot "fall_STEP_070_FIX5_ZIP_CREATION_FAILED.txt") -Encoding UTF8
 }
 if($Failed){
  Write-Host "STEP_070 FIX5 FAILED" -ForegroundColor Red
  Write-Host "Upload: $FailureZip"
 }else{
  Write-Host "STEP_070 FIX5 ROUTE DISCOVERY CAPTURED" -ForegroundColor Green
  Write-Host "INT92 remains BUILT_UNVERIFIED."
  Write-Host "Upload: $SuccessZip"
 }
}
if($Failed){exit 1}
