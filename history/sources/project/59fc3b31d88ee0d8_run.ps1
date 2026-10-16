$ErrorActionPreference="Stop"
[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false)
$env:PYTHONUTF8="1";$env:PYTHONIOENCODING="utf-8"
$Root="PROJECT_ROOT";$LogRoot="$Root\log";$Attempt="STEP_071_FIX1"
$ISO="$Root\BIA_STAGE69_FIX2_NONMDI_INT92_TEST.iso"
$Exe="LOCAL_PATH"
$LogDir="$LogRoot\$Attempt";$OutDir="$LogDir\outputs";$Scripts="$LogDir\scripts_used"
$OK="$LogRoot\bia_STEP_071_FIX1_solo_int92_canary_RESULT.zip";$FAIL="$LogRoot\fall_bia_STEP_071_FIX1_solo_int92_canary_RESULT.zip"
$Failed=$false;$Proc=$null;$OwnPid=$null;$Port=$null
if(Test-Path $LogDir){$s=Get-Date -Format yyyyMMdd_HHmmss;New-Item -ItemType Directory -Force "$LogRoot\old\$s"|Out-Null;Move-Item $LogDir "$LogRoot\old\$s\STEP_071_FIX1"}
New-Item -ItemType Directory -Force $LogDir,$OutDir,$Scripts|Out-Null
Copy-Item $PSCommandPath "$Scripts\run.ps1";Copy-Item "$PSScriptRoot\scripts\*" $Scripts -Force;Copy-Item "$PSScriptRoot\reference\*.json" $Scripts -Force
try{Start-Transcript "$LogDir\run.log" -Force|Out-Null}catch{}
function FreePort{
 foreach($p in 26420..26439){try{$l=[Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback,$p);$l.Start();$l.Stop();return $p}catch{}}
 throw "No free debugger port"
}
function LP([int]$p){
 try{$c=Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue|Select-Object -First 1;if($c){return [int]$c.OwningProcess}}catch{}
 foreach($x in (& netstat -ano -p tcp)){if($x -match "^\s*TCP\s+\S+:$p\s+\S+\s+LISTENING\s+(\d+)"){return [int]$Matches[1]}}
}
try{
 $Py="LOCAL_PATH"
 if(!(Test-Path $Py)){throw "Python missing"}
 if(!(Test-Path $Exe)){throw "PPSSPP missing"}
 if(!(Test-Path $ISO)){throw "ISO missing"}
 $Port=FreePort
 $cfg="$LogDir\append.ini"
 @"
[General]
RemoteISOPort = $Port
RemoteDebuggerOnStartup = True
RemoteDebuggerLocal = True
[Graphics]
SoftwareRenderer = True
"@|Set-Content $cfg -Encoding ASCII
 Write-Host "[1/3] Launching PPSSPP..." -ForegroundColor Cyan
 $Proc=Start-Process $Exe -ArgumentList @("--appendconfig=$cfg",$ISO) -PassThru;$OwnPid=$Proc.Id
 for($i=0;$i -lt 60;$i++){ $q=LP $Port;if($q){break};Start-Sleep -Milliseconds 500 }
 if(!$q -or [int]$q -ne [int]$OwnPid){throw "Debugger PID mismatch"}
 $cmd=[string](Get-CimInstance Win32_Process -Filter "ProcessId=$OwnPid").CommandLine
 if($cmd.IndexOf($ISO,[StringComparison]::OrdinalIgnoreCase)-lt 0){throw "ISO command-line mismatch"}
 Write-Host "[2/3] Entering Skirmish -> Solo Mode once..." -ForegroundColor Cyan
 $old=$ErrorActionPreference;$ErrorActionPreference="Continue"
 try{
  & $Py "$PSScriptRoot\scripts\step071_fix1.py" --port $Port --outdir $OutDir --sigs "$PSScriptRoot\reference\screen_signatures.json" --targets "$PSScriptRoot\reference\int92_targets.json" 1>"$LogDir\stdout.txt" 2>"$LogDir\stderr.txt"
  $ec=$LASTEXITCODE
 }finally{$ErrorActionPreference=$old}
 if($ec -ne 0){throw "step071_fix1.py failed $ec"}
 Write-Host "[3/3] Final INT92 canary complete." -ForegroundColor Green
}catch{
 $Failed=$true;($_|Out-String)|Set-Content "$LogDir\FAILURE.txt" -Encoding UTF8
}finally{
 if($OwnPid){try{$p=Get-Process -Id $OwnPid -ErrorAction SilentlyContinue;if($p){Stop-Process -Id $OwnPid -Force}}catch{}}
 try{Stop-Transcript|Out-Null}catch{}
 $zip=if($Failed){$FAIL}else{$OK}
 if(Test-Path $zip){Remove-Item $zip -Force}
 Compress-Archive "$LogDir\*" $zip -Force
 if($Failed){Write-Host "FAILED: $FAIL" -ForegroundColor Red}else{Write-Host "Upload: $OK" -ForegroundColor Green}
}
if($Failed){exit 1}
