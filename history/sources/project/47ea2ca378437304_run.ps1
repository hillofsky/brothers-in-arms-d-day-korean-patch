$ErrorActionPreference="Stop"
[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false)
$env:PYTHONUTF8="1";$env:PYTHONIOENCODING="utf-8"

$Root="PROJECT_ROOT";$LogRoot="PROJECT_ROOT\log";$Attempt="STEP_070_FIX7"
$ISO="PROJECT_ROOT\BIA_STAGE69_FIX2_NONMDI_INT92_TEST.iso"
$Exe="LOCAL_PATH"
$LogDir=Join-Path $LogRoot $Attempt;$OutDir=Join-Path $LogDir "outputs";$ScriptsUsed=Join-Path $LogDir "scripts_used"
$SuccessZip=Join-Path $LogRoot "bia_STEP_070_FIX7_main_menu_route_RESULT.zip"
$FailureZip=Join-Path $LogRoot "fall_bia_STEP_070_FIX7_main_menu_route_RESULT.zip"
$Failed=$false;$Py=$null;$Proc=$null;$OwnPid=$null;$Port=$null;$LastSuccessfulAction="startup"

if(Test-Path $LogDir){
 $stamp=Get-Date -Format "yyyyMMdd_HHmmss";$archive=Join-Path $LogRoot "old\$stamp"
 New-Item -ItemType Directory -Force -Path $archive|Out-Null
 Move-Item $LogDir (Join-Path $archive $Attempt)
}
New-Item -ItemType Directory -Force -Path $LogRoot,$LogDir,$OutDir,$ScriptsUsed,(Join-Path $LogRoot "steps")|Out-Null
Copy-Item $PSCommandPath (Join-Path $ScriptsUsed "run.ps1") -Force
Copy-Item (Join-Path $PSScriptRoot "STEP_INFO.txt") $LogDir -Force
Copy-Item (Join-Path $PSScriptRoot "scripts\runtime_title_aware_fix7.py") $ScriptsUsed -Force
Copy-Item (Join-Path $PSScriptRoot "scripts\update_state.py") $ScriptsUsed -Force
Copy-Item (Join-Path $PSScriptRoot "reference\title_signature.json") $ScriptsUsed -Force
Copy-Item (Join-Path $PSScriptRoot "reference\title_reference.png") $OutDir -Force
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
 try{& $Py (Join-Path $PSScriptRoot "scripts\update_state.py") --root $Root --phase $Phase --detail $Detail;$ec=$LASTEXITCODE}
 finally{$ErrorActionPreference=$old}
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
  $c=Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue|Select-Object -First 1
  if($c){return [int]$c.OwningProcess}
 }catch{}
 foreach($line in (& netstat.exe -ano -p tcp)){
  if($line -match "^\s*TCP\s+\S+:$p\s+\S+\s+LISTENING\s+(\d+)\s*$"){return [int]$Matches[1]}
 }
 return $null
}
function Failure([string]$Reason){
@"
PROJECT: bia
STEP: STEP_070_FIX7
TIME: $(Get-Date -Format o)
STATUS: FAILED
FAILURE_REASON:
$Reason
PORT=$Port
OWN_PID=$OwnPid
LAST_SUCCESSFUL_ACTION=$LastSuccessfulAction
"@|Set-Content (Join-Path $LogDir "FAILURE.txt") -Encoding UTF8
}

try{
 $Py=FindPython
 if(!(Test-Path -LiteralPath $Exe)){throw "Known PPSSPP missing: $Exe"}
 if(!(Test-Path -LiteralPath $ISO)){throw "Stage69 FIX2 ISO missing: $ISO"}
 State "start" "STEP070_FIX7_title_aware_main_menu_route"

 $Port=FindPort
 $cfg=Join-Path $LogDir "ppsspp_step070_fix7_append.ini"
 @"
[General]
RemoteISOPort = $Port
RemoteDebuggerOnStartup = True
RemoteDebuggerLocal = True

[Graphics]
SoftwareRenderer = True
"@|Set-Content -LiteralPath $cfg -Encoding ASCII

 Write-Host "[1/4] Launching exact PPSSPP + software renderer..." -ForegroundColor Cyan
 $Proc=Start-Process -FilePath $Exe -ArgumentList @("--appendconfig=$cfg",$ISO) -PassThru
 $OwnPid=$Proc.Id

 Write-Host "[2/4] Verifying listener PID and ISO..." -ForegroundColor Cyan
 $listenerPid=$null
 for($i=0;$i -lt 60;$i++){
  $listenerPid=GetListenerPid $Port
  if($listenerPid){break}
  if($Proc.HasExited){throw "PPSSPP exited before debugger listener"}
  Start-Sleep -Milliseconds 500
 }
 if(-not $listenerPid){throw "Debugger listener missing"}
 if([int]$listenerPid -ne [int]$OwnPid){throw "Listener PID mismatch $listenerPid != $OwnPid"}
 $cmd=[string](Get-CimInstance Win32_Process -Filter "ProcessId=$OwnPid").CommandLine
 if($cmd.IndexOf($ISO,[StringComparison]::OrdinalIgnoreCase)-lt 0){throw "Exact ISO missing from command line"}

 Write-Host "[3/4] Seeking known title frame, then capturing main-menu positions..." -ForegroundColor Cyan
 $old=$ErrorActionPreference;$ErrorActionPreference="Continue"
 try{
  & $Py (Join-Path $PSScriptRoot "scripts\runtime_title_aware_fix7.py") `
    --port $Port --outdir $OutDir `
    --title-signature (Join-Path $PSScriptRoot "reference\title_signature.json") `
    1> (Join-Path $LogDir "stdout.txt") 2> (Join-Path $LogDir "stderr.txt")
  $ec=$LASTEXITCODE
 }finally{$ErrorActionPreference=$old}
 if($ec -ne 0){throw "runtime_title_aware_fix7.py failed ExitCode=$ec"}

 $r=Get-Content (Join-Path $OutDir "step070_fix7_report.json") -Raw -Encoding UTF8|ConvertFrom-Json
 State "captured" "STEP070_FIX7_MAIN_MENU_ROUTE_CAPTURED_no_confirm"
 $LastSuccessfulAction="main menu route captured"
 Write-Host "[4/4] Main-menu route capture complete." -ForegroundColor Green
}catch{
 $Failed=$true;$reason=$_|Out-String
 $reason|Set-Content (Join-Path $LogDir "stderr_powershell.txt") -Encoding UTF8
 try{Failure $reason}catch{}
 try{if($Py){State "failure" "STEP070_FIX7_failed_no_status_promotion"}}catch{}
}finally{
 if($OwnPid){
  try{$p=Get-Process -Id $OwnPid -ErrorAction SilentlyContinue;if($p){Stop-Process -Id $OwnPid -Force -ErrorAction SilentlyContinue}}catch{}
 }
 try{Stop-Transcript|Out-Null}catch{}
 foreach($p in @("PROJECT_ROOT\PROJECT_STATE.md","PROJECT_ROOT\log\steps\STEP_070_FIX7.md")){
  if(Test-Path $p){Copy-Item $p $OutDir -Force -ErrorAction SilentlyContinue}
 }
 $zip=if($Failed){$FailureZip}else{$SuccessZip}
 try{
  if(Test-Path $zip){Remove-Item $zip -Force}
  Compress-Archive -Path (Join-Path $LogDir "*") -DestinationPath $zip -Force
 }catch{}
 if($Failed){
  Write-Host "STEP_070 FIX7 FAILED" -ForegroundColor Red
  Write-Host "Upload: $FailureZip"
 }else{
  Write-Host "STEP_070 FIX7 MAIN-MENU ROUTE CAPTURED" -ForegroundColor Green
  Write-Host "Upload: $SuccessZip"
 }
}
if($Failed){exit 1}
