$ErrorActionPreference='Stop'
[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false)
$Root='PROJECT_ROOT';$Source=Join-Path $Root 'BIA_STAGE41A_FIRST_MOVIE_KO_SUB_TEST.iso';$Output=Join-Path $Root 'BIA_STAGE41F_FIRST_MOVIE_FULL_KO_TEST.iso';$Analysis=Join-Path $Root 'analysis\stage41f_first_movie_full';$LogRoot=Join-Path $Root 'log';$OldRoot=Join-Path $LogRoot 'old';$Stamp=Get-Date -Format 'yyyyMMdd_HHmmss';$Owned=$null;$Success=$false
New-Item -ItemType Directory -Force $Analysis,$LogRoot,$OldRoot|Out-Null
Remove-Item (Join-Path $Analysis '*') -Recurse -Force -EA SilentlyContinue
function Find-PPSSPP {$c=@('LOCAL_PATH','PROJECT_ROOT\PPSSPPWindows64.exe');foreach($p in $c){if(Test-Path $p){return $p}};$f=Get-ChildItem 'LOCAL_PATH' -Filter PPSSPPWindows64.exe -Recurse -File -EA SilentlyContinue|Sort-Object LastWriteTime -Descending|Select-Object -First 1;if($f){return $f.FullName};throw 'PPSSPPWindows64.exe not found'}
function Free-Port {foreach($p in 26222..26350){$l=$null;try{$l=[Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback,$p);$l.Start();$l.Stop();return $p}catch{if($l){try{$l.Stop()}catch{}}}};throw 'No free debugger port'}
function Archive([string]$p){if(Test-Path $p){$d=Join-Path $OldRoot $Stamp;New-Item -ItemType Directory -Force $d|Out-Null;Move-Item $p (Join-Path $d ([IO.Path]::GetFileName($p))) -Force}}
function Pack([bool]$ok){$tmp=Join-Path $env:TEMP ("bia41f_"+[guid]::NewGuid().ToString('N'));New-Item -ItemType Directory -Force $tmp|Out-Null;try{Get-ChildItem $Analysis -Recurse -File -EA SilentlyContinue|ForEach-Object{$rel=$_.FullName.Substring($Analysis.Length).TrimStart('\');$dst=Join-Path $tmp $rel;New-Item -ItemType Directory -Force (Split-Path $dst)|Out-Null;Copy-Item $_.FullName $dst -Force};Copy-Item (Join-Path $PSScriptRoot 'stage41f_manifest.json'),(Join-Path $PSScriptRoot 'stage41f_atlas_preview.png'),$PSCommandPath -Destination $tmp -Force;if($ok){$z=Join-Path $LogRoot 'bia_stage41f_upload.zip'}else{$z=Join-Path $LogRoot 'fail_bia_stage41f_upload.zip'};Archive $z;Compress-Archive (Join-Path $tmp '*') $z -Force;Write-Host "`nUpload ZIP: $z"}finally{Remove-Item $tmp -Recurse -Force -EA SilentlyContinue}}
try{
 if(!(Test-Path $Source)){throw "Missing source ISO: $Source"};if(Test-Path $Output){Remove-Item $Output -Force}
 $launcher=Get-Command py.exe -EA SilentlyContinue;if($launcher){$Python=$launcher.Source;$PyPrefix=@('-3')}else{$launcher=Get-Command python.exe -EA Stop;$Python=$launcher.Source;$PyPrefix=@()}
 Write-Host '=== BIA STAGE41F: FIRST MOVIE FULL KOREAN ===';Write-Host '첫 영상 19개 ST1 필드를 전부 1바이트 자막 매핑으로 변환합니다.';Write-Host '제목은 슬롯 한계 때문에 "운명의 날 / 1944.6.6"으로 정리합니다.';Write-Host ''
 & $Python @PyPrefix (Join-Path $PSScriptRoot 'build_stage41f.py') --source $Source --output $Output --assets $PSScriptRoot --report (Join-Path $Analysis 'stage41f_build_report.json');if($LASTEXITCODE -ne 0){throw "Stage41F build failed: $LASTEXITCODE"}
 $P=Find-PPSSPP;$Port=Free-Port;$Owned=Start-Process -FilePath $P -ArgumentList "--debugger=$Port `"$Output`"" -PassThru;Start-Sleep -Milliseconds 1000
 & $Python @PyPrefix (Join-Path $PSScriptRoot 'stage41f_auto_test.py') --port $Port --out $Analysis --iso $Output;if($LASTEXITCODE -ne 0){throw "Stage41F test failed: $LASTEXITCODE"}
 $r=Get-Content (Join-Path $Analysis 'stage41f_test_report.json') -Raw -Encoding UTF8|ConvertFrom-Json;if(!$r.completed){throw 'Stage41F report completed=false'};$Success=$true
}catch{$_|Out-String|Set-Content (Join-Path $Analysis 'FAILURE.txt') -Encoding UTF8;Write-Host "FAILED: $($_.Exception.Message)" -ForegroundColor Red}
finally{if($Owned){try{if(!$Owned.HasExited){Stop-Process -Id $Owned.Id -Force -EA SilentlyContinue}}catch{}};Pack $Success}
if(!$Success){exit 1}
Write-Host '';Write-Host 'STAGE41F COMPLETE' -ForegroundColor Green;Write-Host "Test ISO: $Output"
