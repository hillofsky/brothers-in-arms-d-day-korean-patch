param([Parameter(Mandatory=$true)][string]$OutputDir)
$ErrorActionPreference="Stop"
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
$candidates=New-Object System.Collections.Generic.List[object]
function Add-Candidate([string]$Path,[string]$Source){
 if([string]::IsNullOrWhiteSpace($Path)){return}
 try{
  $rp=(Resolve-Path -LiteralPath $Path -ErrorAction Stop).Path
  if(!(Test-Path -LiteralPath $rp -PathType Leaf)){return}
  $name=[IO.Path]::GetFileName($rp)
  if($name -notmatch '^PPSSPP.*\\.exe$'){return}
  if($candidates | Where-Object {$_.Path -ieq $rp}){return}
  $i=Get-Item -LiteralPath $rp
  $score=if($name -ieq 'PPSSPPWindows64.exe'){3}elseif($name -match '64'){2}else{1}
  $candidates.Add([pscustomobject]@{Path=$rp;Source=$Source;FileName=$name;FileVersion=$i.VersionInfo.FileVersion;ArchScore=$score;LastWriteTime=$i.LastWriteTime.ToString('o')})|Out-Null
 }catch{}
}
if($env:PPSSPP_EXE){Add-Candidate $env:PPSSPP_EXE 'ENV:PPSSPP_EXE'}
Get-Process -ErrorAction SilentlyContinue | Where-Object {$_.ProcessName -match '^PPSSPP'} | ForEach-Object {try{Add-Candidate $_.MainModule.FileName ("RUNNING_PID_"+$_.Id)}catch{}}
$known=@(
'PROJECT_ROOT\\PPSSPPWindows64.exe','PROJECT_ROOT\\PPSSPPWindows.exe',
'PROJECT_ROOT\\PPSSPP\\PPSSPPWindows64.exe','PROJECT_ROOT\\PPSSPP\\PPSSPPWindows.exe',
'PROJECT_ROOT\\PPSSPPWindows64.exe','PROJECT_ROOT\\PPSSPPWindows.exe','PROJECT_ROOT\\ppsspp\\PPSSPPWindows64.exe','PROJECT_ROOT\\ppsspp\\PPSSPPWindows.exe',
'LOCAL_PATH','LOCAL_PATH',
"$env:USERPROFILE\\Downloads\\PPSSPPWindows64.exe","$env:USERPROFILE\\Downloads\\PPSSPPWindows.exe")
foreach($p in $known){Add-Candidate $p 'KNOWN_PATH'}
foreach($script in @('PROJECT_ROOT\\generated_macros\\naruto.bat','PROJECT_ROOT\\naruto.bat')){
 if(Test-Path -LiteralPath $script){
  try{$txt=Get-Content -LiteralPath $script -Raw;[regex]::Matches($txt,'(?i)([A-Z]:\\[^"`''\\r\\n]*?PPSSPP(?:Windows64|Windows)?\\.exe)')|ForEach-Object{Add-Candidate $_.Groups[1].Value ("SCRIPT:"+$script)}}catch{}
 }
}
foreach($n in @('PPSSPPWindows64.exe','PPSSPPWindows.exe')){try{$c=Get-Command $n -ErrorAction SilentlyContinue;if($c){Add-Candidate $c.Source 'PATH'}}catch{}}
$candidates|Sort-Object Path|Export-Csv -LiteralPath (Join-Path $OutputDir 'ppsspp_candidates.csv') -NoTypeInformation -Encoding UTF8
if($candidates.Count -eq 0){throw 'PPSSPP executable not found by FAST search. Set $env:PPSSPP_EXE to the exact executable path and rerun.'}
$sel=$candidates|Sort-Object @{Expression={$_.ArchScore};Descending=$true},@{Expression={[datetime]$_.LastWriteTime};Descending=$true}|Select-Object -First 1
$sel|ConvertTo-Json -Depth 3|Set-Content -LiteralPath (Join-Path $OutputDir 'ppsspp_selected.json') -Encoding UTF8
$sel.Path
