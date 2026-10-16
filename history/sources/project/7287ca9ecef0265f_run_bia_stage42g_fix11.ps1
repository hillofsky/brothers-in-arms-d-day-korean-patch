$ErrorActionPreference='Stop'
[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false)

$Root='PROJECT_ROOT'
$Iso=Join-Path $Root 'BIA_STAGE42G_GLOBAL_512_ATLAS_PROBE.iso'
$Analysis=Join-Path $Root 'analysis\stage42g_fix9_dedicated_config_port'
$LogRoot=Join-Path $Root 'log'
$OldRoot=Join-Path $LogRoot 'old'
$Stamp=Get-Date -Format 'yyyyMMdd_HHmmss'
$Owned=$null
$Port=$null
$Success=$false

New-Item -ItemType Directory -Force $Analysis,$LogRoot,$OldRoot|Out-Null
Remove-Item (Join-Path $Analysis '*') -Recurse -Force -EA SilentlyContinue

function Find-PPSSPP {
  $c=@(
    'LOCAL_PATH',
    'PROJECT_ROOT\PPSSPPWindows64.exe'
  )
  foreach($p in $c){if(Test-Path $p){return $p}}
  $f=Get-ChildItem 'LOCAL_PATH' -Filter PPSSPPWindows64.exe -Recurse -File -EA SilentlyContinue |
      Sort-Object LastWriteTime -Descending | Select-Object -First 1
  if($f){return $f.FullName}
  throw 'PPSSPPWindows64.exe not found'
}

function Test-FreePort([int]$p){
  $l=$null
  try{
    $l=[Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback,$p)
    $l.Start()
    return $true
  }catch{
    return $false
  }finally{
    if($l){try{$l.Stop()}catch{}}
  }
}

function Test-Listening([int]$p){
  $c=$null
  try{
    $c=[Net.Sockets.TcpClient]::new()
    $iar=$c.BeginConnect('127.0.0.1',$p,$null,$null)
    if(!$iar.AsyncWaitHandle.WaitOne(250)){return $false}
    $c.EndConnect($iar)
    return $true
  }catch{
    return $false
  }finally{
    if($c){try{$c.Close()}catch{}}
  }
}

function Get-ReportedDebuggerPorts([string]$logPath){
  if(!(Test-Path $logPath)){return @()}
  $txt=Get-Content $logPath -Raw -EA SilentlyContinue
  if(!$txt){return @()}
  $m=[regex]::Matches($txt,'debugger-webserver.*?(?:port\s+)(\d+)|server started on port\s+(\d+):\s+debugger-webserver')
  $ports=@()
  foreach($x in $m){
    $v=$null
    if($x.Groups[1].Success){$v=$x.Groups[1].Value}
    elseif($x.Groups[2].Success){$v=$x.Groups[2].Value}
    if($v){$ports += [int]$v}
  }
  return @($ports | Select-Object -Unique)
}

function Start-BiaPPSSPP([string]$exe,[string]$iso){
  $records=@()

  foreach($p in 26420..26439){
    if(!(Test-FreePort $p)){continue}

    $startupLog=Join-Path $Analysis ("ppsspp_startup_{0}.log" -f $p)
    $appendCfg=Join-Path $Analysis ("bia_debugger_{0}.ini" -f $p)

    # IMPORTANT:
    # The user's PPSSPP v1.20.4 empirically ignored the numeric value in
    # --debugger=264xx and always opened the server on 26222.
    # Override the real config keys instead. --appendconfig was introduced to
    # merge per-launch config differences without modifying the user's main INI.
    @"
[General]
RemoteISOPort = $p
RemoteDebuggerOnStartup = True
RemoteDebuggerLocal = True
"@ | Set-Content $appendCfg -Encoding ASCII

    $args=@(
      "--appendconfig=`"$appendCfg`"",
      "--windowed",
      "--log=`"$startupLog`"",
      "`"$iso`""
    )

    $rec=[ordered]@{
      port=$p
      mode='appendconfig'
      exe=$exe
      iso=$iso
      append_config=$appendCfg
      arguments=($args -join ' ')
      startup_log=$startupLog
      started=(Get-Date).ToString('s')
      pid=$null
      process_exited=$false
      exit_code=$null
      debugger_listening=$false
      reported_debugger_ports=@()
      wait_seconds=0
    }

    Write-Host "Launching BIA PPSSPP with RemoteISOPort=$p via temporary append-config..."
    $proc=Start-Process -FilePath $exe -ArgumentList $args -WorkingDirectory (Split-Path $exe -Parent) -PassThru
    $rec.pid=$proc.Id

    $deadline=(Get-Date).AddSeconds(15)
    while((Get-Date) -lt $deadline){
      $proc.Refresh()
      if($proc.HasExited){
        $rec.process_exited=$true
        try{$rec.exit_code=$proc.ExitCode}catch{}
        break
      }

      if(Test-Listening $p){
        $rec.debugger_listening=$true
        $rec.wait_seconds=[math]::Round((15-(($deadline-(Get-Date)).TotalSeconds)),2)
        $rec.reported_debugger_ports=@(Get-ReportedDebuggerPorts $startupLog)

        $records += [pscustomobject]$rec
        $records | ConvertTo-Json -Depth 8 |
          Set-Content (Join-Path $Analysis 'ppsspp_launch_attempts.json') -Encoding UTF8

        Write-Host "BIA debugger is LISTENING on dedicated port $p. PID=$($proc.Id)" -ForegroundColor Green
        return [pscustomobject]@{Process=$proc;Port=$p}
      }

      Start-Sleep -Milliseconds 250
    }

    $rec.wait_seconds=15
    $rec.reported_debugger_ports=@(Get-ReportedDebuggerPorts $startupLog)
    $records += [pscustomobject]$rec
    $records | ConvertTo-Json -Depth 8 |
      Set-Content (Join-Path $Analysis 'ppsspp_launch_attempts.json') -Encoding UTF8

    if($rec.reported_debugger_ports.Count -gt 0){
      Write-Host ("Requested {0}, PPSSPP reported debugger port(s): {1}" -f $p,($rec.reported_debugger_ports -join ',')) -ForegroundColor Yellow
    }else{
      Write-Host "Requested $p but no debugger server was reported." -ForegroundColor Yellow
    }

    try{
      if(!$proc.HasExited){Stop-Process -Id $proc.Id -Force -EA SilentlyContinue}
    }catch{}
    Start-Sleep -Milliseconds 500
  }

  throw 'PPSSPP did not expose a debugger on any BIA-dedicated port 26420-26439, even via RemoteISOPort append-config'
}

function Archive([string]$p){
  if(Test-Path $p){
    $d=Join-Path $OldRoot $Stamp
    New-Item -ItemType Directory -Force $d|Out-Null
    Move-Item $p (Join-Path $d ([IO.Path]::GetFileName($p))) -Force
  }
}

function Pack([bool]$ok){
  $tmp=Join-Path $env:TEMP ("bia42g_fix11_"+[guid]::NewGuid().ToString('N'))
  New-Item -ItemType Directory -Force $tmp|Out-Null
  try{
    Get-ChildItem $Analysis -Recurse -File -EA SilentlyContinue|ForEach-Object{
      $rel=$_.FullName.Substring($Analysis.Length).TrimStart('\')
      $dst=Join-Path $tmp $rel
      New-Item -ItemType Directory -Force (Split-Path $dst)|Out-Null
      Copy-Item $_.FullName $dst -Force
    }
    Copy-Item (Join-Path $PSScriptRoot 'stage42g_fix11_register512.py'),$PSCommandPath -Destination $tmp -Force

    if($ok){$z=Join-Path $LogRoot 'bia_stage42g_fix11_upload.zip'}
    else{$z=Join-Path $LogRoot 'fail_bia_stage42g_fix11_upload.zip'}

    Archive $z
    Compress-Archive (Join-Path $tmp '*') $z -Force
    Write-Host "`nUpload ZIP: $z"
  }finally{
    Remove-Item $tmp -Recurse -Force -EA SilentlyContinue
  }
}

try{
  if(!(Test-Path $Iso)){throw "Missing Stage42G ISO: $Iso"}

  $P=Find-PPSSPP

  Write-Host '=== BIA STAGE42G FIX11: BAKER-EVENT-ANCHORED 512x512 PROOF ==='
  Write-Host 'Fix8 evidence: PPSSPP ignored --debugger=264xx and opened 26222 every time.'
  Write-Host 'Fix9 does NOT use --debugger=<port>.'
  Write-Host 'It injects temporary per-launch config:'
  Write-Host '  RemoteISOPort = 26420..26439'
  Write-Host '  RemoteDebuggerOnStartup = True'
  Write-Host '  RemoteDebuggerLocal = True'
  Write-Host 'The user PPSSPP.ini is not modified.'
  Write-Host 'Auto-entry: startup Bink 관찰 -> 종료 확인 + 5초, 또는 Bink 미검출 12초 후 START.'
  Write-Host 'START 이후 8초, Story 이후 3.5초, New Game 이후 3.5초 대기합니다.'
  Write-Host '첫 베이커 ST1 read watchpoint를 잡은 직후 자막 영역을 연속 캡처합니다.'
  Write-Host ''

  $launch=Start-BiaPPSSPP $P $Iso
  $Owned=$launch.Process
  $Port=[int]$launch.Port

  (("PID={0}`r`nPORT={1}`r`nEXE={2}`r`nISO={3}`r`n" -f $Owned.Id,$Port,$P,$Iso)) |
    Set-Content (Join-Path $Analysis 'ppsspp_selected_instance.txt') -Encoding UTF8

  $launcher=Get-Command py.exe -EA SilentlyContinue
  if($launcher){
    & $launcher.Source -3 (Join-Path $PSScriptRoot 'stage42g_fix11_register512.py') `
      --port $Port --out $Analysis --iso $Iso
  }else{
    $launcher=Get-Command python.exe -EA Stop
    & $launcher.Source (Join-Path $PSScriptRoot 'stage42g_fix11_register512.py') `
      --port $Port --out $Analysis --iso $Iso
  }

  if($LASTEXITCODE -ne 0){throw "Stage42G Fix11 runtime test failed: $LASTEXITCODE"}

  $r=Get-Content (Join-Path $Analysis 'stage42g_fix11_report.json') -Raw -Encoding UTF8|ConvertFrom-Json
  if(!$r.completed){throw 'Fix11 report completed=false'}
  $Success=$true
}catch{
  $_|Out-String|Set-Content (Join-Path $Analysis 'FAILURE.txt') -Encoding UTF8
  Write-Host "FAILED: $($_.Exception.Message)" -ForegroundColor Red
}finally{
  if($Owned){
    try{if(!$Owned.HasExited){Stop-Process -Id $Owned.Id -Force -EA SilentlyContinue}}catch{}
  }
  Pack $Success
}

if(!$Success){exit 1}
Write-Host ''
Write-Host 'STAGE42G FIX11 TEST COMPLETE' -ForegroundColor Green
