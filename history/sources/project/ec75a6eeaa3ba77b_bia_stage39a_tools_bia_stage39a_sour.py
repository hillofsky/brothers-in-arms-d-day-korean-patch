#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import struct
import subprocess
import sys
import time
import traceback
import zipfile
from pathlib import Path

ROOT = Path(r"PROJECT_ROOT")
OUT = ROOT / "analysis" / "stage39a_source_encoding_proof"
LOG_DIR = ROOT / "log"
TEST_ISO = ROOT / "BIA_STAGE39A_PRODUCTION_FONT_ENCODING_TEST.iso"

SUCCESS_ZIP = LOG_DIR / "bia_stage39a_upload.zip"
FAIL_ZIP = LOG_DIR / "fail_bia_stage39a_upload.zip"

TARGET_LOCALIZE = ["PSP_GAME", "USRDIR", "SYSTEM", "LOCALIZE.INT"]
TARGET_NEWLOCALIZE = ["PSP_GAME", "USRDIR", "SYSTEM", "NEWLOCALIZE.INT"]

STREAM23_INDEX = 23
GLYPH_REC_SIZE = 24
ORIGINAL_GLYPH_COUNT = 151

TEST_SOURCE_TEXT = "스토리"

SCRIPT_DIR = Path(__file__).resolve().parent

spec = importlib.util.spec_from_file_location(
    "bia_stage36_base",
    SCRIPT_DIR / "bia_stage36_base.py",
)
b = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(b)

# Make the imported helper write its small config files into this stage folder.
b.ANALYSIS_DIR = OUT
b.LOG_DIR = LOG_DIR


def log(msg: str):
    print(msg, flush=True)


def sha1(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


def align(v: int, a: int) -> int:
    return (v + a - 1) // a * a


def read_plan():
    plan = json.loads(
        (SCRIPT_DIR / "stage39a_font_plan.json").read_text(encoding="utf-8")
    )
    atlas = (
        SCRIPT_DIR / "stage39a_tmr18_512x512_swizzled.bin"
    ).read_bytes()

    if len(atlas) != 0x20000:
        raise RuntimeError(f"Atlas size is {len(atlas)}, expected 0x20000")
    if sha1(atlas) != plan["atlas_sha1"]:
        raise RuntimeError("Atlas SHA1 does not match font plan")

    return plan, atlas


def read_translation_corpus():
    p = SCRIPT_DIR / "stage39a_A_translations.tsv"
    rows = list(csv.DictReader(
        p.open(encoding="utf-8-sig", newline=""),
        delimiter="\t",
    ))

    if len(rows) != 1082:
        raise RuntimeError(
            f"Expected 1082 reviewed A translations, found {len(rows)}"
        )

    chars = set()
    for row in rows:
        ko = row["한국어"]
        if not ko:
            raise RuntimeError(f"Blank Korean translation: {row['id']}")
        for ch in ko:
            if 0xAC00 <= ord(ch) <= 0xD7A3:
                chars.add(ch)

    return rows, chars


def patch_production_mdi(original: bytes, atlas: bytes, plan: dict):
    streams = b.parse_mdi(original)

    if len(streams) <= STREAM23_INDEX:
        raise RuntimeError("MDI does not contain stream23")

    s0 = streams[0]
    s19 = streams[b.STREAM19_INDEX]
    s22 = streams[b.STREAM22_INDEX]
    s23 = streams[STREAM23_INDEX]

    if len(s19["decoded"]) != b.MDI_STREAM_SIZE:
        raise RuntimeError("stream19 unexpected size")
    if len(s22["decoded"]) != b.MDI_STREAM_SIZE:
        raise RuntimeError("stream22 unexpected size")
    if len(s23["decoded"]) != b.MDI_STREAM_SIZE:
        raise RuntimeError("stream23 unexpected size")
    if any(s22["decoded"]):
        raise RuntimeError("original stream22 is not zero")
    if any(s23["decoded"]):
        raise RuntimeError("original stream23 is not zero")

    dec0 = s0["decoded"]
    dec19 = bytearray(s19["decoded"])
    dec22 = bytearray(s22["decoded"])
    dec23 = bytearray(s23["decoded"])

    old_count = struct.unpack_from("<H", dec19, b.TMR_COUNT_OFF)[0]
    old_ptr = struct.unpack_from("<I", dec19, b.TMR_GLYPH_PTR_OFF)[0]
    if old_count != ORIGINAL_GLYPH_COUNT or old_ptr != 0x09723FD8:
        raise RuntimeError(
            f"Unexpected original TMR font object: "
            f"count={old_count} ptr=0x{old_ptr:08X}"
        )

    stream23_base = b.MDI_SEQ_BASE + STREAM23_INDEX * b.MDI_STREAM_SIZE

    # Original Latin records.
    old_ptr_off = old_ptr - b.STREAM19_RAM_BASE
    latin = bytes(
        dec19[
            old_ptr_off:
            old_ptr_off + ORIGINAL_GLYPH_COUNT * GLYPH_REC_SIZE
        ]
    )

    layout = sorted(plan["layout"], key=lambda x: x["glyph_index"])
    hangul_count = len(layout)
    glyph_count = ORIGINAL_GLYPH_COUNT + hangul_count

    if glyph_count != plan["glyph_count_total"]:
        raise RuntimeError("Plan glyph count mismatch")

    glyph_array_off = 0x0000
    glyph_bytes = glyph_count * GLYPH_REC_SIZE
    pages_off = align(glyph_bytes, 0x100)

    high_bytes = sorted({int(x["codepoint"]) >> 8 for x in layout})
    page_offsets = {
        hb: pages_off + i * 512
        for i, hb in enumerate(high_bytes)
    }
    aux_off = align(pages_off + len(high_bytes) * 512, 0x100)

    widths_off = aux_off
    heights_off = aux_off + 0x10
    texptrs_off = aux_off + 0x20
    used_end = texptrs_off + 0x10

    if used_end > b.MDI_STREAM_SIZE:
        raise RuntimeError(
            f"stream23 production metadata exceeds capacity: 0x{used_end:X}"
        )

    # Put original Latin records first.
    dec23[
        glyph_array_off:
        glyph_array_off + len(latin)
    ] = latin

    # A record supplies the already-proven metrics/advance.
    A_MAP_VALUE = 34
    a_off = old_ptr_off + A_MAP_VALUE * GLYPH_REC_SIZE
    template = bytes(dec19[a_off:a_off + GLYPH_REC_SIZE])

    # Allocate all actual Hangul high-byte pages.
    for hb, off in page_offsets.items():
        dec23[off:off + 512] = b"\x00" * 512
        struct.pack_into(
            "<I",
            dec19,
            b.TMR_PAGE_TABLE_OFF + hb * 4,
            stream23_base + off,
        )

    seen_indices = set()
    seen_chars = set()

    for item in layout:
        ch = item["char"]
        cp = int(item["codepoint"])
        gi = int(item["glyph_index"])
        x = int(item["atlas_x"])
        y = int(item["atlas_y"])

        if gi in seen_indices:
            raise RuntimeError(f"Duplicate glyph index {gi}")
        if ch in seen_chars:
            raise RuntimeError(f"Duplicate glyph character {ch}")
        seen_indices.add(gi)
        seen_chars.add(ch)

        if ord(ch) != cp:
            raise RuntimeError(f"Codepoint mismatch for {ch}")

        rec = bytearray(template)
        struct.pack_into("<H", rec, 0, cp)
        struct.pack_into("<f", rec, 8,  (x + 0.5) / 128.0)
        struct.pack_into("<f", rec, 12, (y + 0.5) / 256.0)
        struct.pack_into("<f", rec, 16, (x + 17.5) / 128.0)
        struct.pack_into("<f", rec, 20, (y + 16.5) / 256.0)

        roff = glyph_array_off + gi * GLYPH_REC_SIZE
        dec23[roff:roff + GLYPH_REC_SIZE] = rec

        hb = cp >> 8
        lb = cp & 0xFF
        struct.pack_into(
            "<H",
            dec23,
            page_offsets[hb] + lb * 2,
            gi,
        )

    # Read the original renderer page-0 texture object.
    old_texptrs_ptr = struct.unpack_from(
        "<I", dec19, b.TMR_FONT_TEXTURE_PTRS_FIELD
    )[0]

    stream0_off = old_texptrs_ptr - b.MDI_SEQ_BASE
    if stream0_off < 0 or stream0_off + 4 > b.MDI_STREAM_SIZE:
        raise RuntimeError(
            f"Original TMR texture-object array not in stream0: "
            f"0x{old_texptrs_ptr:08X}"
        )

    original_texture_object = struct.unpack_from(
        "<I", dec0, stream0_off
    )[0]

    # Four renderer pages, all addressing the same enlarged 512x512 texture.
    for i in range(4):
        struct.pack_into("<H", dec23, widths_off + i * 2, 128)
        struct.pack_into("<H", dec23, heights_off + i * 2, 256)
        struct.pack_into(
            "<I", dec23, texptrs_off + i * 4, original_texture_object
        )

    struct.pack_into("<H", dec19, b.TMR_COUNT_OFF, glyph_count)
    struct.pack_into(
        "<I",
        dec19,
        b.TMR_GLYPH_PTR_OFF,
        stream23_base + glyph_array_off,
    )
    struct.pack_into(
        "<I",
        dec19,
        b.TMR_FONT_WIDTHS_FIELD,
        stream23_base + widths_off,
    )
    struct.pack_into(
        "<I",
        dec19,
        b.TMR_FONT_HEIGHTS_FIELD,
        stream23_base + heights_off,
    )
    struct.pack_into(
        "<I",
        dec19,
        b.TMR_FONT_TEXTURE_PTRS_FIELD,
        stream23_base + texptrs_off,
    )

    dec22[:len(atlas)] = atlas

    rebuilt = b.rebuild_mdi(original, {
        b.STREAM19_INDEX: bytes(dec19),
        b.STREAM22_INDEX: bytes(dec22),
        STREAM23_INDEX: bytes(dec23),
    })

    # Full on-disk structural verification.
    vs = b.parse_mdi(rebuilt)
    v19 = vs[b.STREAM19_INDEX]["decoded"]
    v22 = vs[b.STREAM22_INDEX]["decoded"]
    v23 = vs[STREAM23_INDEX]["decoded"]

    rb_count = struct.unpack_from("<H", v19, b.TMR_COUNT_OFF)[0]
    rb_ptr = struct.unpack_from("<I", v19, b.TMR_GLYPH_PTR_OFF)[0]

    if rb_count != glyph_count:
        raise RuntimeError(f"rebuilt glyph count={rb_count}")
    if rb_ptr != stream23_base:
        raise RuntimeError(f"rebuilt glyph pointer=0x{rb_ptr:08X}")
    if sha1(v22[:len(atlas)]) != sha1(atlas):
        raise RuntimeError("rebuilt stream22 atlas hash mismatch")
    if v23[:len(latin)] != latin:
        raise RuntimeError("original Latin glyph records changed")

    # Verify every production Hangul page mapping.
    for item in layout:
        cp = int(item["codepoint"])
        gi = int(item["glyph_index"])
        hb = cp >> 8
        lb = cp & 0xFF

        page_ptr = struct.unpack_from(
            "<I", v19, b.TMR_PAGE_TABLE_OFF + hb * 4
        )[0]
        value = struct.unpack_from(
            "<H",
            v23,
            (page_ptr - stream23_base) + lb * 2,
        )[0]
        if value != gi:
            raise RuntimeError(
                f"U+{cp:04X} maps to {value}, expected {gi}"
            )

    return rebuilt, {
        "hangul_glyphs": hangul_count,
        "glyph_count_total": glyph_count,
        "glyph_ptr": f"0x{stream23_base:08X}",
        "stream23_base": f"0x{stream23_base:08X}",
        "stream23_used_bytes": used_end,
        "stream23_capacity": b.MDI_STREAM_SIZE,
        "unicode_high_byte_pages": len(high_bytes),
        "high_bytes": [f"0x{x:02X}" for x in high_bytes],
        "renderer_page_widths": [128, 128, 128, 128],
        "renderer_page_heights": [256, 256, 256, 256],
        "renderer_texture_object":
            f"0x{original_texture_object:08X}",
        "atlas_sha1": sha1(atlas),
        "latin_records_unchanged": True,
    }


def build_production_font_iso(source_iso: Path, plan: dict, atlas: bytes):
    if TEST_ISO.exists():
        TEST_ISO.unlink()

    log(f"[Stage39A] Copying original ISO -> {TEST_ISO.name}")
    b.copy_file_with_progress(source_iso, TEST_ISO)

    _, mdi = b.iso_read_file(source_iso, b.TARGET_MDI)
    _, dsl = b.iso_read_file(source_iso, b.TARGET_DSL)
    _, dsx = b.iso_read_file(source_iso, b.TARGET_DSX)

    if sha1(mdi) != b.EXPECTED_MDI_SHA1:
        raise RuntimeError("Original MDI SHA1 mismatch")
    if sha1(dsl) != b.EXPECTED_DSL_SHA1:
        raise RuntimeError("Original DSL SHA1 mismatch")
    if sha1(dsx) != b.EXPECTED_DSX_SHA1:
        raise RuntimeError("Original DSX SHA1 mismatch")

    patched_mdi, mdi_info = patch_production_mdi(mdi, atlas, plan)
    patched_dsl, dsl_info = b.patch_dsl_descriptor(dsl)
    patched_dsx, dsx_info = b.rebuild_dsx_from_logical(dsx, patched_dsl)

    b.append_iso_file_and_repoint(TEST_ISO, b.TARGET_MDI, patched_mdi)
    b.overwrite_iso_same_size(TEST_ISO, b.TARGET_DSL, patched_dsl)
    b.append_iso_file_and_repoint(TEST_ISO, b.TARGET_DSX, patched_dsx)

    _, mdi_rb = b.iso_read_file(TEST_ISO, b.TARGET_MDI)
    _, dsl_rb = b.iso_read_file(TEST_ISO, b.TARGET_DSL)
    _, dsx_rb = b.iso_read_file(TEST_ISO, b.TARGET_DSX)

    if mdi_rb != patched_mdi:
        raise RuntimeError("Production MDI ISO read-back mismatch")
    if dsl_rb != patched_dsl:
        raise RuntimeError("Production DSL ISO read-back mismatch")
    if dsx_rb != patched_dsx:
        raise RuntimeError("Production DSX ISO read-back mismatch")
    if b.dsx_logical_bytes(dsx_rb) != dsl_rb:
        raise RuntimeError("Production DSX logical output != DSL")

    # Save pristine source localization bytes for repeated encoding attempts.
    _, localize = b.iso_read_file(source_iso, TARGET_LOCALIZE)
    _, newlocalize = b.iso_read_file(source_iso, TARGET_NEWLOCALIZE)

    return {
        "mdi": mdi_info,
        "dsl": dsl_info,
        "dsx": dsx_info,
        "iso_readback_verified": True,
        "localize_sha1": sha1(localize),
        "newlocalize_sha1": sha1(newlocalize),
    }, localize, newlocalize


def decode_original_localization(raw: bytes):
    if raw.startswith(b"\xff\xfe"):
        return raw[2:].decode("utf-16le"), "utf-16le-bom"
    if raw.startswith(b"\xfe\xff"):
        return raw[2:].decode("utf-16be"), "utf-16be-bom"
    try:
        return raw.decode("utf-8-sig"), "utf-8"
    except UnicodeDecodeError:
        return raw.decode("cp1252"), "cp1252"


def patch_story_values(text: str):
    """
    Patch only actual localization VALUES equal to 'Story'.

    This avoids changing NSTRY/LSTRY identifiers.  The known reference
    NEWLOCALIZE:[MenuStory] TITLE=Story is included by this rule.
    """
    out = []
    changed = []

    section = ""
    lines = text.splitlines(keepends=True)

    for line_no, line in enumerate(lines, 1):
        body = line.rstrip("\r\n")
        newline = line[len(body):]

        stripped = body.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped[1:-1].strip()
            out.append(line)
            continue

        if "=" not in body:
            out.append(line)
            continue

        left, right = body.split("=", 1)
        value = right.strip()
        prefix = right[:len(right) - len(right.lstrip())]
        suffix = right[len(right.rstrip()):]

        quote = ""
        core = value
        if len(value) >= 2 and value.startswith('"') and value.endswith('"'):
            quote = '"'
            core = value[1:-1]

        if core == "Story":
            replacement = quote + TEST_SOURCE_TEXT + quote
            new_right = prefix + replacement + suffix
            out.append(left + "=" + new_right + newline)
            changed.append({
                "line": line_no,
                "section": section,
                "key": left.strip(),
                "old": core,
                "new": TEST_SOURCE_TEXT,
            })
        else:
            out.append(line)

    return "".join(out), changed


def encode_variant(text: str, variant: str):
    if variant == "utf8":
        return text.encode("utf-8")
    if variant == "utf8_bom":
        return b"\xef\xbb\xbf" + text.encode("utf-8")
    if variant == "utf16le_bom":
        return b"\xff\xfe" + text.encode("utf-16le")
    raise ValueError(variant)


def patch_localization_variant(
    iso: Path,
    original_localize: bytes,
    original_newlocalize: bytes,
    variant: str,
):
    result = {}

    total_changed = 0
    for name, target, raw in [
        ("LOCALIZE.INT", TARGET_LOCALIZE, original_localize),
        ("NEWLOCALIZE.INT", TARGET_NEWLOCALIZE, original_newlocalize),
    ]:
        text, original_encoding = decode_original_localization(raw)
        patched_text, changed = patch_story_values(text)
        total_changed += len(changed)

        encoded = encode_variant(patched_text, variant)
        iso_info = b.append_iso_file_and_repoint(
            iso, target, encoded
        )

        _, rb = b.iso_read_file(iso, target)
        if rb != encoded:
            raise RuntimeError(f"{name} ISO read-back mismatch")

        result[name] = {
            "original_encoding": original_encoding,
            "original_sha1": sha1(raw),
            "patched_sha1": sha1(encoded),
            "patched_bytes": len(encoded),
            "changed_story_values": changed,
            "iso_relocation": iso_info,
        }

    if total_changed < 1:
        raise RuntimeError(
            "No exact Story localization value was found to patch"
        )

    result["total_changed_story_values"] = total_changed
    result["variant"] = variant
    return result


def advance_until_source_text(ws, pid, base, timeout=60):
    target = TEST_SOURCE_TEXT.encode("utf-16le")
    original = "Story".encode("utf-16le")

    start = time.time()
    presses = 0
    h = b.open_process(pid)
    samples = []
    saw_original = False

    try:
        while time.time() - start < timeout:
            raw = b.guest_read(h, base, b.STORY_GUEST, 32)

            if raw.startswith(target):
                return {
                    "success": True,
                    "elapsed_seconds": round(time.time() - start, 3),
                    "start_presses": presses,
                    "story_slot_hex": raw.hex(),
                    "saw_original_story": saw_original,
                }

            if raw.startswith(original):
                saw_original = True

            if len(samples) < 20:
                samples.append(raw.hex())

            try:
                ws.request(
                    "input.buttons.press",
                    timeout=5,
                    button="start",
                    duration=2,
                )
                presses += 1
            except Exception:
                # Input failures are retried; they do not imply a font failure.
                pass

            time.sleep(0.18)
    finally:
        b.kernel32.CloseHandle(h)

    return {
        "success": False,
        "elapsed_seconds": round(time.time() - start, 3),
        "start_presses": presses,
        "saw_original_story": saw_original,
        "slot_samples_hex": samples,
    }


def inspect_production_runtime(pid, base, plan: dict, atlas_sha1: str):
    stream23_base = b.MDI_SEQ_BASE + STREAM23_INDEX * b.MDI_STREAM_SIZE

    h = b.open_process(pid)
    try:
        count = struct.unpack(
            "<H",
            b.guest_read(
                h, base,
                b.STREAM19_RAM_BASE + b.TMR_COUNT_OFF,
                2,
            ),
        )[0]

        glyph_ptr = struct.unpack(
            "<I",
            b.guest_read(
                h, base,
                b.STREAM19_RAM_BASE + b.TMR_GLYPH_PTR_OFF,
                4,
            ),
        )[0]

        desc = struct.unpack(
            "<III",
            b.guest_read(h, base, b.TMR_RUNTIME_DESC, 12),
        )

        tex = b.guest_read(
            h, base, b.TMR_TEX_ADDR, 0x20000
        )
        tex_sha1 = sha1(tex)

        # Verify every actual Korean lookup entry at runtime.
        bad_maps = []
        for item in plan["layout"]:
            cp = int(item["codepoint"])
            expected = int(item["glyph_index"])
            hb = cp >> 8
            lb = cp & 0xFF

            page_ptr = struct.unpack(
                "<I",
                b.guest_read(
                    h, base,
                    b.STREAM19_RAM_BASE
                    + b.TMR_PAGE_TABLE_OFF
                    + hb * 4,
                    4,
                ),
            )[0]

            got = struct.unpack(
                "<H",
                b.guest_read(
                    h, base,
                    page_ptr + lb * 2,
                    2,
                ),
            )[0]

            if got != expected:
                bad_maps.append({
                    "cp": f"U+{cp:04X}",
                    "expected": expected,
                    "got": got,
                    "page_ptr": f"0x{page_ptr:08X}",
                })
                if len(bad_maps) >= 10:
                    break

        result = {
            "glyph_count": count,
            "expected_glyph_count": plan["glyph_count_total"],
            "glyph_ptr": f"0x{glyph_ptr:08X}",
            "expected_glyph_ptr": f"0x{stream23_base:08X}",
            "descriptor": [f"0x{x:08X}" for x in desc],
            "expected_descriptor": [
                "0xA087D020", "0xA8090200", "0xB8000909"
            ],
            "atlas_sha1": tex_sha1,
            "expected_atlas_sha1": atlas_sha1,
            "bad_mapping_samples": bad_maps,
            "all_production_mappings_ok": not bad_maps,
        }

        result["ok"] = (
            count == plan["glyph_count_total"]
            and glyph_ptr == stream23_base
            and desc == (0xA087D020, 0xA8090200, 0xB8000909)
            and tex_sha1 == atlas_sha1
            and not bad_maps
        )
        return result
    finally:
        b.kernel32.CloseHandle(h)


def run_variant(variant: str, exe: Path, cfg: Path, plan: dict, atlas_sha1: str):
    log_path = OUT / f"stage39a_{variant}_ppsspp.log"
    screenshot = OUT / f"stage39a_{variant}.png"

    if log_path.exists():
        log_path.unlink()

    requested_port = b.choose_free_port()

    b.close_existing_ppsspp(timeout=3.0)

    cmd = [
        str(exe),
        "-d",
        f"--log={log_path}",
        "--windowed",
        f"--appendconfig={cfg}",
        f"--debugger={requested_port}",
        str(TEST_ISO),
    ]

    log(f"[Stage39A] Launching source encoding variant: {variant}")
    proc = subprocess.Popen(cmd)
    cleanup = b.register_ppsspp_auto_close(proc)

    result = {
        "variant": variant,
        "launched_pid": proc.pid,
        "log": str(log_path),
    }

    try:
        hwnd = b.find_ppsspp_hwnd(30)
        if not hwnd:
            raise RuntimeError("PPSSPP window did not appear")

        end = time.time() + 30
        pid = base = None
        while time.time() < end:
            try:
                pid, base = b.get_pid_base(hwnd)
                if pid and base:
                    break
            except Exception:
                pass
            time.sleep(0.2)

        if not pid or not base:
            raise RuntimeError("PPSSPP memory base unavailable")

        port = b.wait_for_actual_debugger_port(log_path, 30)
        ws, host = b.connect_debugger(port)

        try:
            result["debugger_host"] = host
            result["debugger_port"] = port

            try:
                result["version"] = ws.request(
                    "version",
                    timeout=5,
                    name="bia-stage39a",
                    version="1",
                )
            except Exception as e:
                result["version_error"] = str(e)

            advance = advance_until_source_text(
                ws, pid, base, timeout=60
            )
            result["advance"] = advance

            # Whether the source text succeeded or not, inspect the production
            # font if the game has reached the menu far enough to load it.
            try:
                result["production_font_runtime"] = (
                    inspect_production_runtime(
                        pid, base, plan, atlas_sha1
                    )
                )
            except Exception as e:
                result["production_font_runtime_error"] = str(e)

            # Screenshot is diagnostic only.  Failure to download/capture the
            # image is NOT treated as glyph/source failure.
            try:
                b.capture(
                    hwnd,
                    screenshot,
                    SCRIPT_DIR / "capture_ppsspp.ps1",
                )
                result["screenshot"] = str(screenshot)
            except Exception as e:
                result["screenshot_error"] = str(e)

        finally:
            ws.close()

    finally:
        try:
            cleanup()
            result["ppsspp_closed"] = True
        except Exception as e:
            result["ppsspp_close_error"] = str(e)

    return result


def make_zip(path: Path):
    if path.exists():
        path.unlink()

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(OUT.rglob("*")):
            if p.is_file():
                z.write(p, p.relative_to(OUT).as_posix())

        for name in [
            "stage39a_A_translations.tsv",
            "stage39a_font_plan.json",
            "stage39a_tmr18_512x512_preview.png",
        ]:
            p = SCRIPT_DIR / name
            if p.exists():
                z.write(p, name)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    # Clean previous Stage39A diagnostics.
    for p in OUT.iterdir():
        if p.is_file():
            p.unlink()

    plan, atlas = read_plan()
    translations, corpus = read_translation_corpus()

    planned_chars = {x["char"] for x in plan["layout"]}
    if corpus != planned_chars:
        missing = "".join(sorted(corpus - planned_chars, key=ord))
        extra = "".join(sorted(planned_chars - corpus, key=ord))
        raise RuntimeError(
            f"Translation corpus/font plan mismatch. "
            f"missing={missing!r} extra={extra!r}"
        )

    report = {
        "stage": "39A",
        "purpose":
            "Build the production A-priority Korean font and prove which "
            "on-disc .INT Unicode encoding reaches the renderer without "
            "runtime text patching",
        "reviewed_A_translation_units": len(translations),
        "production_unique_hangul": len(corpus),
        "production_glyph_count": plan["glyph_count_total"],
        "production_high_byte_pages": plan["high_byte_page_count"],
        "atlas_unused_safe_slots": plan["atlas_unused_slots"],
        "atlas_sha1": plan["atlas_sha1"],
        "runtime_text_patch": False,
        "screenshot_failure_is_not_test_failure": True,
    }

    source_iso = b.find_original_iso()
    exe = b.find_ppsspp_exe()

    report["source_iso"] = str(source_iso)
    report["ppsspp_exe"] = str(exe)
    report["test_iso"] = str(TEST_ISO)

    iso_info, original_localize, original_newlocalize = (
        build_production_font_iso(source_iso, plan, atlas)
    )
    report["production_iso"] = iso_info

    cfg = OUT / "stage39a_append.ini"
    cfg.write_text(
        "[Debugger]\n"
        "ShowDeveloperMenu = True\n"
        "\n"
        "[Graphics]\n"
        "ReplaceTextures = False\n"
        "SaveNewTextures = False\n",
        encoding="utf-8",
    )

    variants = ["utf8", "utf8_bom", "utf16le_bom"]
    selected = None
    attempts = []

    for variant in variants:
        log(f"[Stage39A] Patching Story source as {variant}")
        patch_info = patch_localization_variant(
            TEST_ISO,
            original_localize,
            original_newlocalize,
            variant,
        )

        attempt = {
            "source_patch": patch_info,
        }

        runtime = run_variant(
            variant,
            exe,
            cfg,
            plan,
            plan["atlas_sha1"],
        )
        attempt["runtime"] = runtime
        attempts.append(attempt)

        advance_ok = runtime.get("advance", {}).get("success", False)
        font_ok = runtime.get(
            "production_font_runtime", {}
        ).get("ok", False)

        if advance_ok and font_ok:
            selected = variant
            break

    report["encoding_attempts"] = attempts
    report["selected_int_encoding"] = selected
    report["source_encoding_proof"] = selected is not None

    report_path = OUT / "stage39a_report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    if selected is None:
        make_zip(FAIL_ZIP)
        raise RuntimeError(
            "None of UTF-8 / UTF-8 BOM / UTF-16LE BOM produced "
            "the Korean Story source string at runtime. "
            f"See {FAIL_ZIP}"
        )

    (OUT / "SELECTED_ENCODING.txt").write_text(
        selected + "\n",
        encoding="utf-8",
    )

    make_zip(SUCCESS_ZIP)

    log("")
    log("[Stage39A] COMPLETE")
    log(f"  A translations     : {len(translations)}")
    log(f"  unique Hangul      : {len(corpus)}")
    log(f"  production glyphs  : {plan['glyph_count_total']}")
    log(f"  high-byte pages    : {plan['high_byte_page_count']}")
    log(f"  selected encoding  : {selected}")
    log(f"  ISO                : {TEST_ISO}")
    log(f"  upload ZIP         : {SUCCESS_ZIP}")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        OUT.mkdir(parents=True, exist_ok=True)
        LOG_DIR.mkdir(parents=True, exist_ok=True)

        failure = OUT / "FAILURE.txt"
        failure.write_text(
            traceback.format_exc(),
            encoding="utf-8",
        )

        try:
            make_zip(FAIL_ZIP)
        except Exception:
            pass

        print(traceback.format_exc(), flush=True)
        print(f"STAGE 39A FAILED: {FAIL_ZIP}", flush=True)
        raise SystemExit(1)
