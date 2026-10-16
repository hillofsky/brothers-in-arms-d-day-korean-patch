$ErrorActionPreference='Stop'
[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false)

$Root='PROJECT_ROOT'
$Iso=Join-Path $Root 'BIA_STAGE41F_FIRST_MOVIE_FULL_KO_TEST.iso'
$Analysis=Join-Path $Root 'analysis\stage41f_autoentry_fix1'
$LogRoot=Join-Path $Root 'log'
$OldRoot=Join-Path $LogRoot 'old'
$Stamp=Get-Date -Format 'yyyyMMdd_HHmmss'
$Py=Join-Path $PSScriptRoot 'stage41f_autoentry_fix1.py'
$Owned=$null
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
      Sort-Object LastWriteTime -Descending|Select-Object -First 1
  if($f){return $f.FullName}
  throw 'PPSSPPWindows64.exe not found'
}
function Free-Port {
  foreach($p in 26222..26350){
    $l=$null
    try{
      $l=[Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback,$p)
      $l.Start();$l.Stop();return $p
    }catch{if($l){try{$l.Stop()}catch{}}}
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
  $tmp=Join-Path $env:TEMP ("bia41f_autoentry_fix1_"+[guid]::NewGuid().ToString('N'))
  New-Item -ItemType Directory -Force $tmp|Out-Null
  try{
    Get-ChildItem $Analysis -Recurse -File -EA SilentlyContinue|ForEach-Object{
      $rel=$_.FullName.Substring($Analysis.Length).TrimStart('\')
      $dst=Join-Path $tmp $rel
      New-Item -ItemType Directory -Force (Split-Path $dst)|Out-Null
      Copy-Item $_.FullName $dst -Force
    }
    Copy-Item $Py,$PSCommandPath -Destination $tmp -Force
    if($ok){$z=Join-Path $LogRoot 'bia_stage41f_autoentry_fix1_upload.zip'}
    else{$z=Join-Path $LogRoot 'fail_bia_stage41f_autoentry_fix1_upload.zip'}
    Archive $z
    Compress-Archive (Join-Path $tmp '*') $z -Force
    Write-Host "`nUpload ZIP: $z"
  }finally{
    Remove-Item $tmp -Recurse -Force -EA SilentlyContinue
  }
}

try{
  if(!(Test-Path $Iso)){throw "Missing Stage41F ISO: $Iso"}
  $P=Find-PPSSPP
  $Port=Free-Port

  Write-Host '=== BIA STAGE41F AUTO-ENTRY FIX1 ==='
  Write-Host '스크린샷 진단 결과를 반영한 보정 경로입니다.'
  Write-Host 'START 1회 -> 6초 대기 -> CROSS -> 2초 -> CROSS -> 2초 -> CROSS'
  Write-Host '기존의 반복 START/CROSS와 DOWN 입력은 제거했습니다.'
  Write-Host ''

  $Owned=Start-Process -FilePath $P -ArgumentList "--debugger=$Port `"$Iso`"" -PassThru
  Start-Sleep -Milliseconds 1000

  $launcher=Get-Command py.exe -EA SilentlyContinue
  if($launcher){
    & $launcher.Source -3 $Py --port $Port --out $Analysis --iso $Iso
  }else{
    $launcher=Get-Command python.exe -EA Stop
    & $launcher.Source $Py --port $Port --out $Analysis --iso $Iso
  }
  if($LASTEXITCODE -ne 0){throw "Auto-entry fix exit code $LASTEXITCODE"}

  $r=Get-Content (Join-Path $Analysis 'stage41f_autoentry_fix1_report.json') -Raw -Encoding UTF8|ConvertFrom-Json
  if(!$r.completed){throw 'auto-entry report completed=false'}
  $Success=$true
}catch{
  $_|Out-String|Set-Content (Join-Path $Analysis 'FAILURE.txt') -Encoding UTF8
  Write-Host "FAILED: $($_.Exception.Message)" -ForegroundColor Red
}finally{
  if($Owned){try{if(!$Owned.HasExited){Stop-Process -Id $Owned.Id -Force -EA SilentlyContinue}}catch{}}
  Pack $Success
}

if(!$Success){exit 1}
Write-Host ''
Write-Host 'STAGE41F AUTO-ENTRY FIX1 SUCCESS' -ForegroundColor Green
