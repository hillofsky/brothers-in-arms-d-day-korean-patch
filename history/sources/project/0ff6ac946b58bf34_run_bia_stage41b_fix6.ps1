$ErrorActionPreference='Stop'
[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false)

$Root='PROJECT_ROOT'
$Iso=Join-Path $Root 'BIA_STAGE41A_FIRST_MOVIE_KO_SUB_TEST.iso'
$Analysis=Join-Path $Root 'analysis\stage41b_fix6_stepping'
$LogRoot=Join-Path $Root 'log'
$OldRoot=Join-Path $LogRoot 'old'
$Stamp=Get-Date -Format 'yyyyMMdd_HHmmss'
$Py=Join-Path $PSScriptRoot 'stage41b_fix6_trace.py'
$Owned=$null
$Success=$false

New-Item -ItemType Directory -Force $Analysis,$LogRoot,$OldRoot|Out-Null
Get-ChildItem $Analysis -File -EA SilentlyContinue|Remove-Item -Force -EA SilentlyContinue

function Find-PPSSPP {
  $c=@(
    'LOCAL_PATH',
    'PROJECT_ROOT\PPSSPPWindows64.exe'
  )
  foreach($p in $c){if(Test-Path $p){return $p}}
  $f=Get-ChildItem 'LOCAL_PATH' -Filter PPSSPPWindows64.exe -Recurse -File -EA SilentlyContinue |
      Sort-Object LastWriteTime -Descending|Select-Object -First 1
  if($f){return $f.FullName}
  throw 'PPSSPPWindows64.exe not found'
}
function Free-Port {
  foreach($p in 26222..26350){
    $l=$null
    try{$l=[Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback,$p);$l.Start();$l.Stop();return $p}
    catch{if($l){try{$l.Stop()}catch{}}}
  }
  throw 'No free debugger port'
}
function Archive([string]$p){
  if(Test-Path $p){
    $d=Join-Path $OldRoot $Stamp
    New-Item -ItemType Directory -Force $d|Out-Null
    Move-Item $p (Join-Path $d ([IO.Path]::GetFileName($p))) -Force
  }
}
function Pack([bool]$ok){
  $tmp=Join-Path $Analysis '_pkg'
  Remove-Item $tmp -Recurse -Force -EA SilentlyContinue
  New-Item -ItemType Directory -Force $tmp|Out-Null
  Get-ChildItem $Analysis -File -EA SilentlyContinue|Copy-Item -Destination $tmp -Force
  Copy-Item $Py,$PSCommandPath -Destination $tmp -Force
  if($ok){$z=Join-Path $LogRoot 'bia_stage41b_fix6_upload.zip'}
  else{$z=Join-Path $LogRoot 'fail_bia_stage41b_fix6_upload.zip'}
  Archive $z
  Compress-Archive (Join-Path $tmp '*') $z -Force
  Remove-Item $tmp -Recurse -Force -EA SilentlyContinue
  Write-Host "`nUpload ZIP: $z"
}

try{
  if(!(Test-Path $Iso)){throw "Missing ISO: $Iso"}
  $P=Find-PPSSPP
  $Port=Free-Port

  Write-Host '=== BIA STAGE41B FIX6 ==='
  Write-Host '자동 진입: START -> 스토리 -> 새 게임 -> 보통'
  Write-Host 'Fix5에서 확인된 cpu.stepping 이벤트를 직접 캡처합니다.'
  Write-Host 'ST1 read breakpoint가 CPU를 멈추면 PC/레지스터/backtrace/disasm을 저장하고 자동 재개합니다.'
  Write-Host ''

  # Interpreter mode is intentional for reliable memory read breakpoints.
  $Owned=Start-Process -FilePath $P -ArgumentList "-i --debugger=$Port `"$Iso`"" -PassThru
  Start-Sleep -Milliseconds 1000

  $launcher=Get-Command py.exe -EA SilentlyContinue
  if($launcher){& $launcher.Source -3 $Py --port $Port --out $Analysis --iso $Iso}
  else{$launcher=Get-Command python.exe -EA Stop;& $launcher.Source $Py --port $Port --out $Analysis --iso $Iso}

  if($LASTEXITCODE -ne 0){throw "Tracer exit code $LASTEXITCODE"}

  $report=Join-Path $Analysis 'stage41b_fix6_report.json'
  if(!(Test-Path $report)){throw 'stage41b_fix6_report.json missing'}
  $r=Get-Content $report -Raw -Encoding UTF8|ConvertFrom-Json
  if(!$r.completed){throw 'Report completed=false'}
  $Success=$true
}catch{
  $_|Out-String|Set-Content (Join-Path $Analysis 'FAILURE.txt') -Encoding UTF8
  Write-Host "FAILED: $($_.Exception.Message)" -ForegroundColor Red
}finally{
  if($Owned){try{if(!$Owned.HasExited){Stop-Process -Id $Owned.Id -Force -EA SilentlyContinue}}catch{}}
  Pack $Success
}
if(!$Success){exit 1}
Write-Host 'STAGE41B FIX6 SUCCESS' -ForegroundColor Green
