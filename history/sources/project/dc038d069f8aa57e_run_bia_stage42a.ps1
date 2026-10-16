$ErrorActionPreference='Stop'
[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false)

$Root='PROJECT_ROOT'
$Source=Join-Path $Root 'BIA_STAGE40Y_FIRST_MISSION_UI_TEST.iso'
$Analysis=Join-Path $Root 'analysis\stage42a_movie_st1_sweep'
$LogRoot=Join-Path $Root 'log'
$OldRoot=Join-Path $LogRoot 'old'
$Stamp=Get-Date -Format 'yyyyMMdd_HHmmss'
$Py=Join-Path $PSScriptRoot 'stage42a_st1_sweep.py'
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
  $tmp=Join-Path $env:TEMP ("bia42a_"+[guid]::NewGuid().ToString('N'))
  New-Item -ItemType Directory -Force $tmp|Out-Null
  try{
    Get-ChildItem $Analysis -Recurse -File -EA SilentlyContinue|ForEach-Object{
      $rel=$_.FullName.Substring($Analysis.Length).TrimStart('\')
      $dst=Join-Path $tmp $rel
      New-Item -ItemType Directory -Force (Split-Path $dst)|Out-Null
      Copy-Item $_.FullName $dst -Force
    }
    Copy-Item $Py,$PSCommandPath -Destination $tmp -Force
    if($ok){$z=Join-Path $LogRoot 'bia_stage42a_upload.zip'}
    else{$z=Join-Path $LogRoot 'fail_bia_stage42a_upload.zip'}
    Archive $z
    Compress-Archive (Join-Path $tmp '*') $z -Force
    Write-Host "`nUpload ZIP: $z"
  }finally{
    Remove-Item $tmp -Recurse -Force -EA SilentlyContinue
  }
}

try{
  if(!(Test-Path $Source)){throw "Missing original subtitle source ISO: $Source"}

  Write-Host '=== BIA STAGE42A: ALL MOVIE ST1 SWEEP ==='
  Write-Host 'Stage41F 및 한글 자막 ISO는 수정하지 않습니다.'
  Write-Host 'Stage40Y 기준선에서 모든 .ST1 원문을 추출합니다.'
  Write-Host ''

  $launcher=Get-Command py.exe -EA SilentlyContinue
  if($launcher){
    & $launcher.Source -3 $Py --iso $Source --out $Analysis
  }else{
    $launcher=Get-Command python.exe -EA Stop
    & $launcher.Source $Py --iso $Source --out $Analysis
  }
  if($LASTEXITCODE -ne 0){throw "Stage42A analyzer exit code $LASTEXITCODE"}

  $r=Get-Content (Join-Path $Analysis 'stage42a_report.json') -Raw -Encoding UTF8|ConvertFrom-Json
  if(!$r.completed){throw 'stage42a report completed=false'}
  $Success=$true
}catch{
  $_|Out-String|Set-Content (Join-Path $Analysis 'FAILURE.txt') -Encoding UTF8
  Write-Host "FAILED: $($_.Exception.Message)" -ForegroundColor Red
}finally{
  Pack $Success
}

if(!$Success){exit 1}
Write-Host 'STAGE42A SUCCESS' -ForegroundColor Green
