$ErrorActionPreference='Stop'
[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false)

$Root='PROJECT_ROOT'
$Source=Join-Path $Root 'BIA_STAGE42G_GLOBAL_512_ATLAS_PROBE.iso'
$Output=Join-Path $Root 'BIA_STAGE42G_FIX3_512_DIMENSION_PATCH.iso'
$Analysis=Join-Path $Root 'analysis\stage42g_fix3_512_dimension'
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
  $tmp=Join-Path $env:TEMP ("bia42g_fix3_"+[guid]::NewGuid().ToString('N'))
  New-Item -ItemType Directory -Force $tmp|Out-Null
  try{
    Get-ChildItem $Analysis -Recurse -File -EA SilentlyContinue|ForEach-Object{
      $rel=$_.FullName.Substring($Analysis.Length).TrimStart('\')
      $dst=Join-Path $tmp $rel
      New-Item -ItemType Directory -Force (Split-Path $dst)|Out-Null
      Copy-Item $_.FullName $dst -Force
    }
    Copy-Item (Join-Path $PSScriptRoot 'build_stage42g_fix3.py'),$PSCommandPath -Destination $tmp -Force
    if($ok){$z=Join-Path $LogRoot 'bia_stage42g_fix3_upload.zip'}
    else{$z=Join-Path $LogRoot 'fail_bia_stage42g_fix3_upload.zip'}
    Archive $z
    Compress-Archive (Join-Path $tmp '*') $z -Force
    Write-Host "`nUpload ZIP: $z"
  }finally{
    Remove-Item $tmp -Recurse -Force -EA SilentlyContinue
  }
}

try{
  if(!(Test-Path $Source)){throw "Missing Stage42G ISO: $Source"}
  if(Test-Path $Output){Remove-Item $Output -Force}

  $launcher=Get-Command py.exe -EA SilentlyContinue
  if($launcher){$Python=$launcher.Source;$PyPrefix=@('-3')}
  else{$launcher=Get-Command python.exe -EA Stop;$Python=$launcher.Source;$PyPrefix=@()}

  Write-Host '=== BIA STAGE42G FIX3: 512x512 TEXTURE DIMENSION PATCH ==='
  Write-Host 'Fix2에서 확인한 텍스처 인자만 변경합니다:'
  Write-Host '  0x0893D968 : 0x80  -> 0x200  (height 128 -> 512)'
  Write-Host '  0x0893D96C : 0x100 -> 0x200  (width/tbw 256 -> 512)'
  Write-Host 'PRX/BIN에서 relocation-independent MIPS signature를 찾아 정확히 1곳일 때만 패치합니다.'
  Write-Host ''

  & $Python @PyPrefix (Join-Path $PSScriptRoot 'build_stage42g_fix3.py') `
    --source $Source --output $Output `
    --report (Join-Path $Analysis 'stage42g_fix3_build_report.json')
  if($LASTEXITCODE -ne 0){throw "Stage42G Fix3 build failed: $LASTEXITCODE"}

  $P=Find-PPSSPP
  $Port=Free-Port
  $Owned=Start-Process -FilePath $P -ArgumentList "--debugger=$Port `"$Output`"" -PassThru
  Start-Sleep -Milliseconds 1000

  & $Python @PyPrefix (Join-Path $PSScriptRoot 'stage42g_fix3_auto_test.py') `
    --port $Port --out $Analysis --iso $Output
  if($LASTEXITCODE -ne 0){throw "Stage42G Fix3 runtime test failed: $LASTEXITCODE"}

  $r=Get-Content (Join-Path $Analysis 'stage42g_fix3_report.json') -Raw -Encoding UTF8|ConvertFrom-Json
  if(!$r.completed){throw 'Fix3 runtime report completed=false'}
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
Write-Host 'STAGE42G FIX3 TEST COMPLETE' -ForegroundColor Green
Write-Host "Test ISO: $Output"
