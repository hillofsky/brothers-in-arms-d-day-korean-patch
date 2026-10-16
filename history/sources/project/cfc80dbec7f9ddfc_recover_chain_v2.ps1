$ErrorActionPreference="Stop"

$Root="PROJECT_ROOT"
$LogDir=Join-Path $Root "log"
if(-not (Test-Path $LogDir)){New-Item -ItemType Directory -Path $LogDir -Force | Out-Null}
$Log=Join-Path $LogDir "bia_recover_chain_v2.txt"
if(Test-Path $Log){Remove-Item $Log -Force}

function Log([string]$s){
    Write-Host $s
    $s | Add-Content $Log -Encoding UTF8
}

function Read-Json([string]$p){
    if(-not (Test-Path $p)){ return $null }
    try {
        return Get-Content $p -Raw -Encoding UTF8 | ConvertFrom-Json
    } catch {
        return $null
    }
}

function Run-AllowFail([string]$Name,[string]$Script){
    if(-not (Test-Path $Script)){
        throw "$Name tool missing: $Script"
    }
    Log ""
    Log "===== $Name ====="
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File $Script
    $code=$LASTEXITCODE
    Log ("$Name exit code: {0}" -f $code)
    return $code
}

$Stage39BRunner=Join-Path $Root "bia_stage39b_tools\run_bia_stage39b.ps1"
$Stage39FRunner=Join-Path $Root "bia_stage39f_tools\run_bia_stage39f.ps1"
$Stage39URunner=Join-Path $Root "bia_stage39u_tools\run_bia_stage39u.ps1"
$Stage40CRetry=Join-Path $Root "bia_stage40c_retry_tools\run_bia_stage40c_retry.ps1"

$Stage39BISO=Join-Path $Root "BIA_STAGE39B_COMPILED_MDI_TEXT_TEST.iso"
$Stage39FISO=Join-Path $Root "BIA_STAGE39F_CORRECT_NARROW_METADATA_TEST.iso"
$Stage39UISO=Join-Path $Root "BIA_STAGE39U_BOOT_RENDER_UTF8_TEST.iso"
$Stage40CISO=Join-Path $Root "BIA_STAGE40C_MENU_MASS_TEST.iso"

$Stage39BReport=Join-Path $Root "analysis\stage39b_compiled_mdi_text\stage39b_report.json"
$Stage39FReport=Join-Path $Root "analysis\stage39f_correct_narrow_metadata\stage39f_report.json"
$Stage39UReport=Join-Path $Root "analysis\stage39u_boot_renderer_utf8\stage39u_report.json"

Log "=== BIA recovery chain v2 ==="
Log "Important: Stage39B and Stage39F have known obsolete runtime proof checks."
Log "Their non-zero exit code is accepted ONLY when structural/runtime invariants pass."

# ----------------------------------------------------------------------
# Stage39B validator.
#
# Known historical behavior:
#   - compiled UTF-16 STORY patch itself does NOT change the visible top label;
#   - therefore source_ok=False is expected here;
#   - but production font and built ISO are valid and are exactly what Stage39F
#     needs as its source.
# ----------------------------------------------------------------------
function Test-Stage39B {
    if(-not (Test-Path $Stage39BISO)){ return $false }

    $r=Read-Json $Stage39BReport
    if($null -eq $r){ return $false }

    $ok = (
        [bool]$r.build.iso_readback_verified -and
        ([int]$r.build.story_patch_count -eq 3) -and
        [bool]$r.production_font_runtime_ok -and
        ([int]$r.runtime.production_font_runtime.glyph_count -eq 847) -and
        ($r.runtime.production_font_runtime.glyph_ptr -eq "0x098F5020") -and
        [bool]$r.runtime.production_font_runtime.all_production_mappings_ok
    )

    if($ok){
        Log "Stage39B ACCEPTED structurally."
        Log "  ISO readback: true"
        Log "  Story patch count: 3"
        Log "  production glyph_count: 847"
        Log "  production glyph_ptr: 0x098F5020"
        Log "  all production mappings: OK"
        if(-not [bool]$r.compiled_mdi_source_proof){
            Log "  visible Story proof: false (KNOWN/EXPECTED historical Stage39B limitation)"
        }
    }

    return $ok
}

if(-not (Test-Stage39B)){
    $code=Run-AllowFail "Stage39B production font / compiled MDI" $Stage39BRunner
    if(-not (Test-Stage39B)){
        throw "Stage39B structural validation failed. Do not continue."
    }
} else {
    Log "Reusing already-built valid Stage39B ISO."
}

# ----------------------------------------------------------------------
# Stage39F validator.
#
# Known historical behavior in PPSSPP v1.20.4:
#   memory.search -> "Bad message: unknown event"
# so unicode_conversion_proof=false and Stage39F exits non-zero.
#
# The Stage39F ISO itself is valid if:
#   - both UTF-8 Story display fields are resident,
#   - MenuStory key is intact,
#   - both FString ptr/Num/Max are 10/10,
#   - production font is still valid.
# ----------------------------------------------------------------------
function Test-Stage39F {
    if(-not (Test-Path $Stage39FISO)){ return $false }

    $r=Read-Json $Stage39FReport
    if($null -eq $r){ return $false }

    $src=$r.runtime.runtime_sources
    $font=$r.runtime.production_font_runtime

    $ok = (
        ($r.build.after.display1_utf8_hex -eq "ec8aa4ed86a0eba6ac00") -and
        ($r.build.after.display2_utf8_hex -eq "ec8aa4ed86a0eba6ac00") -and
        ($r.build.after.menustory_key -eq "MenuStory") -and
        [bool]$src.display1_ok -and
        [bool]$src.display2_ok -and
        [bool]$src.menustory_key_ok -and
        [bool]$src.meta1_ok -and
        [bool]$src.meta2_ok -and
        [bool]$font.ok -and
        ([int]$font.glyph_count -eq 847) -and
        ($font.glyph_ptr -eq "0x098F5020")
    )

    if($ok){
        Log "Stage39F ACCEPTED structurally/runtime-source-wise."
        Log "  Story UTF-8 fields: OK"
        Log "  MenuStory key: intact"
        Log "  Num/Max metadata: 10/10 OK"
        Log "  production font: OK"
        if(-not [bool]$r.runtime.unicode_conversion_proof){
            Log "  memory.search proof: false (KNOWN PPSSPP v1.20.4 unsupported event)"
        }
    }

    return $ok
}

if(-not (Test-Stage39F)){
    $code=Run-AllowFail "Stage39F corrected narrow metadata" $Stage39FRunner
    if(-not (Test-Stage39F)){
        throw "Stage39F structural/runtime-source validation failed. Do not continue."
    }
} else {
    Log "Reusing already-built valid Stage39F ISO."
}

# ----------------------------------------------------------------------
# Stage39U is the promoted baseline and MUST fully pass its own modern proof.
# ----------------------------------------------------------------------
Log ""
Log "===== Stage39U promoted baseline ====="

# Always rebuild U from the just-validated F so there is no ambiguity.
if(Test-Path $Stage39UISO){Remove-Item $Stage39UISO -Force}

powershell.exe -NoProfile -ExecutionPolicy Bypass -File $Stage39URunner
$uCode=$LASTEXITCODE
Log ("Stage39U exit code: {0}" -f $uCode)

if($uCode -ne 0){
    throw "Stage39U did not pass its full runtime proof."
}
if(-not (Test-Path $Stage39UISO)){
    throw "Stage39U reported success but ISO is missing."
}

$u=Read-Json $Stage39UReport
if($null -eq $u -or -not [bool]$u.completed){
    throw "Stage39U report is missing or completed != true."
}

Log "Stage39U FULL SUCCESS."
Log "  promoted ISO: $Stage39UISO"

# Only now delete large intermediate B/F ISOs.
foreach($p in @($Stage39BISO,$Stage39FISO)){
    if(Test-Path $p){
        $sz=(Get-Item $p).Length
        Remove-Item $p -Force
        Log ("Removed reproducible intermediate ISO: {0} ({1:N2} GiB)" -f $p,($sz/1GB))
    }
}

$drive=Get-PSDrive D
Log ("Free before Stage40C: {0:N2} GiB" -f ($drive.Free/1GB))

# ----------------------------------------------------------------------
# Continue Stage40C.
# ----------------------------------------------------------------------
Log ""
Log "===== Stage40C menu-only mass relocation proof ====="
powershell.exe -NoProfile -ExecutionPolicy Bypass -File $Stage40CRetry
$cCode=$LASTEXITCODE
Log ("Stage40C exit code: {0}" -f $cCode)

$good=Join-Path $LogDir "bia_stage40c_upload.zip"
$bad=Join-Path $LogDir "fail_bia_stage40c_upload.zip"

if($cCode -eq 0 -and (Test-Path $good)){
    Log "Stage40C SUCCESS:"
    Log ("  " + $good)
} elseif(Test-Path $bad){
    Log "Stage40C produced a failure ZIP:"
    Log ("  " + $bad)
    throw "Stage40C failed; upload its failure ZIP."
} else {
    throw "Stage40C failed without a result ZIP."
}

$drive=Get-PSDrive D
Log ("Final free space: {0:N2} GiB" -f ($drive.Free/1GB))
Log ("Overall log: {0}" -f $Log)
