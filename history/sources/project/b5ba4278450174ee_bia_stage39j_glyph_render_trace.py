#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import math
import os
import struct
import subprocess
import sys
import time
import traceback
import zipfile
from pathlib import Path

ROOT = Path(r"PROJECT_ROOT")
BASE_TOOLS = ROOT / "bia_stage39b_tools"
ISO = ROOT / "BIA_STAGE39F_CORRECT_NARROW_METADATA_TEST.iso"

OUT = ROOT / "analysis" / "stage39j_glyph_render_trace"
LOG_DIR = ROOT / "log"

SUCCESS_ZIP = LOG_DIR / "bia_stage39j_upload.zip"
FAIL_ZIP = LOG_DIR / "fail_bia_stage39j_upload.zip"

REPORT_PATH = OUT / "stage39j_report.json"
PPSSPP_LOG = OUT / "stage39j_ppsspp.log"

UNICODE_LOOKUP = 0x08C7F2FC

# Proven production font state.
EXPECTED_GLYPH_PTR = 0x098F5020
EXPECTED_GLYPH_COUNT = 847
EXPECTED_ATLAS_ADDR = 0x0987D020
EXPECTED_ATLAS_SIZE = 0x20000
EXPECTED_ATLAS_SHA1 = "b58e6ef06af9555a23d8be1f70a0e8d65b2ce4c6"

# At lookup entry Stage39I showed:
#   a0 = 0x097238B4  (Unicode high-byte page-table base)
#   s0 = 0x0972385C  (TMR18 font object)
EXPECTED_FONT_OBJECT = 0x0972385C
EXPECTED_PAGE_TABLE = 0x097238B4

# Renderer page-array pointers are stored in the TMR object at these offsets.
FONT_WIDTHS_FIELD = 0x474
FONT_HEIGHTS_FIELD = 0x478
FONT_TEXTURE_PTRS_FIELD = 0x488

GLYPH_RECORD_SIZE = 24

TEXT = "\uc2a4\ud1a0\ub9ac"
CPS = [ord(x) for x in TEXT]
FIRST_CP = CPS[0]

# Stage39H opens this before the title/menu environment.
MENU_OPEN_MARKER = (
    "sceIoOpen(disc0:/PSP_GAME/USRDIR/SYSTEM/RAWFILES/MENUINT0.RAW"
)

# Collect enough subsequent codepoints to cover "토리" and usually the
# beginning of the next menu item.
FOLLOWING_LOOKUPS = 16

SCRIPT_DIR = Path(__file__).resolve().parent


def log(msg):
    print(msg, flush=True)


def load_helpers():
    module_path = BASE_TOOLS / "bia_stage39b_compiled_mdi_text.py"
    if not module_path.exists():
        raise RuntimeError(f"Missing Stage39B helper: {module_path}")

    sys.path.insert(0, str(BASE_TOOLS))
    spec = importlib.util.spec_from_file_location(
        "bia_stage39b_local", module_path
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)

    b = getattr(mod, "b", None)
    if b is None and hasattr(mod, "s39"):
        b = getattr(mod.s39, "b", None)
    if b is None:
        raise RuntimeError("Could not resolve Stage39B helper module")

    return mod, b


def regs_to_dict(resp):
    out = {}
    for cat in resp.get("categories", []):
        names = cat.get("registerNames", [])
        vals = cat.get("uintValues", [])
        for n, v in zip(names, vals):
            out[n.lower()] = int(v) & 0xFFFFFFFF
    return out


def read_ws(ws, address, size):
    r = ws.request(
        "memory.read",
        timeout=10,
        address=address,
        size=size,
    )
    return base64.b64decode(r["base64"])


def read_u16(ws, address):
    return struct.unpack("<H", read_ws(ws, address, 2))[0]


def read_u32(ws, address):
    return struct.unpack("<I", read_ws(ws, address, 4))[0]


def disasm(ws, address, count=32):
    try:
        return ws.request(
            "memory.disasm",
            timeout=10,
            address=address & 0xFFFFFFFF,
            count=count,
            displaySymbols=True,
            compact=False,
        )
    except Exception as e:
        return {"error": str(e)}


def wait_pause(ws, timeout=45.0):
    end = time.time() + timeout
    last = None
    while time.time() < end:
        try:
            last = ws.request("cpu.status", timeout=3)
            if last.get("stepping", False):
                return last
        except Exception:
            pass
        time.sleep(0.035)
    return None


def remove_bp(ws, address):
    try:
        ws.request(
            "cpu.breakpoint.remove",
            timeout=5,
            address=address,
        )
    except Exception:
        pass


def resume(ws):
    try:
        ws.request("cpu.resume", timeout=1)
    except Exception:
        pass


def log_has_menu_open():
    if not PPSSPP_LOG.exists():
        return False
    try:
        txt = PPSSPP_LOG.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return False
    return MENU_OPEN_MARKER in txt


def wait_menu_open(ws, timeout=120.0):
    end = time.time() + timeout
    last_press = 0.0
    presses = 0

    while time.time() < end:
        if log_has_menu_open():
            return {"opened": True, "start_presses": presses}

        now = time.time()
        if now - last_press >= 1.25:
            try:
                ws.request(
                    "input.buttons.press",
                    timeout=3,
                    button="start",
                    duration=2,
                )
                presses += 1
            except Exception:
                pass
            last_press = now
        time.sleep(0.12)

    return {"opened": False, "start_presses": presses}


def pointer_memory_samples(ws, regs):
    """
    Sample PSP-RAM pointer registers at the lookup hit.  This is especially
    useful for identifying the real UTF-16 source buffer used by the renderer.
    """
    out = []
    for name, value in regs.items():
        if not isinstance(value, int):
            continue
        if not (0x08800000 <= value < 0x0A800000):
            continue

        try:
            lo = max(0x08800000, value - 24)
            raw = read_ws(ws, lo, 80)
        except Exception:
            continue

        item = {
            "register": name,
            "value": f"0x{value:08X}",
            "sample_base": f"0x{lo:08X}",
            "sample_hex": raw.hex(),
            "contains_story_utf16":
                TEXT.encode("utf-16le") in raw,
        }
        out.append(item)

    return out


def map_codepoint(ws, page_table, cp):
    hb = (cp >> 8) & 0xFF
    lb = cp & 0xFF

    page_ptr = read_u32(
        ws, page_table + hb * 4
    )
    glyph_index = read_u16(
        ws, page_ptr + lb * 2
    )

    return {
        "codepoint": f"U+{cp:04X}",
        "high_byte": f"0x{hb:02X}",
        "low_byte": f"0x{lb:02X}",
        "page_ptr": f"0x{page_ptr:08X}",
        "glyph_index": glyph_index,
    }


def decode_glyph_record(raw):
    if len(raw) != GLYPH_RECORD_SIZE:
        raise ValueError("bad glyph record size")

    cp = struct.unpack_from("<H", raw, 0)[0]
    metrics = list(raw[2:8])
    u0, v0, u1, v1 = struct.unpack_from("<ffff", raw, 8)

    return {
        "raw_hex": raw.hex(),
        "codepoint_field": f"U+{cp:04X}",
        "metrics_2_7": metrics,
        "u0": u0,
        "v0": v0,
        "u1": u1,
        "v1": v1,
        "renderer_page": int(math.trunc(u0)),
        "fractional_u0": u0 - math.trunc(u0),
    }


def font_state(ws, regs):
    page_table = regs.get("a0", 0)
    font_object = regs.get("s0", 0)

    state = {
        "lookup_a0_page_table": f"0x{page_table:08X}",
        "lookup_s0_font_object": f"0x{font_object:08X}",
        "expected_page_table": f"0x{EXPECTED_PAGE_TABLE:08X}",
        "expected_font_object": f"0x{EXPECTED_FONT_OBJECT:08X}",
    }

    # Map the three Story syllables exactly as the lookup function does.
    mappings = []
    for cp in CPS:
        m = map_codepoint(ws, page_table, cp)
        gi = int(m["glyph_index"])

        rec_addr = EXPECTED_GLYPH_PTR + gi * GLYPH_RECORD_SIZE
        rec = read_ws(ws, rec_addr, GLYPH_RECORD_SIZE)

        m["glyph_record_address"] = f"0x{rec_addr:08X}"
        m["glyph_record"] = decode_glyph_record(rec)
        mappings.append(m)

    state["story_mappings"] = mappings

    # Page arrays from the live font object.
    widths_ptr = read_u32(
        ws, font_object + FONT_WIDTHS_FIELD
    )
    heights_ptr = read_u32(
        ws, font_object + FONT_HEIGHTS_FIELD
    )
    tex_ptrs_ptr = read_u32(
        ws, font_object + FONT_TEXTURE_PTRS_FIELD
    )

    widths = list(struct.unpack(
        "<4H", read_ws(ws, widths_ptr, 8)
    ))
    heights = list(struct.unpack(
        "<4H", read_ws(ws, heights_ptr, 8)
    ))
    textures = list(struct.unpack(
        "<4I", read_ws(ws, tex_ptrs_ptr, 16)
    ))

    state["renderer_arrays"] = {
        "widths_ptr": f"0x{widths_ptr:08X}",
        "widths": widths,
        "heights_ptr": f"0x{heights_ptr:08X}",
        "heights": heights,
        "texture_ptrs_ptr": f"0x{tex_ptrs_ptr:08X}",
        "textures": [f"0x{x:08X}" for x in textures],
    }

    atlas = read_ws(
        ws, EXPECTED_ATLAS_ADDR, EXPECTED_ATLAS_SIZE
    )
    state["atlas"] = {
        "address": f"0x{EXPECTED_ATLAS_ADDR:08X}",
        "size": len(atlas),
        "sha1": hashlib.sha1(atlas).hexdigest(),
        "expected_sha1": EXPECTED_ATLAS_SHA1,
        "ok": hashlib.sha1(atlas).hexdigest()
            == EXPECTED_ATLAS_SHA1,
    }

    return state


def wait_for_lookup(ws, cp, timeout=45.0):
    remove_bp(ws, UNICODE_LOOKUP)
    ws.request(
        "cpu.breakpoint.add",
        timeout=10,
        address=UNICODE_LOOKUP,
        enabled=True,
        log=True,
        condition=f"a1 == 0x{cp:04X}",
        logFormat=(
            "BIA39J_LOOKUP "
            "pc={pc} ra={ra} a0={a0} a1={a1} "
            "s0={s0} s1={s1} t0={t0} t1={t1} t4={t4}"
        ),
    )
    return wait_pause(ws, timeout=timeout)


def collect_following_lookup_sequence(ws, count):
    """
    Called while paused at the first Story lookup return/caller state.
    Break at lookup entry unconditionally and record the next N codepoints.
    """
    remove_bp(ws, UNICODE_LOOKUP)

    ws.request(
        "cpu.breakpoint.add",
        timeout=10,
        address=UNICODE_LOOKUP,
        enabled=True,
        log=False,
    )

    seq = []

    for i in range(count):
        resume(ws)
        paused = wait_pause(ws, timeout=8.0)
        if paused is None:
            break

        regs = regs_to_dict(
            ws.request("cpu.getAllRegs", timeout=10)
        )
        seq.append({
            "index": i,
            "a1_codepoint":
                f"U+{regs.get('a1', 0) & 0xFFFF:04X}",
            "a1_raw": f"0x{regs.get('a1', 0):08X}",
            "ra": f"0x{regs.get('ra', 0):08X}",
            "a0": f"0x{regs.get('a0', 0):08X}",
            "s0": f"0x{regs.get('s0', 0):08X}",
        })

    remove_bp(ws, UNICODE_LOOKUP)
    return seq


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    for p in OUT.iterdir():
        if p.is_file():
            p.unlink()

    if not ISO.exists():
        raise RuntimeError(f"Missing ISO: {ISO}")

    _, b = load_helpers()

    exe = b.find_ppsspp_exe()

    cfg = OUT / "stage39j_append.ini"
    cfg.write_text(
        "[Debugger]\n"
        "ShowDeveloperMenu = True\n"
        "\n"
        "[Graphics]\n"
        "ReplaceTextures = False\n"
        "SaveNewTextures = False\n",
        encoding="utf-8",
    )

    if PPSSPP_LOG.exists():
        PPSSPP_LOG.unlink()

    try:
        b.close_existing_ppsspp(timeout=3.0)
    except Exception:
        pass

    requested_port = b.choose_free_port()

    cmd = [
        str(exe),
        "-d",
        f"--log={PPSSPP_LOG}",
        "--windowed",
        f"--appendconfig={cfg}",
        f"--debugger={requested_port}",
        str(ISO),
    ]

    log("[Stage39J] Launching PPSSPP normal JIT")
    proc = subprocess.Popen(cmd)
    cleanup = b.register_ppsspp_auto_close(proc)

    report = {
        "stage": "39J",
        "purpose":
            "Determine whether the visibly corrupted Korean menu item reaches "
            "the proven Unicode lookup as the correct three Hangul codepoints, "
            "then verify lookup result, glyph records, page arrays and atlas.",
        "iso_patch": False,
        "runtime_patch": False,
        "stage39i_findings": {
            "narrow_source_read_trace":
                "Still caught openseason_data_decode; source bytes were zero "
                "when the memcheck was installed, so this was not the real menu consumer.",
            "bad_u00ec_lookup_hit": False,
            "good_uc2a4_lookup_hit": True,
            "good_hit_ra": "0x08C7F9BC",
            "implication":
                "The visual corruption cannot be attributed solely to UTF-8 "
                "bytes being passed as U+00xx through this Unicode lookup.",
        },
    }

    try:
        hwnd = b.find_ppsspp_hwnd(30)
        if not hwnd:
            raise RuntimeError("PPSSPP window did not appear")

        actual_port = b.wait_for_actual_debugger_port(
            PPSSPP_LOG, 30
        )
        ws, host = b.connect_debugger(actual_port)

        try:
            report["debugger_host"] = host
            report["debugger_port"] = actual_port

            menu = wait_menu_open(ws, timeout=120.0)
            report["menu_resource_open"] = menu
            if not menu["opened"]:
                raise RuntimeError("MENUINT0.RAW did not open")

            # Install the proven lookup breakpoint before entering selectable
            # main menu.
            paused = wait_for_lookup(
                ws, FIRST_CP, timeout=1.0
            )

            # If background/title path already rendered it, record that.
            if paused is None:
                try:
                    ws.request(
                        "input.buttons.press",
                        timeout=5,
                        button="start",
                        duration=2,
                    )
                    report["main_menu_start_sent"] = True
                except Exception as e:
                    report["main_menu_start_error"] = str(e)

                paused = wait_pause(ws, timeout=45.0)

            if paused is None:
                raise RuntimeError(
                    "U+C2A4 did not reach Unicode lookup"
                )

            regs = regs_to_dict(
                ws.request("cpu.getAllRegs", timeout=10)
            )

            entry = {
                "pc": f"0x{regs.get('pc', 0):08X}",
                "ra": f"0x{regs.get('ra', 0):08X}",
                "a0": f"0x{regs.get('a0', 0):08X}",
                "a1": f"0x{regs.get('a1', 0):08X}",
                "s0": f"0x{regs.get('s0', 0):08X}",
                "register_pointer_samples":
                    pointer_memory_samples(ws, regs),
                "lookup_disasm":
                    disasm(ws, UNICODE_LOOKUP, 36),
                "caller_disasm":
                    disasm(
                        ws,
                        max(0, regs.get("ra", 0) - 0x40),
                        44,
                    ),
            }

            entry["font_state"] = font_state(ws, regs)
            report["first_story_lookup"] = entry

            # Prove the actual return value from the Unicode lookup.
            ra = regs.get("ra", 0)
            if not ra:
                raise RuntimeError("Lookup RA is zero")

            remove_bp(ws, UNICODE_LOOKUP)
            ws.request(
                "cpu.breakpoint.add",
                timeout=10,
                address=ra,
                enabled=True,
                log=False,
            )

            resume(ws)
            ret_pause = wait_pause(ws, timeout=8.0)

            if ret_pause is not None:
                ret_regs = regs_to_dict(
                    ws.request("cpu.getAllRegs", timeout=10)
                )
                report["first_lookup_return"] = {
                    "pc": f"0x{ret_regs.get('pc', 0):08X}",
                    "v0": f"0x{ret_regs.get('v0', 0):08X}",
                    "v0_decimal": ret_regs.get("v0", 0),
                    "expected_from_manual_mapping":
                        entry["font_state"]["story_mappings"][0]["glyph_index"],
                    "post_return_disasm":
                        disasm(ws, ra, 36),
                }
            else:
                report["first_lookup_return"] = {
                    "error": "return breakpoint did not hit"
                }

            remove_bp(ws, ra)

            # The most important sequence test:
            # after "스", do we immediately see "토", "리" through the same
            # lookup/caller?  If yes, the visible path is Unicode-correct and
            # the corruption is downstream (glyph record/page/atlas/rendering).
            report["following_lookup_sequence"] = (
                collect_following_lookup_sequence(
                    ws, FOLLOWING_LOOKUPS
                )
            )

            seq = [
                x["a1_codepoint"]
                for x in report["following_lookup_sequence"]
            ]

            report["sequence_analysis"] = {
                "expected_next_two": [
                    f"U+{CPS[1]:04X}",
                    f"U+{CPS[2]:04X}",
                ],
                "observed_first_two": seq[:2],
                "story_sequence_confirmed":
                    seq[:2] == [
                        f"U+{CPS[1]:04X}",
                        f"U+{CPS[2]:04X}",
                    ],
            }

            # Save a compact diagnostic text file too.
            summary_lines = [
                "Stage39J glyph/render trace",
                "",
                f"Story first lookup RA: {entry['ra']}",
                f"Story mapping: "
                + ", ".join(
                    f"{m['codepoint']}->{m['glyph_index']}"
                    for m in entry["font_state"]["story_mappings"]
                ),
                f"Following codepoints: {' '.join(seq)}",
                f"Story sequence confirmed: "
                f"{report['sequence_analysis']['story_sequence_confirmed']}",
                f"Atlas SHA1: "
                f"{entry['font_state']['atlas']['sha1']}",
            ]
            (OUT / "stage39j_summary.txt").write_text(
                "\n".join(summary_lines),
                encoding="utf-8",
            )

            # A trace is considered successful when the first Hangul lookup
            # and all three mappings were captured.  We intentionally do not
            # claim visual success here.
            report["completed"] = True

        finally:
            try:
                ws.close()
            except Exception:
                pass

    except Exception as e:
        report["runtime_exception"] = str(e)
        report["runtime_traceback"] = traceback.format_exc()
        report["completed"] = False

    finally:
        try:
            cleanup()
            report["ppsspp_closed"] = True
        except Exception as e:
            report["ppsspp_close_error"] = str(e)

    REPORT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    target = SUCCESS_ZIP if report["completed"] else FAIL_ZIP
    if target.exists():
        target.unlink()

    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(OUT.rglob("*")):
            if p.is_file():
                z.write(p, p.relative_to(OUT).as_posix())

    if not report["completed"]:
        raise RuntimeError(
            f"Stage39J trace failed. See {FAIL_ZIP}"
        )

    log("[Stage39J] COMPLETE")
    log(f"[Stage39J] Upload ZIP: {SUCCESS_ZIP}")


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
            if FAIL_ZIP.exists():
                FAIL_ZIP.unlink()
            with zipfile.ZipFile(
                FAIL_ZIP, "w", zipfile.ZIP_DEFLATED
            ) as z:
                for p in sorted(OUT.rglob("*")):
                    if p.is_file():
                        z.write(
                            p, p.relative_to(OUT).as_posix()
                        )
        except Exception:
            pass

        print(traceback.format_exc(), flush=True)
        print(f"STAGE 39J FAILED: {FAIL_ZIP}", flush=True)
        raise SystemExit(1)
