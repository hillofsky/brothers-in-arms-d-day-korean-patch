$ErrorActionPreference="Stop"
[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false)
$env:PYTHONUTF8="1";$env:PYTHONIOENCODING="utf-8"

$Root="PROJECT_ROOT";$LogRoot="PROJECT_ROOT\log";$Attempt="STEP_070"
$ISO="PROJECT_ROOT\BIA_STAGE69_FIX2_NONMDI_INT92_TEST.iso"
$LogDir=Join-Path $LogRoot $Attempt;$OutDir=Join-Path $LogDir "outputs";$ScriptsUsed=Join-Path $LogDir "scripts_used"
$SuccessZip=Join-Path $LogRoot "bia_STEP_070_int92_runtime_route_RESULT.zip"
$FailureZip=Join-Path $LogRoot "fall_bia_STEP_070_int92_runtime_route_RESULT.zip"
$Failed=$false;$LastSuccessfulAction="PowerShell startup";$Py=$null;$Proc=$null;$Port=$null;$OwnPid=$null

if(Test-Path $LogDir){
 $stamp=Get-Date -Format "yyyyMMdd_HHmmss";$archive=Join-Path $LogRoot "old\$stamp"
 New-Item -ItemType Directory -Force -Path $archive|Out-Null
 Move-Item $LogDir (Join-Path $archive $Attempt)
}
New-Item -ItemType Directory -Force -Path $LogRoot,$LogDir,$OutDir,$ScriptsUsed,(Join-Path $LogRoot "steps")|Out-Null
Copy-Item $PSCommandPath (Join-Path $ScriptsUsed "run.ps1") -Force
Copy-Item (Join-Path $PSScriptRoot "STEP_INFO.txt") $LogDir -Force
Copy-Item (Join-Path $PSScriptRoot "scripts\runtime_route_discovery.py") $ScriptsUsed -Force
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
function Test-PortFree([int]$p){
 try{
  $l=[System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback,$p)
  $l.Start();$l.Stop();return $true
 }catch{return $false}
}
function Find-FreeBiaPort{
 foreach($p in 26420..26439){
  if(Test-PortFree $p){return $p}
 }
 throw "No free PPSSPP BIA debugger port in 26420..26439"
}
function Find-PPSSPP{
 if($env:PPSSPP_EXE -and (Test-Path $env:PPSSPP_EXE)){return (Resolve-Path $env:PPSSPP_EXE).Path}
 # Read existing PPSSPP executable paths only; do not control those processes.
 foreach($p in Get-Process -ErrorAction SilentlyContinue | Where-Object {$_.ProcessName -match '^PPSSPP'}){
  try{
   $x=$p.MainModule.FileName
   if($x -and (Test-Path $x)){return $x}
  }catch{}
 }
 $cands=@(
  "PROJECT_ROOT\PPSSPPWindows64.exe",
  "PROJECT_ROOT\ppsspp\PPSSPPWindows64.exe",
  "LOCAL_PATH",
  "$env:USERPROFILE\Downloads\PPSSPPWindows64.exe"
 )
 foreach($x in $cands){if(Test-Path $x){return (Resolve-Path $x).Path}}
 $found=Get-ChildItem -LiteralPath "PROJECT_ROOT" -Filter "PPSSPPWindows64.exe" -File -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
 if($found){return $found.FullName}
 throw "PPSSPPWindows64.exe not found. Set PPSSPP_EXE environment variable or keep an existing PPSSPP instance installed/running so its executable path can be read."
}
function Failure([string]$Reason){
@"
PROJECT: bia
STEP: STEP_070
TIME: $(Get-Date -Format o)
STATUS: FAILED
FAILURE_REASON:
$Reason
DEDICATED_PORT: $Port
OWN_STARTED_PID: $OwnPid
LAST_SUCCESSFUL_ACTION: $LastSuccessfulAction
NEXT_RECOMMENDED_ACTION:
Upload PROJECT_ROOT\log\fall_bia_STEP_070_int92_runtime_route_RESULT.zip.
"@|Set-Content (Join-Path $LogDir "FAILURE.txt") -Encoding UTF8
}

try{
 $Py=FindPython
 if(!(Test-Path $ISO)){throw "Missing Stage69 FIX2 ISO: $ISO"}
 State "start" "STEP070_runtime_route_discovery_started"
 $LastSuccessfulAction="STEP_070 marked IN_PROGRESS"

 $Port=Find-FreeBiaPort
 $Exe=Find-PPSSPP
 @"
[General]
RemoteISOPort = $Port
RemoteDebuggerOnStartup = True
RemoteDebuggerLocal = True
"@|Set-Content (Join-Path $LogDir "ppsspp_step070_append.ini") -Encoding ASCII

 @"
PPSSPP_EXE=$Exe
PORT=$Port
ISO=$ISO
"@|Set-Content (Join-Path $LogDir "launch_identity.txt") -Encoding UTF8

 $args=@("--appendconfig=$(Join-Path $LogDir 'ppsspp_step070_append.ini')",$ISO)
 $Proc=Start-Process -FilePath $Exe -ArgumentList $args -PassThru
 $OwnPid=$Proc.Id
 $LastSuccessfulAction="Dedicated PPSSPP launched PID=$OwnPid port=$Port"

 $old=$ErrorActionPreference;$ErrorActionPreference="Continue"
 try{
  & $Py (Join-Path $PSScriptRoot "scripts\runtime_route_discovery.py") `
    --port $Port `
    --expected-pid $OwnPid `
    --expected-iso $ISO `
    --outdir $OutDir `
    1> (Join-Path $LogDir "stdout.txt") `
    2> (Join-Path $LogDir "stderr.txt")
  $ec=$LASTEXITCODE
 }finally{$ErrorActionPreference=$old}
 if($ec -ne 0){throw "runtime_route_discovery.py failed ExitCode=$ec"}

 $report=Get-Content (Join-Path $OutDir "step070_report.json") -Raw -Encoding UTF8|ConvertFrom-Json
 $LastSuccessfulAction="Title/main-menu route screenshots and runtime memory samples captured"
 State "captured" ("STEP070_CAPTURED_runtimeLoadedKO_"+$report.runtime_loaded_korean+"_renderVerified_FALSE")
 $LastSuccessfulAction="STEP_070 route discovery captured"
}catch{
 $Failed=$true;$reason=$_|Out-String
 $reason|Set-Content (Join-Path $LogDir "stderr_powershell.txt") -Encoding UTF8
 try{Failure $reason}catch{}
 try{if($Py){State "failure" "STEP070_failed_no_campaign_status_promotion"}}catch{}
}finally{
 # Stop only the exact process launched by this step. Never touch another PPSSPP.
 if($Proc){
  try{
   $p=Get-Process -Id $OwnPid -ErrorAction SilentlyContinue
   if($p){Stop-Process -Id $OwnPid -Force -ErrorAction SilentlyContinue}
  }catch{}
 }
 try{Stop-Transcript|Out-Null}catch{}
 try{
  foreach($p in @(
   "PROJECT_ROOT\PROJECT_STATE.md",
   "PROJECT_ROOT\log\steps\STEP_070.md"
  )){
   if(Test-Path $p){Copy-Item $p $OutDir -Force}
  }
 }catch{($_|Out-String)|Set-Content (Join-Path $LogDir "collection_error.txt") -Encoding UTF8}

 $zip=if($Failed){$FailureZip}else{$SuccessZip}
 try{
  if(Test-Path $zip){Remove-Item $zip -Force}
  Compress-Archive -Path (Join-Path $LogDir "*") -DestinationPath $zip -Force
  if(!(Test-Path $zip)){throw "RESULT ZIP missing"}
 }catch{
  ($_|Out-String)|Set-Content (Join-Path $LogRoot "fall_STEP_070_ZIP_CREATION_FAILED.txt") -Encoding UTF8
 }

 Write-Host ""
 if($Failed){
  Write-Host "STEP_070 FAILED" -ForegroundColor Red
  Write-Host "Upload: $FailureZip"
 }else{
  Write-Host "STEP_070 ROUTE DISCOVERY CAPTURED" -ForegroundColor Green
  Write-Host "INT92 status remains BUILT_UNVERIFIED."
  Write-Host "Upload: $SuccessZip"
 }
}
if($Failed){exit 1}
