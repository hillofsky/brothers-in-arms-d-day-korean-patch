$ErrorActionPreference='Stop'
[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false)
$Root='PROJECT_ROOT'
$Source=Join-Path $Root 'BIA_STAGE42C_HIGHBYTE_KEY_PROBE.iso'
$Output=Join-Path $Root 'BIA_STAGE42F_MULTIGLYPH_TOKEN_PROBE.iso'
$Analysis=Join-Path $Root 'analysis\stage42f_multiglyph_token'
$LogRoot=Join-Path $Root 'log';$OldRoot=Join-Path $LogRoot 'old';$Stamp=Get-Date -Format 'yyyyMMdd_HHmmss'
$Owned=$null;$Success=$false
New-Item -ItemType Directory -Force $Analysis,$LogRoot,$OldRoot|Out-Null
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
function Archive([string]$p){if(Test-Path $p){$d=Join-Path $OldRoot $Stamp;New-Item -ItemType Directory -Force $d|Out-Null;Move-Item $p (Join-Path $d ([IO.Path]::GetFileName($p))) -Force}}
function Pack([bool]$ok){
 $tmp=Join-Path $env:TEMP ("bia42f_"+[guid]::NewGuid().ToString('N'));New-Item -ItemType Directory -Force $tmp|Out-Null
 try{
  Get-ChildItem $Analysis -Recurse -File -EA SilentlyContinue|ForEach-Object{$rel=$_.FullName.Substring($Analysis.Length).TrimStart('\');$dst=Join-Path $tmp $rel;New-Item -ItemType Directory -Force (Split-Path $dst)|Out-Null;Copy-Item $_.FullName $dst -Force}
  Copy-Item (Join-Path $PSScriptRoot 'stage42f_manifest.json'),(Join-Path $PSScriptRoot 'stage42f_atlas_preview.png'),$PSCommandPath -Destination $tmp -Force
  if($ok){$z=Join-Path $LogRoot 'bia_stage42f_upload.zip'}else{$z=Join-Path $LogRoot 'fail_bia_stage42f_upload.zip'}
  Archive $z;Compress-Archive (Join-Path $tmp '*') $z -Force;Write-Host "`nUpload ZIP: $z"
 }finally{Remove-Item $tmp -Recurse -Force -EA SilentlyContinue}
}
try{
 if(!(Test-Path $Source)){throw "Missing Stage42C ISO: $Source"}
 if(Test-Path $Output){Remove-Item $Output -Force}
 $launcher=Get-Command py.exe -EA SilentlyContinue
 if($launcher){$Python=$launcher.Source;$PyPrefix=@('-3')}else{$launcher=Get-Command python.exe -EA Stop;$Python=$launcher.Source;$PyPrefix=@()}
 Write-Host '=== BIA STAGE42F: MULTI-GLYPH TOKEN PROBE ==='
 Write-Host '0xFD 한 바이트에 "베이커" 세 글자를 한 번에 그리는 시험입니다.'
 Write-Host '14초 화면에 기존과 똑같이 "베이커:"가 보여야 성공입니다.'
 Write-Host ''
 & $Python @PyPrefix (Join-Path $PSScriptRoot 'build_stage42f.py') --source $Source --output $Output --assets $PSScriptRoot --report (Join-Path $Analysis 'stage42f_build_report.json')
 if($LASTEXITCODE -ne 0){throw "Stage42F build failed: $LASTEXITCODE"}
 $P=Find-PPSSPP;$Port=Free-Port
 $Owned=Start-Process -FilePath $P -ArgumentList "--debugger=$Port `"$Output`"" -PassThru
 Start-Sleep -Milliseconds 1000
 & $Python @PyPrefix (Join-Path $PSScriptRoot 'stage42f_auto_test.py') --port $Port --out $Analysis --iso $Output
 if($LASTEXITCODE -ne 0){throw "Stage42F runtime test failed: $LASTEXITCODE"}
 $r=Get-Content (Join-Path $Analysis 'stage42f_report.json') -Raw -Encoding UTF8|ConvertFrom-Json
 if(!$r.completed){throw 'Stage42F report completed=false'}
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
Write-Host 'STAGE42F COMPLETE' -ForegroundColor Green
Write-Host "Probe ISO: $Output"
