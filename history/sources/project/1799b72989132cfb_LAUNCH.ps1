# BIA STEP095 FIX1 — independent supervisor for child launcher (Windows PowerShell 5.1).
# Must write fall_ ZIP if run.ps1 exits/crashes without writing any result ZIP.
[CmdletBinding()]
param()
$ErrorActionPreference='Stop'
$root='PROJECT_ROOT'
$log=Join-Path $root 'log'
$runid=('{0}_{1}' -f (Get-Date -Format 'yyyyMMdd_HHmmss_fff'),$PID)
$folder=Join-Path (Join-Path $log 'STEP_095_FIX1') $runid
$good=Join-Path $log ('bia_STEP_095_FIX1_passive_owner_probe_'+$runid+'.zip')
$bad=Join-Path $log ('fall_bia_STEP_095_FIX1_passive_owner_probe_'+$runid+'.zip')
$childExit=$null
$launchFailure=$null
function TestArchive([string]$p){
    if(!(Test-Path -LiteralPath $p -PathType Leaf)){return $false}
    try {
        Add-Type -AssemblyName System.IO.Compression.FileSystem -ErrorAction SilentlyContinue
        $archive=[System.IO.Compression.ZipFile]::OpenRead($p)
        try {
            if($archive.Entries.Count -lt 1){return $false}
            foreach($entry in $archive.Entries){
                if($entry.FullName.EndsWith('/')){continue}
                $stream=$entry.Open()
                try {$buf=New-Object byte[] 65536;while($stream.Read($buf,0,$buf.Length) -gt 0){}}
                finally {$stream.Dispose()}
            }
            return $true
        } finally {$archive.Dispose()}
    } catch {return $false}
}
try {
    New-Item -ItemType Directory -Path $folder -Force | Out-Null
    Set-Content -LiteralPath (Join-Path $folder 'SUPERVISOR_STARTED.txt') -Encoding UTF8 -Value "BIA STEP095 FIX1 supervisor started $(Get-Date -Format o)`r`nPARENT_PID=$PID`r`nRUNID=$runid"
    Write-Host "STEP095 FIX1 supervisor: $runid" -ForegroundColor Cyan
    Write-Host 'The emulator will NOT be auto-closed on errors; no breakpoints will be installed.' -ForegroundColor Yellow
    Write-Host 'Press START normally. On broken Mission2 text, press the existing key 1 once.' -ForegroundColor Yellow
    $run=Join-Path $PSScriptRoot 'run.ps1'
    if(!(Test-Path -LiteralPath $run -PathType Leaf)){throw "MISSING_RUN_SCRIPT: $run"}
    # Nested process: if run.ps1 terminates unexpectedly, this supervisor survives
    # and archives whatever evidence the child managed to write.
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $run -RunIdOverride $runid
    $childExit=$LASTEXITCODE
    if($null -eq $childExit){$childExit=255}
} catch {
    $launchFailure=$_ | Out-String
    Write-Host "STEP095 FIX1 supervisor caught: $launchFailure" -ForegroundColor Red
} finally {
    # Corrupt or incomplete child ZIPs are NOT acceptable success/failure evidence.
    foreach($existing in @($good,$bad)){
        if((Test-Path -LiteralPath $existing -PathType Leaf) -and !(TestArchive $existing)){
            $renamed=$existing+'.corrupt'
            try{Move-Item -LiteralPath $existing -Destination $renamed -Force -ErrorAction Stop}catch{}
            Write-Host "WARNING: invalid child ZIP retained for diagnosis as $renamed" -ForegroundColor Red
        }
    }
    # If the child did not create a valid archive, make an emergency fall_ ZIP.
    if((!(TestArchive $good)) -and (!(TestArchive $bad))){
        try {
            New-Item -ItemType Directory -Path $folder -Force | Out-Null
            $lines=@(
                'STEP_095_FIX1 SUPERVISOR_FALLBACK_FAILURE',
                "runid=$runid",
                "child_exit_code=$childExit",
                "time=$(Get-Date -Format o)",
                "supervisor_error=$launchFailure",
                'Main runner failed to create an archive. See this folder for partial evidence.',
                'No claim of successful Korean rendering or font writer identification.'
            )
            Set-Content -LiteralPath (Join-Path $folder 'SUPERVISOR_FALLBACK_FAILURE.txt') -Value $lines -Encoding UTF8
            foreach($rel in @('run.ps1','LAUNCH.ps1','README.md')){
                $src=Join-Path $PSScriptRoot $rel
                if(Test-Path -LiteralPath $src -PathType Leaf){Copy-Item -LiteralPath $src -Destination (Join-Path $folder (Split-Path -Leaf $rel)) -Force -ErrorAction SilentlyContinue}
            }
            foreach($rel in @('scripts\passive_owner_watch.py','scripts\ws_readonly.py')){
                $src=Join-Path $PSScriptRoot $rel
                if(Test-Path -LiteralPath $src -PathType Leaf){Copy-Item -LiteralPath $src -Destination $folder -Force -ErrorAction SilentlyContinue}
            }
            New-Item -ItemType Directory -Path $log -Force | Out-Null
            $data=@(Get-ChildItem -LiteralPath $folder -Force -ErrorAction SilentlyContinue)
            if($data.Count -eq 0){Set-Content -LiteralPath (Join-Path $folder 'EMPTY_REPORT.txt') -Value 'No child files' -Encoding ASCII}
            Compress-Archive -Path (Join-Path $folder '*') -DestinationPath $bad -CompressionLevel Optimal -Force
            Add-Type -AssemblyName System.IO.Compression.FileSystem -ErrorAction SilentlyContinue
            $zf=[System.IO.Compression.ZipFile]::OpenRead($bad)
            try {if($zf.Entries.Count -eq 0){throw 'Emergency result ZIP is empty'}}finally{$zf.Dispose()}
            Write-Host "FALLBACK ZIP CREATED: $bad" -ForegroundColor Red
        } catch {
            $err=$_ | Out-String
            Write-Host "PROJECT_ROOT\log ZIP fallback failed: $err" -ForegroundColor Red
            # Secondary fallback if D: is full/unavailable; never delete the evidence directory.
            try {
                $fallback=Join-Path (Join-Path $env:USERPROFILE 'Downloads') ('fall_bia_STEP_095_FIX1_RECOVERY_'+$runid+'.zip')
                Compress-Archive -Path (Join-Path $folder '*') -DestinationPath $fallback -Force
                Write-Host "RECOVERY ZIP CREATED IN DOWNLOADS: $fallback" -ForegroundColor Red
            } catch {Write-Host "Please retain diagnostic folder: $folder" -ForegroundColor Red}
        }
    }
    if(TestArchive $good){
        Write-Host "UPLOAD RESULT ZIP: $good" -ForegroundColor Green
    } elseif(TestArchive $bad){
        Write-Host "UPLOAD FAILURE ZIP: $bad" -ForegroundColor Yellow
    } else {
        Write-Host "DIAGNOSTIC FOLDER: $folder" -ForegroundColor Red
    }
}
if(($null -eq $childExit) -or ($childExit -ne 0) -or $launchFailure -or !(TestArchive $good)){
    exit 1
}
exit 0
