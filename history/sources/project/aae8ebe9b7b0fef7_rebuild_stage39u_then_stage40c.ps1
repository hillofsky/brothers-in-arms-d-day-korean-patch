$ErrorActionPreference="Stop"

$Root="PROJECT_ROOT"
$LogDir=Join-Path $Root "log"
if(-not (Test-Path $LogDir)){New-Item -ItemType Directory -Path $LogDir -Force | Out-Null}
$Log=Join-Path $LogDir "bia_rebuild39u_then_stage40c.txt"
if(Test-Path $Log){Remove-Item $Log -Force}

function Log([string]$s){
    Write-Host $s
    $s | Add-Content $Log -Encoding UTF8
}

function Run-Stage([string]$Name,[string]$Script){
    if(-not (Test-Path $Script)){
        throw "$Name tool missing: $Script"
    }

    Log ""
    Log "===== $Name ====="
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File $Script
    if($LASTEXITCODE -ne 0){
        throw "$Name failed with exit code $LASTEXITCODE"
    }
    Log "$Name completed."
}

Log "=== BIA Stage39U baseline rebuild + Stage40C ==="

# --------------------------------------------------------------------------
# Confirm original ISO. Stage39B's own helper uses the same selection rule:
# any non-STAGE/non-TEST ISO under PROJECT_ROOT, preferring Brothers/D-Day names.
# --------------------------------------------------------------------------
$originalCandidates=Get-ChildItem $Root -File -Filter "*.iso" -ErrorAction SilentlyContinue |
    Where-Object {
        $_.Name -notmatch '(?i)STAGE|TEST'
    } |
    Sort-Object Length -Descending

if(-not $originalCandidates){
    Log "ERROR: No original/non-stage ISO exists under PROJECT_ROOT."
    Log "Current root ISO files:"
    Get-ChildItem $Root -File -Filter "*.iso" -ErrorAction SilentlyContinue |
        ForEach-Object { Log ("  {0:N2} GiB  {1}" -f ($_.Length/1GB), $_.FullName) }
    throw "Original Brothers in Arms ISO is missing."
}

$preferred=$originalCandidates |
    Where-Object { $_.Name -match '(?i)BROTHERS|D-DAY' } |
    Select-Object -First 1
if(-not $preferred){$preferred=$originalCandidates | Select-Object -First 1}

Log ("Original ISO selected: {0}" -f $preferred.FullName)
Log ("Original ISO size: {0:N2} GiB" -f ($preferred.Length/1GB))

# --------------------------------------------------------------------------
# Exact existing local toolchain discovered by the recovery scan.
# --------------------------------------------------------------------------
$Stage39BRunner=Join-Path $Root "bia_stage39b_tools\run_bia_stage39b.ps1"
$Stage39FRunner=Join-Path $Root "bia_stage39f_tools\run_bia_stage39f.ps1"
$Stage39URunner=Join-Path $Root "bia_stage39u_tools\run_bia_stage39u.ps1"
$Stage40CRetry=Join-Path $Root "bia_stage40c_retry_tools\run_bia_stage40c_retry.ps1"

$required=@(
    $Stage39BRunner,
    $Stage39FRunner,
    $Stage39URunner,
    $Stage40CRetry,
    (Join-Path $Root "bia_stage39b_tools\bia_stage39b_compiled_mdi_text.py"),
    (Join-Path $Root "bia_stage39b_tools\bia_stage39a_source_encoding_proof.py"),
    (Join-Path $Root "bia_stage39b_tools\bia_stage36_base.py"),
    (Join-Path $Root "bia_stage39b_tools\stage39a_A_translations.tsv"),
    (Join-Path $Root "bia_stage39b_tools\stage39a_font_plan.json"),
    (Join-Path $Root "bia_stage39b_tools\stage39a_tmr18_512x512_swizzled.bin")
)

$missing=@($required | Where-Object { -not (Test-Path $_) })
if($missing.Count -gt 0){
    Log "ERROR: Required local recovery assets are missing:"
    $missing | ForEach-Object { Log ("  " + $_) }
    throw "Recovery toolchain is incomplete."
}

Log "Stage39B/F/U and Stage40C local tools are present."

# --------------------------------------------------------------------------
# Space check. We need three temporary generated ISO copies during the rebuild.
# 30 GiB free from the previous cleanup is more than enough, but calculate.
# --------------------------------------------------------------------------
$isoBytes=$preferred.Length
$requiredFree=($isoBytes * 3) + 1073741824 # 3 copies + 1 GiB safety
$drive=Get-PSDrive -Name D
Log ("Free before rebuild: {0:N2} GiB" -f ($drive.Free/1GB))
Log ("Conservative rebuild requirement: {0:N2} GiB" -f ($requiredFree/1GB))

if($drive.Free -lt $requiredFree){
    # Only remove reproducible generated stage ISO outputs.
    Log "Cleaning reproducible stage ISO outputs to make room..."
    Get-ChildItem $Root -File -Filter "BIA_STAGE*.iso" -ErrorAction SilentlyContinue |
        ForEach-Object {
            try{
                $sz=$_.Length
                Remove-Item $_.FullName -Force
                Log ("  removed {0} ({1:N2} GiB)" -f $_.Name,($sz/1GB))
            } catch {
                Log ("  WARN could not remove {0}: {1}" -f $_.FullName,$_.Exception.Message)
            }
        }
    $drive=Get-PSDrive -Name D
}

if($drive.Free -lt $requiredFree){
    throw ("Not enough free space. Need {0:N2} GiB, have {1:N2} GiB." -f ($requiredFree/1GB),($drive.Free/1GB))
}

# Remove only possibly partial versions of the three outputs we are rebuilding.
$Stage39BISO=Join-Path $Root "BIA_STAGE39B_COMPILED_MDI_TEXT_TEST.iso"
$Stage39FISO=Join-Path $Root "BIA_STAGE39F_CORRECT_NARROW_METADATA_TEST.iso"
$Stage39UISO=Join-Path $Root "BIA_STAGE39U_BOOT_RENDER_UTF8_TEST.iso"
$Stage40CISO=Join-Path $Root "BIA_STAGE40C_MENU_MASS_TEST.iso"

foreach($p in @($Stage39BISO,$Stage39FISO,$Stage39UISO,$Stage40CISO)){
    if(Test-Path $p){
        Remove-Item $p -Force
        Log ("Removed stale/partial output: {0}" -f $p)
    }
}

# --------------------------------------------------------------------------
# Rebuild the exact successful chain.
#
# Stage39B:
#   original ISO -> production font (847 glyphs / 696 Hangul) + compiled MDI
# Stage39F:
#   Stage39B -> corrected two Story display values + Num/Max=10
# Stage39U:
#   Stage39F -> actual BOOT executable UTF-8-widened decoder
# --------------------------------------------------------------------------
Run-Stage "Stage39B production font + compiled MDI" $Stage39BRunner

if(-not (Test-Path $Stage39BISO)){
    throw "Stage39B reported success but output ISO is missing."
}
Log ("Stage39B ISO ready: {0:N2} GiB" -f ((Get-Item $Stage39BISO).Length/1GB))

Run-Stage "Stage39F corrected narrow metadata" $Stage39FRunner

if(-not (Test-Path $Stage39FISO)){
    throw "Stage39F reported success but output ISO is missing."
}
Log ("Stage39F ISO ready: {0:N2} GiB" -f ((Get-Item $Stage39FISO).Length/1GB))

Run-Stage "Stage39U proven renderer UTF-8 decoder" $Stage39URunner

if(-not (Test-Path $Stage39UISO)){
    throw "Stage39U reported success but output ISO is missing."
}
Log ("Stage39U ISO recovered: {0}" -f $Stage39UISO)

# Stage39U is the promoted baseline. Stage39B/F are fully reproducible and are
# no longer needed by Stage40C, so delete their large ISO copies now.
foreach($p in @($Stage39BISO,$Stage39FISO)){
    if(Test-Path $p){
        $sz=(Get-Item $p).Length
        Remove-Item $p -Force
        Log ("Removed intermediate ISO after successful Stage39U: {0} ({1:N2} GiB)" -f $p,($sz/1GB))
    }
}

$drive=Get-PSDrive -Name D
Log ("Free after Stage39U recovery: {0:N2} GiB" -f ($drive.Free/1GB))

# --------------------------------------------------------------------------
# Continue directly with the pending Stage40C menu-only relocation proof.
# --------------------------------------------------------------------------
Run-Stage "Stage40C ON_MEMU_O relocation proof" $Stage40CRetry

$Stage40CUpload=Join-Path $LogDir "bia_stage40c_upload.zip"
$Stage40CFail=Join-Path $LogDir "fail_bia_stage40c_upload.zip"

Log ""
if(Test-Path $Stage40CUpload){
    Log "SUCCESS: Stage40C upload ZIP is ready:"
    Log ("  " + $Stage40CUpload)
} elseif(Test-Path $Stage40CFail){
    Log "Stage40C produced a failure ZIP:"
    Log ("  " + $Stage40CFail)
} else {
    Log "WARNING: Stage40C finished but no result ZIP was found."
}

$drive=Get-PSDrive -Name D
Log ("Final free space: {0:N2} GiB" -f ($drive.Free/1GB))
Log ("Recovery log: {0}" -f $Log)
