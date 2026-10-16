param(
    [switch]$Aggressive
)

$ErrorActionPreference="Stop"

$Root="PROJECT_ROOT"
$Original=Join-Path $Root "Brothers in Arms - D-Day (USA) (v1.01).iso"
$Stage39F=Join-Path $Root "BIA_STAGE39F_CORRECT_NARROW_METADATA_TEST.iso"
$Stage39U=Join-Path $Root "BIA_STAGE39U_BOOT_RENDER_UTF8_TEST.iso"
$Stage39T=Join-Path $Root "BIA_STAGE39T_BOOT_RENDER_UTF8_TEST.iso"

$LogDir=Join-Path $Root "log"
if(-not (Test-Path $LogDir)){
    New-Item -ItemType Directory -Path $LogDir | Out-Null
}
$Log=Join-Path $LogDir "bia_cleanup_recover_stage39u.txt"

function Log([string]$s){
    $s | Tee-Object -FilePath $Log -Append
}

if(Test-Path $Log){Remove-Item $Log -Force}

Log "=== BIA cleanup/recovery ==="
$drive=Get-PSDrive -Name D
Log ("Free before: {0:N2} GiB" -f ($drive.Free/1GB))

# ----------------------------------------------------------------------
# 1) Recover Stage39U by zero-copy rename if the equivalent Stage39T ISO exists.
#    Stage39U changed only the test harness timing; the ISO patch itself is
#    equivalent to Stage39T.
# ----------------------------------------------------------------------
if(-not (Test-Path $Stage39U)){
    if(Test-Path $Stage39T){
        Log "Stage39U missing; Stage39T exists. Renaming Stage39T -> Stage39U (no extra space)."
        Move-Item $Stage39T $Stage39U -Force
    }
}

# ----------------------------------------------------------------------
# 2) Remove generated stage ISOs that are no longer promoted baselines.
#    Preserve:
#      - original game ISO
#      - Stage39F
#      - Stage39U
# ----------------------------------------------------------------------
$Protected=@(
    [IO.Path]::GetFullPath($Original).ToLowerInvariant(),
    [IO.Path]::GetFullPath($Stage39F).ToLowerInvariant(),
    [IO.Path]::GetFullPath($Stage39U).ToLowerInvariant()
)

$StageIsos=Get-ChildItem $Root -File -Filter "BIA_STAGE*.iso" -ErrorAction SilentlyContinue

foreach($f in $StageIsos){
    $full=$f.FullName.ToLowerInvariant()
    if($Protected -contains $full){ continue }

    # All non-protected BIA_STAGE*.iso files are reproducible test outputs.
    try {
        $sz=$f.Length
        Remove-Item $f.FullName -Force
        Log ("Removed generated ISO: {0} ({1:N2} GiB)" -f $f.Name, ($sz/1GB))
    } catch {
        Log ("WARN could not remove {0}: {1}" -f $f.FullName, $_.Exception.Message)
    }
}

# Partial/temp ISO artifacts.
$TempPatterns=@(
    "*.iso.tmp",
    "*.iso.partial",
    "*.partial.iso",
    "*.tmp.iso"
)
foreach($pat in $TempPatterns){
    Get-ChildItem $Root -File -Filter $pat -ErrorAction SilentlyContinue | ForEach-Object {
        try {
            $sz=$_.Length
            Remove-Item $_.FullName -Force
            Log ("Removed temp ISO: {0} ({1:N2} GiB)" -f $_.Name, ($sz/1GB))
        } catch {
            Log ("WARN could not remove temp {0}: {1}" -f $_.FullName, $_.Exception.Message)
        }
    }
}

# Safe obsolete analysis folders from failed/replaced diagnostic stages.
$SafeAnalysis=@(
    "stage39s_renderer_utf8_fix",
    "stage39t_boot_renderer_utf8",
    "stage40b_a_mass_insert",
    "stage40c_menu_mass"
)
foreach($name in $SafeAnalysis){
    $p=Join-Path (Join-Path $Root "analysis") $name
    if(Test-Path $p){
        try {
            Remove-Item $p -Recurse -Force
            Log ("Removed obsolete analysis dir: {0}" -f $p)
        } catch {
            Log ("WARN could not remove analysis dir {0}: {1}" -f $p, $_.Exception.Message)
        }
    }
}

# Aggressive mode: delete older fail ZIPs only. Successful upload ZIPs are kept.
if($Aggressive){
    if(Test-Path $LogDir){
        Get-ChildItem $LogDir -File -Filter "fail_bia_stage*.zip" -ErrorAction SilentlyContinue |
            Sort-Object LastWriteTime -Descending |
            Select-Object -Skip 3 |
            ForEach-Object {
                try {
                    $sz=$_.Length
                    Remove-Item $_.FullName -Force
                    Log ("Aggressive: removed old fail ZIP {0} ({1:N2} MiB)" -f $_.Name, ($sz/1MB))
                } catch {
                    Log ("WARN could not remove fail ZIP {0}: {1}" -f $_.FullName, $_.Exception.Message)
                }
            }
    }
}

$drive=Get-PSDrive -Name D
Log ("Free after cleanup: {0:N2} GiB" -f ($drive.Free/1GB))

# ----------------------------------------------------------------------
# 3) If Stage39U is still missing, regenerate it from Stage39F with the proven
#    bundled Stage39U tool.
# ----------------------------------------------------------------------
if(-not (Test-Path $Stage39U)){
    if(-not (Test-Path $Stage39F)){
        Log "ERROR: Stage39U is missing and Stage39F baseline is also missing."
        Log "Cannot safely regenerate Stage39U automatically."
        throw "Missing both Stage39U and Stage39F baseline."
    }

    $sourceBytes=(Get-Item $Stage39F).Length
    $drive=Get-PSDrive -Name D
    $required=$sourceBytes + 536870912

    Log ("Stage39U still missing. Need about {0:N2} GiB free to regenerate it." -f ($required/1GB))
    Log ("Current free: {0:N2} GiB" -f ($drive.Free/1GB))

    if($drive.Free -lt $required){
        Log "ERROR: Not enough free space to regenerate Stage39U."
        Log "Largest files under PROJECT_ROOT:"
        Get-ChildItem $Root -File -Recurse -ErrorAction SilentlyContinue |
            Sort-Object Length -Descending |
            Select-Object -First 20 |
            ForEach-Object {
                Log ("  {0,8:N2} GiB  {1}" -f ($_.Length/1GB), $_.FullName)
            }

        throw "Cleanup completed, but more free space is required before Stage39U can be regenerated."
    }

    $ScriptDir=Split-Path -Parent $MyInvocation.MyCommand.Path
    $Recovery=Join-Path $ScriptDir "stage39u_recovery\run_bia_stage39u.ps1"

    if(-not (Test-Path $Recovery)){
        throw "Bundled Stage39U recovery tool missing: $Recovery"
    }

    Log "Regenerating Stage39U from Stage39F..."
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File $Recovery

    if($LASTEXITCODE -ne 0){
        throw "Stage39U regeneration failed with exit code $LASTEXITCODE"
    }
}

if(-not (Test-Path $Stage39U)){
    throw "Stage39U source is still missing after recovery."
}

$drive=Get-PSDrive -Name D
Log ("Stage39U ready: {0}" -f $Stage39U)
Log ("Stage39U size: {0:N2} GiB" -f ((Get-Item $Stage39U).Length/1GB))
Log ("Final free space: {0:N2} GiB" -f ($drive.Free/1GB))

Log ""
Log "Largest remaining files under PROJECT_ROOT:"
Get-ChildItem $Root -File -Recurse -ErrorAction SilentlyContinue |
    Sort-Object Length -Descending |
    Select-Object -First 15 |
    ForEach-Object {
        Log ("  {0,8:N2} GiB  {1}" -f ($_.Length/1GB), $_.FullName)
    }

Write-Host ""
Write-Host "Cleanup/recovery complete."
Write-Host ("Stage39U: {0}" -f $Stage39U)
Write-Host ("Free space: {0:N2} GiB" -f ((Get-PSDrive D).Free/1GB))
Write-Host ("Log: {0}" -f $Log)
