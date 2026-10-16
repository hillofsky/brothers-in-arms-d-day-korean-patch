$ErrorActionPreference='Stop'
[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false)

$Analysis='PROJECT_ROOT\analysis\stage41d_subtitle_resources'
$LogRoot='PROJECT_ROOT\log'
$OldRoot=Join-Path $LogRoot 'old'
$Stamp=Get-Date -Format 'yyyyMMdd_HHmmss'
$OutZip=Join-Path $LogRoot 'bia_stage41d_upload.zip'

if(!(Test-Path $Analysis)){
    throw "Missing analysis folder: $Analysis"
}

# Remove runaway recursive packaging folders created by the bad Stage41D Pack().
$badPkg = Join-Path $Analysis '_pkg'
if(Test-Path $badPkg){
    Write-Host "Removing runaway package tree: $badPkg" -ForegroundColor Yellow
    Remove-Item -LiteralPath $badPkg -Recurse -Force -ErrorAction SilentlyContinue
}

New-Item -ItemType Directory -Force $LogRoot,$OldRoot | Out-Null

# Verify that the actual analysis finished before repacking.
$Report = Join-Path $Analysis 'stage41d_report.json'
$Summary = Join-Path $Analysis 'stage41d_summary.txt'

if(!(Test-Path $Report)){
    throw "stage41d_report.json is missing. The analysis may not have completed."
}
$r = Get-Content $Report -Raw -Encoding UTF8 | ConvertFrom-Json
if(-not $r.completed){
    throw "stage41d_report.json says completed=false."
}

if(Test-Path $OutZip){
    $oldDir=Join-Path $OldRoot $Stamp
    New-Item -ItemType Directory -Force $oldDir | Out-Null
    Move-Item $OutZip (Join-Path $oldDir 'bia_stage41d_upload.zip') -Force
}

# IMPORTANT: temp packaging directory is OUTSIDE $Analysis, so recursion cannot occur.
$tmp = Join-Path $env:TEMP ("bia_stage41d_pack_" + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force $tmp | Out-Null

try{
    Get-ChildItem -LiteralPath $Analysis -Recurse -File -ErrorAction Stop |
        Where-Object { $_.FullName -notlike "$badPkg*" } |
        ForEach-Object {
            $rel=$_.FullName.Substring($Analysis.Length).TrimStart('\')
            $dst=Join-Path $tmp $rel
            $parent=Split-Path $dst
            if($parent){New-Item -ItemType Directory -Force $parent | Out-Null}
            Copy-Item -LiteralPath $_.FullName -Destination $dst -Force
        }

    Compress-Archive -Path (Join-Path $tmp '*') -DestinationPath $OutZip -Force
}
finally{
    Remove-Item -LiteralPath $tmp -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host ""
Write-Host "Stage41D analysis was already complete." -ForegroundColor Green
Write-Host "Fixed upload ZIP: $OutZip" -ForegroundColor Green
Write-Host ""

if(Test-Path $Summary){
    Get-Content $Summary
}
