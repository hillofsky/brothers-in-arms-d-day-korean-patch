$ErrorActionPreference='Stop'
[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false)

$Root='PROJECT_ROOT'
$Iso=Join-Path $Root 'BIA_STAGE42G_GLOBAL_512_ATLAS_PROBE.iso'
$Analysis=Join-Path $Root 'analysis\stage42g_fix7_register512'
$LogRoot=Join-Path $Root 'log'
$OldRoot=Join-Path $LogRoot 'old'
$Stamp=Get-Date -Format 'yyyyMMdd_HHmmss'
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
      Sort-Object LastWriteTime -Descending | Select-Object -First 1
  if($f){return $f.FullName}
  throw 'PPSSPPWindows64.exe not found'
}
function Bia-Port {
  # Dedicated BIA range only. Do not touch the shared 26222-26350 range.
  foreach($p in 26420..26439){
    $l=$null
    try{
      $l=[Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback,$p)
      $l.Start();$l.Stop()
      return $p
    }catch{
      if($l){try{$l.Stop()}catch{}}
    }
  }
  throw 'No free BIA debugger port in dedicated range 26420-26439'
}
function Archive([string]$p){
  if(Test-Path $p){
    $d=Join-Path $OldRoot $Stamp
    New-Item -ItemType Directory -Force $d|Out-Null
    Move-Item $p (Join-Path $d ([IO.Path]::GetFileName($p))) -Force
  }
}
function Pack([bool]$ok){
  $tmp=Join-Path $env:TEMP ("bia42g_fix7_"+[guid]::NewGuid().ToString('N'))
  New-Item -ItemType Directory -Force $tmp|Out-Null
  try{
    Get-ChildItem $Analysis -Recurse -File -EA SilentlyContinue|ForEach-Object{
      $rel=$_.FullName.Substring($Analysis.Length).TrimStart('\')
      $dst=Join-Path $tmp $rel
      New-Item -ItemType Directory -Force (Split-Path $dst)|Out-Null
      Copy-Item $_.FullName $dst -Force
    }
    Copy-Item (Join-Path $PSScriptRoot 'stage42g_fix7_register512.py'),$PSCommandPath -Destination $tmp -Force
    if($ok){$z=Join-Path $LogRoot 'bia_stage42g_fix7_upload.zip'}
    else{$z=Join-Path $LogRoot 'fail_bia_stage42g_fix7_upload.zip'}
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
  $Port=Bia-Port

  Write-Host '=== BIA STAGE42G FIX7: NON-BLOCKING AUTO-ENTRY + 512x512 PROOF ==='
  Write-Host "BIA dedicated debugger port: $Port"
  Write-Host 'Fix7 auto-entry: 진입 전 스크린샷/VRAM 읽기 없이 6초 후 START를 즉시 자동 입력합니다.'
  Write-Host 'Code RAM is not modified.'
  Write-Host 'At the subtitle texture call site 0x0893D980, live arguments are changed:'
  Write-Host '  a1: 256 -> 512   (width)'
  Write-Host '  a2: 128 -> 512   (height)'
  Write-Host '  a3: 256 -> 512   (tbw)'
  Write-Host ''

  $Owned=Start-Process -FilePath $P -ArgumentList "--debugger=$Port `"$Iso`"" -PassThru
  Start-Sleep -Milliseconds 1000

  $launcher=Get-Command py.exe -EA SilentlyContinue
  if($launcher){
    & $launcher.Source -3 (Join-Path $PSScriptRoot 'stage42g_fix7_register512.py') `
      --port $Port --out $Analysis --iso $Iso
  }else{
    $launcher=Get-Command python.exe -EA Stop
    & $launcher.Source (Join-Path $PSScriptRoot 'stage42g_fix7_register512.py') `
      --port $Port --out $Analysis --iso $Iso
  }

  if($LASTEXITCODE -ne 0){throw "Stage42G Fix7 runtime test failed: $LASTEXITCODE"}

  $r=Get-Content (Join-Path $Analysis 'stage42g_fix7_report.json') -Raw -Encoding UTF8|ConvertFrom-Json
  if(!$r.completed){throw 'Fix7 report completed=false'}
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
Write-Host 'STAGE42G FIX7 TEST COMPLETE' -ForegroundColor Green
