$ErrorActionPreference="Stop"

$Root="PROJECT_ROOT"
$Source=Join-Path $Root "BIA_STAGE39U_BOOT_RENDER_UTF8_TEST.iso"
$Output=Join-Path $Root "BIA_STAGE40C_MENU_MASS_TEST.iso"

if(-not (Test-Path $Source)){
    throw "Required source ISO not found: $Source"
}

# These are reproducible diagnostic/test ISOs that are no longer the promoted
# baseline.  Keep the original game ISO, Stage39F, and Stage39U.
$SafeToDelete=@(
    (Join-Path $Root "BIA_STAGE39S_RENDER_UTF8_TEST.iso"),
    (Join-Path $Root "BIA_STAGE39T_BOOT_RENDER_UTF8_TEST.iso"),
    (Join-Path $Root "BIA_STAGE40B_A_MASS_TEST.iso"),
    (Join-Path $Root "BIA_STAGE40C_MENU_MASS_TEST.iso")
)

Write-Host "[Stage40C-Retry] Checking D: free space..."
$sourceBytes=(Get-Item $Source).Length
$needBytes=$sourceBytes + 536870912   # source-size copy + 512 MiB safety margin
$drive=Get-PSDrive -Name D

Write-Host ("[Stage40C-Retry] Source ISO: {0:N2} GiB" -f ($sourceBytes/1GB))
Write-Host ("[Stage40C-Retry] Free before cleanup: {0:N2} GiB" -f ($drive.Free/1GB))

if($drive.Free -lt $needBytes){
    Write-Host "[Stage40C-Retry] Free space is insufficient. Removing only obsolete generated test ISOs..."

    foreach($p in $SafeToDelete){
        if(Test-Path $p){
            try {
                $sz=(Get-Item $p).Length
                Remove-Item $p -Force
                Write-Host ("  removed {0} ({1:N2} GiB)" -f $p, ($sz/1GB))
            } catch {
                Write-Warning ("Could not remove {0}: {1}" -f $p, $_.Exception.Message)
            }
        }
    }

    $drive=Get-PSDrive -Name D
    Write-Host ("[Stage40C-Retry] Free after cleanup: {0:N2} GiB" -f ($drive.Free/1GB))
}

if($drive.Free -lt $needBytes){
    $needGiB=$needBytes/1GB
    $freeGiB=$drive.Free/1GB
    throw ("Still not enough free space on D:. Need about {0:N2} GiB free, currently {1:N2} GiB. Keep BIA_STAGE39U_BOOT_RENDER_UTF8_TEST.iso and free more space, then rerun." -f $needGiB,$freeGiB)
}

$ScriptDir=Split-Path -Parent $MyInvocation.MyCommand.Path
$Py=Join-Path $ScriptDir "bia_stage40c_menu_mass.py"

$Python=Get-Command python -ErrorAction SilentlyContinue
if(-not $Python){$Python=Get-Command py -ErrorAction SilentlyContinue}
if(-not $Python){throw "Python was not found in PATH."}

Write-Host "[Stage40C-Retry] Disk space OK. Starting Stage40C..."
& $Python.Source $Py

if($LASTEXITCODE -ne 0){
    throw "Stage 40C retry failed with exit code $LASTEXITCODE"
}
