$ErrorActionPreference='Stop'
[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false)
$Root='PROJECT_ROOT'
$Source=Join-Path $Root 'BIA_STAGE41F_FIRST_MOVIE_FULL_KO_TEST.iso'
$Output=Join-Path $Root 'BIA_STAGE42B_HASHMAP_223_PROBE.iso'
$Analysis=Join-Path $Root 'analysis\stage42b_hashmap_223_probe'
$Translation=Join-Path $Root 'translation\stage42b'
$LogRoot=Join-Path $Root 'log'
$OldRoot=Join-Path $LogRoot 'old'
$Stamp=Get-Date -Format 'yyyyMMdd_HHmmss'
$Owned=$null;$Success=$false
New-Item -ItemType Directory -Force $Analysis,$Translation,$LogRoot,$OldRoot|Out-Null
Remove-Item (Join-Path $Analysis '*') -Recurse -Force -EA SilentlyContinue

function Find-PPSSPP {
 $c=@('LOCAL_PATH','PROJECT_ROOT\PPSSPPWindows64.exe')
 foreach($p in $c){if(Test-Path $p){return $p}}
 $f=Get-ChildItem 'LOCAL_PATH' -Filter PPSSPPWindows64.exe -Recurse -File -EA SilentlyContinue|Sort-Object LastWriteTime -Descending|Select-Object -First 1
 if($f){return $f.FullName};throw 'PPSSPPWindows64.exe not found'
}
function Free-Port {
 foreach($p in 26222..26350){$l=$null;try{$l=[Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback,$p);$l.Start();$l.Stop();return $p}catch{if($l){try{$l.Stop()}catch{}}}}
 throw 'No free debugger port'
}
function Archive([string]$p){
 if(Test-Path $p){$d=Join-Path $OldRoot $Stamp;New-Item -ItemType Directory -Force $d|Out-Null;Move-Item $p (Join-Path $d ([IO.Path]::GetFileName($p))) -Force}
}
function Pack([bool]$ok){
 $tmp=Join-Path $env:TEMP ("bia42b_"+[guid]::NewGuid().ToString('N'));New-Item -ItemType Directory -Force $tmp|Out-Null
 try{
  Get-ChildItem $Analysis -Recurse -File -EA SilentlyContinue|ForEach-Object{$rel=$_.FullName.Substring($Analysis.Length).TrimStart('\');$dst=Join-Path $tmp $rel;New-Item -ItemType Directory -Force (Split-Path $dst)|Out-Null;Copy-Item $_.FullName $dst -Force}
  Copy-Item (Join-Path $PSScriptRoot 'movie_subtitles_ko.tsv'),(Join-Path $PSScriptRoot 'stage42b_translation_report.json'),(Join-Path $PSScriptRoot 'stage42b_charset.txt'),$PSCommandPath -Destination $tmp -Force
  if($ok){$z=Join-Path $LogRoot 'bia_stage42b_upload.zip'}else{$z=Join-Path $LogRoot 'fail_bia_stage42b_upload.zip'}
  Archive $z;Compress-Archive (Join-Path $tmp '*') $z -Force;Write-Host "`nUpload ZIP: $z"
 }finally{Remove-Item $tmp -Recurse -Force -EA SilentlyContinue}
}
try{
 if(!(Test-Path $Source)){throw "Missing Stage41F ISO: $Source"}
 Copy-Item (Join-Path $PSScriptRoot 'movie_subtitles_ko.tsv') (Join-Path $Translation 'movie_subtitles_ko.tsv') -Force
 Copy-Item (Join-Path $PSScriptRoot 'stage42b_translation_report.json') (Join-Path $Translation 'stage42b_translation_report.json') -Force
 if(Test-Path $Output){Remove-Item $Output -Force}

 $launcher=Get-Command py.exe -EA SilentlyContinue
 if($launcher){$Python=$launcher.Source;$PyPrefix=@('-3')}else{$launcher=Get-Command python.exe -EA Stop;$Python=$launcher.Source;$PyPrefix=@()}

 Write-Host '=== BIA STAGE42B ==='
 Write-Host '영상 자막 133개 전체 번역 TSV를 설치합니다.'
 Write-Host 'Subtitle HASHMAP를 223개 엔트리(콘텐츠용 222키)로 확장해 안정성을 시험합니다.'
 Write-Host ''
 & $Python @PyPrefix (Join-Path $PSScriptRoot 'build_stage42b_probe.py') --source $Source --output $Output --ini (Join-Path $PSScriptRoot 'SUBTITLEHASHMAP_223_PROBE.INI') --report (Join-Path $Analysis 'stage42b_build_report.json')
 if($LASTEXITCODE -ne 0){throw "Probe build failed: $LASTEXITCODE"}

 $P=Find-PPSSPP;$Port=Free-Port
 $Owned=Start-Process -FilePath $P -ArgumentList "--debugger=$Port `"$Output`"" -PassThru
 Start-Sleep -Milliseconds 1000
 & $Python @PyPrefix (Join-Path $PSScriptRoot 'stage42b_probe_test.py') --port $Port --out $Analysis --iso $Output
 if($LASTEXITCODE -ne 0){throw "Probe runtime test failed: $LASTEXITCODE"}

 $r=Get-Content (Join-Path $Analysis 'stage42b_probe_report.json') -Raw -Encoding UTF8|ConvertFrom-Json
 if(!$r.completed){throw 'probe report completed=false'}
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
Write-Host 'STAGE42B COMPLETE' -ForegroundColor Green
Write-Host "Translation TSV: $Translation\movie_subtitles_ko.tsv"
Write-Host "Probe ISO: $Output"
