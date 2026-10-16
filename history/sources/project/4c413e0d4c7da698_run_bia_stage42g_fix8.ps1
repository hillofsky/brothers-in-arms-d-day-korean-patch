$ErrorActionPreference='Stop'
[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false)

$Root='PROJECT_ROOT'
$Iso=Join-Path $Root 'BIA_STAGE42G_GLOBAL_512_ATLAS_PROBE.iso'
$Analysis=Join-Path $Root 'analysis\stage42g_fix8_debugger_preflight'
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

function Start-BiaPPSSPP([string]$exe,[string]$iso){
  $launchRecords=@()

  foreach($p in 26420..26439){
    if(!(Test-FreePort $p)){continue}

    $startupLog=Join-Path $Analysis ("ppsspp_startup_{0}.log" -f $p)
    $args=@(
      "--debugger=$p",
      "--windowed",
      "--log=`"$startupLog`"",
      "`"$iso`""
    )

    $rec=[ordered]@{
      port=$p
      exe=$exe
      iso=$iso
      arguments=($args -join ' ')
      startup_log=$startupLog
      started=(Get-Date).ToString('s')
      pid=$null
      process_exited=$false
      exit_code=$null
      debugger_listening=$false
      wait_seconds=0
    }

    Write-Host "Launching BIA PPSSPP on dedicated debugger port $p..."
    $proc=Start-Process -FilePath $exe -ArgumentList $args -WorkingDirectory (Split-Path $exe -Parent) -PassThru
    $rec.pid=$proc.Id

    $deadline=(Get-Date).AddSeconds(12)
    while((Get-Date) -lt $deadline){
      $proc.Refresh()
      if($proc.HasExited){
        $rec.process_exited=$true
        try{$rec.exit_code=$proc.ExitCode}catch{}
        break
      }

      if(Test-Listening $p){
        $rec.debugger_listening=$true
        $rec.wait_seconds=[math]::Round((12-(($deadline-(Get-Date)).TotalSeconds)),2)
        $launchRecords += [pscustomobject]$rec
        $launchRecords | ConvertTo-Json -Depth 6 |
          Set-Content (Join-Path $Analysis 'ppsspp_launch_attempts.json') -Encoding UTF8

        Write-Host "Debugger port $p is LISTENING. PID=$($proc.Id)" -ForegroundColor Green
        return [pscustomobject]@{ Process=$proc; Port=$p }
      }

      Start-Sleep -Milliseconds 250
    }

    $rec.wait_seconds=12
    $launchRecords += [pscustomobject]$rec
    $launchRecords | ConvertTo-Json -Depth 6 |
      Set-Content (Join-Path $Analysis 'ppsspp_launch_attempts.json') -Encoding UTF8

    Write-Host "Port $p did not open; trying next BIA-dedicated port." -ForegroundColor Yellow
    try{
      if(!$proc.HasExited){Stop-Process -Id $proc.Id -Force -EA SilentlyContinue}
    }catch{}
    Start-Sleep -Milliseconds 500
  }

  throw 'PPSSPP did not expose a debugger on any dedicated BIA port 26420-26439'
}

function Archive([string]$p){
  if(Test-Path $p){
    $d=Join-Path $OldRoot $Stamp
    New-Item -ItemType Directory -Force $d|Out-Null
    Move-Item $p (Join-Path $d ([IO.Path]::GetFileName($p))) -Force
  }
}

function Pack([bool]$ok){
  $tmp=Join-Path $env:TEMP ("bia42g_fix8_"+[guid]::NewGuid().ToString('N'))
  New-Item -ItemType Directory -Force $tmp|Out-Null
  try{
    Get-ChildItem $Analysis -Recurse -File -EA SilentlyContinue|ForEach-Object{
      $rel=$_.FullName.Substring($Analysis.Length).TrimStart('\')
      $dst=Join-Path $tmp $rel
      New-Item -ItemType Directory -Force (Split-Path $dst)|Out-Null
      Copy-Item $_.FullName $dst -Force
    }
    Copy-Item (Join-Path $PSScriptRoot 'stage42g_fix8_register512.py'),$PSCommandPath -Destination $tmp -Force

    if($ok){$z=Join-Path $LogRoot 'bia_stage42g_fix8_upload.zip'}
    else{$z=Join-Path $LogRoot 'fail_bia_stage42g_fix8_upload.zip'}

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

  Write-Host '=== BIA STAGE42G FIX8: DEBUGGER PREFLIGHT + NON-BLOCKING AUTO-ENTRY ==='
  Write-Host 'BIA debugger ports: 26420-26439 only.'
  Write-Host 'PPSSPP is not handed to Python until its selected debugger port is confirmed LISTENING.'
  Write-Host 'No framebuffer reads occur before START / menu navigation.'
  Write-Host ''

  $launch=Start-BiaPPSSPP $P $Iso
  $Owned=$launch.Process
  $Port=[int]$launch.Port

  (("PID={0}`r`nPORT={1}`r`nEXE={2}`r`nISO={3}`r`n" -f $Owned.Id,$Port,$P,$Iso)) |
    Set-Content (Join-Path $Analysis 'ppsspp_selected_instance.txt') -Encoding UTF8

  $launcher=Get-Command py.exe -EA SilentlyContinue
  if($launcher){
    & $launcher.Source -3 (Join-Path $PSScriptRoot 'stage42g_fix8_register512.py') `
      --port $Port --out $Analysis --iso $Iso
  }else{
    $launcher=Get-Command python.exe -EA Stop
    & $launcher.Source (Join-Path $PSScriptRoot 'stage42g_fix8_register512.py') `
      --port $Port --out $Analysis --iso $Iso
  }

  if($LASTEXITCODE -ne 0){throw "Stage42G Fix8 runtime test failed: $LASTEXITCODE"}

  $r=Get-Content (Join-Path $Analysis 'stage42g_fix8_report.json') -Raw -Encoding UTF8|ConvertFrom-Json
  if(!$r.completed){throw 'Fix8 report completed=false'}
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
Write-Host 'STAGE42G FIX8 TEST COMPLETE' -ForegroundColor Green
