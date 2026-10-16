#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import base64
import importlib.util
import json
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

OUT = ROOT / "analysis" / "stage39k_visible_narrow_renderer"
LOG_DIR = ROOT / "log"

SUCCESS_ZIP = LOG_DIR / "bia_stage39k_upload.zip"
FAIL_ZIP = LOG_DIR / "fail_bia_stage39k_upload.zip"

REPORT_PATH = OUT / "stage39k_report.json"
PPSSPP_LOG = OUT / "stage39k_ppsspp.log"

# Correct Stage39F source/metadata.
DISPLAY1_ADDR = 0x093B1B40
DISPLAY2_ADDR = 0x093B1BF0
META1_ADDR = 0x095EC774
META2_ADDR = 0x095F1758

UTF8 = "\uc2a4\ud1a0\ub9ac".encode("utf-8")
UTF8_NUL = UTF8 + b"\x00"

EXPECTED_META1 = (DISPLAY1_ADDR, 10, 10)
EXPECTED_META2 = (DISPLAY2_ADDR, 10, 10)

# Production glyph array.
GLYPH_PTR = 0x098F5020
GLYPH_REC_SIZE = 24

# Stage39H GPU dump decoded the visible top menu item as NINE glyph sprites.
# The first visible sprite uses original glyph index 135 = U+00EC, the first
# byte of UTF-8 "스". Unsupported following bytes use fallback glyph 0.
#
# The fourth visible sprite is glyph index 136 = U+00ED.
GLYPH_EC = 135
GLYPH_FALLBACK = 0
GLYPH_ED = 136

REC_EC = GLYPH_PTR + GLYPH_EC * GLYPH_REC_SIZE
REC_FALLBACK = GLYPH_PTR + GLYPH_FALLBACK * GLYPH_REC_SIZE
REC_ED = GLYPH_PTR + GLYPH_ED * GLYPH_REC_SIZE

# Break specifically on UV floats (+8..+23). Width/measurement routines usually
# touch byte +6 only, so this strongly selects the real quad renderer.
UV_EC = REC_EC + 8
UV_FALLBACK = REC_FALLBACK + 8
UV_ED = REC_ED + 8
UV_SIZE = 16

MENU_OPEN_MARKER = (
    "sceIoOpen(disc0:/PSP_GAME/USRDIR/SYSTEM/RAWFILES/MENUINT0.RAW"
)

GPR_NAMES = [
    "zero","at","v0","v1","a0","a1","a2","a3",
    "t0","t1","t2","t3","t4","t5","t6","t7",
    "s0","s1","s2","s3","s4","s5","s6","s7",
    "t8","t9","k0","k1","gp","sp","fp","ra","pc",
]


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


def read_ws(ws, addr, size):
    r = ws.request(
        "memory.read",
        timeout=10,
        address=addr,
        size=size,
    )
    return base64.b64decode(r["base64"])


def regs_to_dict(resp):
    out = {}
    for cat in resp.get("categories", []):
        names = cat.get("registerNames", [])
        values = cat.get("uintValues", [])
        for n, v in zip(names, values):
            out[n.lower()] = int(v) & 0xFFFFFFFF
    return out


def disasm(ws, address, count=48):
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


def wait_pause(ws, timeout=90.0):
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


def resume(ws):
    try:
        ws.request("cpu.resume", timeout=1)
    except Exception:
        pass


def add_read_memcheck(ws, address, label):
    return ws.request(
        "memory.breakpoint.add",
        timeout=10,
        address=address,
        size=UV_SIZE,
        enabled=True,
        log=True,
        read=True,
        write=False,
        change=False,
        logFormat=(
            f"BIA39K_{label} "
            "pc={pc} ra={ra} "
            "a0={a0} a1={a1} a2={a2} a3={a3} "
            "s0={s0} s1={s1} s2={s2} s3={s3} "
            "s4={s4} s5={s5} s6={s6} s7={s7} "
            "t0={t0} t1={t1} t2={t2} t3={t3}"
        ),
    )


def remove_memcheck(ws, address):
    try:
        ws.request(
            "memory.breakpoint.remove",
            timeout=5,
            address=address,
            size=UV_SIZE,
        )
    except Exception:
        pass


def wait_menu_open(ws, timeout=180.0):
    end = time.time() + timeout
    last_press = 0.0
    presses = 0

    while time.time() < end:
        if PPSSPP_LOG.exists():
            txt = PPSSPP_LOG.read_text(
                encoding="utf-8", errors="replace"
            )
            if MENU_OPEN_MARKER in txt:
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


def wait_correct_source_resident(ws, timeout=60.0):
    end = time.time() + timeout
    last = None

    while time.time() < end:
        try:
            d1 = read_ws(ws, DISPLAY1_ADDR, 16)
            d2 = read_ws(ws, DISPLAY2_ADDR, 16)
            m1 = struct.unpack("<III", read_ws(ws, META1_ADDR, 12))
            m2 = struct.unpack("<III", read_ws(ws, META2_ADDR, 12))

            last = {
                "display1": d1.hex(),
                "display2": d2.hex(),
                "meta1": [f"0x{m1[0]:08X}", m1[1], m1[2]],
                "meta2": [f"0x{m2[0]:08X}", m2[1], m2[2]],
            }

            if (
                d1.startswith(UTF8_NUL)
                and d2.startswith(UTF8_NUL)
                and m1 == EXPECTED_META1
                and m2 == EXPECTED_META2
            ):
                last["ok"] = True
                return last
        except Exception:
            pass

        time.sleep(0.15)

    if last is None:
        last = {}
    last["ok"] = False
    return last


def pointer_samples(ws, regs):
    """
    Search memory around every PSP-RAM GPR for the UTF-8 Story byte sequence.
    The visible narrow renderer should normally retain either a string base or
    current cursor in one of these registers.
    """
    out = []
    for name in GPR_NAMES:
        if name not in regs:
            continue
        value = regs[name]
        if not (0x08800000 <= value < 0x0A800000):
            continue

        base = max(0x08800000, value - 64)
        try:
            raw = read_ws(ws, base, 160)
        except Exception:
            continue

        pos = raw.find(UTF8)
        out.append({
            "register": name,
            "value": f"0x{value:08X}",
            "sample_base": f"0x{base:08X}",
            "utf8_story_offset":
                None if pos < 0 else pos,
            "utf8_story_address":
                None if pos < 0 else f"0x{base + pos:08X}",
            "sample_hex": raw.hex(),
        })

    return out


def stack_scan(ws, regs):
    sp = regs.get("sp", 0)
    if not (0x08800000 <= sp < 0x0A800000):
        return None

    base = max(0x08800000, sp - 0x100)
    try:
        raw = read_ws(ws, base, 0x500)
    except Exception as e:
        return {"error": str(e)}

    hits = []
    pos = 0
    while True:
        p = raw.find(UTF8, pos)
        if p < 0:
            break
        hits.append(f"0x{base+p:08X}")
        pos = p + 1

    return {
        "base": f"0x{base:08X}",
        "size": len(raw),
        "utf8_hits": hits,
        "hex": raw.hex(),
    }


def capture_hit(ws, paused, label, expected_record):
    regs = regs_to_dict(
        ws.request("cpu.getAllRegs", timeout=10)
    )
    pc = regs.get("pc", int(paused.get("pc", 0)))
    ra = regs.get("ra", 0)

    return {
        "label": label,
        "expected_record": f"0x{expected_record:08X}",
        "pc": f"0x{pc:08X}",
        "ra": f"0x{ra:08X}",
        "registers": {
            k: f"0x{v:08X}"
            for k, v in regs.items()
            if isinstance(v, int)
        },
        "pointer_samples": pointer_samples(ws, regs),
        "stack_scan": stack_scan(ws, regs),
        "instruction_window":
            disasm(ws, max(0, pc - 0x80), 80),
        "caller_window":
            disasm(ws, max(0, ra - 0x60), 64)
            if ra else None,
    }


def trace_next_record(ws, old_addr, new_addr, label, timeout=15.0):
    remove_memcheck(ws, old_addr)
    add_read_memcheck(ws, new_addr, label)
    resume(ws)
    paused = wait_pause(ws, timeout=timeout)

    if paused is None:
        remove_memcheck(ws, new_addr)
        return {
            "label": label,
            "hit": False,
        }

    hit = capture_hit(
        ws, paused, label, new_addr - 8
    )
    hit["hit"] = True
    remove_memcheck(ws, new_addr)
    return hit


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    for p in OUT.iterdir():
        if p.is_file():
            p.unlink()

    if not ISO.exists():
        raise RuntimeError(f"Missing Stage39F ISO: {ISO}")

    _, b = load_helpers()

    exe = b.find_ppsspp_exe()

    cfg = OUT / "stage39k_append.ini"
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

    # Interpreter mode is deliberate: read memchecks pause before the exact
    # glyph-record UV access and give an unambiguous renderer PC.
    cmd = [
        str(exe),
        "-i",
        "-d",
        f"--log={PPSSPP_LOG}",
        "--windowed",
        f"--appendconfig={cfg}",
        f"--debugger={requested_port}",
        str(ISO),
    ]

    log("[Stage39K] Launching PPSSPP interpreter")
    proc = subprocess.Popen(cmd)
    cleanup = b.register_ppsspp_auto_close(proc)

    report = {
        "stage": "39K",
        "purpose":
            "Catch the actual visible narrow-byte renderer by breaking on the "
            "UV floats of glyph U+00EC (index 135), which the Stage39H GPU dump "
            "proved is the first visible sprite of the corrupted menu label.",
        "iso_patch": False,
        "runtime_patch": False,
        "stage39j_conclusion": {
            "unicode_measurement_path":
                "Correct: U+C2A4 -> 154, U+D1A0 -> 764, U+B9AC -> 384.",
            "lookup_return_for_first":
                "154, exactly matching the table.",
            "story_sequence":
                "The wide Unicode path sees U+C2A4, U+D1A0, U+B9AC correctly.",
            "why_that_does_not_explain_visible_output":
                "Stage39H GPU vertices contain no Korean atlas coordinates for "
                "the visible top item. They contain nine original-Latin/fallback "
                "sprites instead.",
        },
        "stage39h_gpu_proof": {
            "visible_top_sprite_count": 9,
            "first_sprite_uv": [[107, 0], [114, 16]],
            "first_sprite_original_glyph_index": 135,
            "first_sprite_original_codepoint": "U+00EC",
            "second_and_third_sprite_glyph": "fallback index 0",
            "fourth_sprite_uv": [[107, 16], [114, 32]],
            "fourth_sprite_original_glyph_index": 136,
            "fourth_sprite_original_codepoint": "U+00ED",
            "interpretation":
                "The visible menu draw is a separate narrow-byte path. "
                "EC 8A A4 ED ... is mapped byte-by-byte to the original font.",
        },
        "glyph_record_targets": {
            "glyph135_record": f"0x{REC_EC:08X}",
            "glyph135_uv": f"0x{UV_EC:08X}",
            "fallback_record": f"0x{REC_FALLBACK:08X}",
            "fallback_uv": f"0x{UV_FALLBACK:08X}",
            "glyph136_record": f"0x{REC_ED:08X}",
            "glyph136_uv": f"0x{UV_ED:08X}",
        },
    }

    try:
        hwnd = b.find_ppsspp_hwnd(60)
        if not hwnd:
            raise RuntimeError("PPSSPP window did not appear")

        actual_port = b.wait_for_actual_debugger_port(
            PPSSPP_LOG, 60
        )
        ws, host = b.connect_debugger(actual_port)

        try:
            report["debugger_host"] = host
            report["debugger_port"] = actual_port

            menu = wait_menu_open(ws, timeout=180.0)
            report["menu_resource_open"] = menu
            if not menu["opened"]:
                raise RuntimeError("MENUINT0.RAW did not open")

            resident = wait_correct_source_resident(
                ws, timeout=60.0
            )
            report["correct_source_resident"] = resident
            if not resident.get("ok", False):
                raise RuntimeError(
                    "Stage39F corrected Story source/metadata "
                    "did not become resident"
                )

            # The source is now fully decompressed.  Install the UV memcheck only
            # at this point, so generic asset loading cannot be mistaken for the
            # actual text renderer.
            add_read_memcheck(ws, UV_EC, "GLYPH135_UV")

            # One Start enters the selectable main menu. No further automatic
            # Start input is sent.
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

            paused = wait_pause(ws, timeout=120.0)

            if paused is None:
                remove_memcheck(ws, UV_EC)
                raise RuntimeError(
                    "Visible U+00EC glyph UV record was never read"
                )

            first = capture_hit(
                ws, paused, "GLYPH135_UV", REC_EC
            )
            first["hit"] = True
            report["visible_first_glyph_hit"] = first

            # The next UTF-8 byte (0x8A) is unsupported and Stage39H GPU proves
            # it uses fallback glyph index 0.  Catching its UV access should
            # hit the SAME renderer PC almost immediately.
            fallback = trace_next_record(
                ws,
                UV_EC,
                UV_FALLBACK,
                "FALLBACK_GLYPH0_UV",
                timeout=20.0,
            )
            report["visible_second_glyph_hit"] = fallback

            # The fourth UTF-8 byte is 0xED -> original glyph index 136.
            # Even if the fallback trace misses due another unrelated use, make
            # one direct attempt at index 136.
            old = UV_FALLBACK
            try:
                remove_memcheck(ws, old)
            except Exception:
                pass

            add_read_memcheck(ws, UV_ED, "GLYPH136_UV")
            resume(ws)
            p2 = wait_pause(ws, timeout=20.0)

            if p2 is not None:
                ed = capture_hit(
                    ws, p2, "GLYPH136_UV", REC_ED
                )
                ed["hit"] = True
            else:
                ed = {
                    "label": "GLYPH136_UV",
                    "hit": False,
                }

            remove_memcheck(ws, UV_ED)
            report["visible_fourth_glyph_hit"] = ed

            pc1 = first.get("pc")
            pc0 = fallback.get("pc")
            pced = ed.get("pc")

            report["renderer_pc_analysis"] = {
                "glyph135_pc": pc1,
                "fallback_pc": pc0,
                "glyph136_pc": pced,
                "same_pc_135_and_fallback":
                    bool(pc1 and pc0 and pc1 == pc0),
                "same_pc_135_and_136":
                    bool(pc1 and pced and pc1 == pced),
            }

            # Diagnostic completion is the exact UV read for glyph135.  It is
            # the first visible GPU sprite and therefore identifies the real
            # corrupted-label renderer independent of the hidden/wide path.
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

    with zipfile.ZipFile(
        target, "w", zipfile.ZIP_DEFLATED
    ) as z:
        for p in sorted(OUT.rglob("*")):
            if p.is_file():
                z.write(
                    p,
                    p.relative_to(OUT).as_posix(),
                )

    if not report["completed"]:
        raise RuntimeError(
            f"Stage39K failed. See {FAIL_ZIP}"
        )

    log("[Stage39K] COMPLETE")
    log(f"[Stage39K] Upload ZIP: {SUCCESS_ZIP}")


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
                            p,
                            p.relative_to(OUT).as_posix(),
                        )
        except Exception:
            pass

        print(traceback.format_exc(), flush=True)
        print(f"STAGE 39K FAILED: {FAIL_ZIP}", flush=True)
        raise SystemExit(1)
