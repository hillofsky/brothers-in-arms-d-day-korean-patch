$ErrorActionPreference='Stop'
[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false)

$Root='PROJECT_ROOT'
$Iso=Join-Path $Root 'BIA_STAGE41A_FIRST_MOVIE_KO_SUB_TEST.iso'
$Analysis=Join-Path $Root 'analysis\stage41d_subtitle_resources'
$LogRoot=Join-Path $Root 'log'
$OldRoot=Join-Path $LogRoot 'old'
$Stamp=Get-Date -Format 'yyyyMMdd_HHmmss'
$Py=Join-Path $PSScriptRoot 'stage41d_extract_subtitle_resources.py'
$Success=$false

New-Item -ItemType Directory -Force $Analysis,$LogRoot,$OldRoot|Out-Null
Remove-Item (Join-Path $Analysis '*') -Recurse -Force -EA SilentlyContinue

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
  Get-ChildItem $Analysis -Recurse -File -EA SilentlyContinue | ForEach-Object {
    $rel=$_.FullName.Substring($Analysis.Length).TrimStart('\')
    $dst=Join-Path $tmp $rel
    New-Item -ItemType Directory -Force (Split-Path $dst) | Out-Null
    Copy-Item $_.FullName $dst -Force
  }
  Copy-Item $Py,$PSCommandPath -Destination $tmp -Force
  if($ok){$z=Join-Path $LogRoot 'bia_stage41d_upload.zip'}
  else{$z=Join-Path $LogRoot 'fail_bia_stage41d_upload.zip'}
  Archive $z
  Compress-Archive (Join-Path $tmp '*') $z -Force
  Remove-Item $tmp -Recurse -Force -EA SilentlyContinue
  Write-Host "`nUpload ZIP: $z"
}

try{
  if(!(Test-Path $Iso)){throw "Missing ISO: $Iso"}
  Write-Host '=== BIA STAGE41D: SUBTITLE RESOURCE EXTRACTION ==='
  Write-Host 'PPSSPP는 실행하지 않습니다.'
  Write-Host 'Stage41A ISO에서 SUBTITLEHASHMAP.INI / SUBTITLETEXTURE.RAW를 직접 추출합니다.'
  Write-Host ''

  $launcher=Get-Command py.exe -EA SilentlyContinue
  if($launcher){
    & $launcher.Source -3 $Py --iso $Iso --out $Analysis
  }else{
    $launcher=Get-Command python.exe -EA Stop
    & $launcher.Source $Py --iso $Iso --out $Analysis
  }
  if($LASTEXITCODE -ne 0){throw "Analyzer exit code $LASTEXITCODE"}

  $r=Get-Content (Join-Path $Analysis 'stage41d_report.json') -Raw -Encoding UTF8 | ConvertFrom-Json
  if(!$r.completed){throw 'stage41d report completed=false'}
  $Success=$true
}catch{
  $_|Out-String|Set-Content (Join-Path $Analysis 'FAILURE.txt') -Encoding UTF8
  Write-Host "FAILED: $($_.Exception.Message)" -ForegroundColor Red
}finally{
  Pack $Success
}
if(!$Success){exit 1}
Write-Host 'STAGE41D SUCCESS' -ForegroundColor Green
