#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import base64
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
BASE_TOOLS = ROOT / "bia_stage39b_tools"
ISO = ROOT / "BIA_STAGE39F_CORRECT_NARROW_METADATA_TEST.iso"

OUT = ROOT / "analysis" / "stage39l_dual_renderer_trace"
LOG_DIR = ROOT / "log"

SUCCESS_ZIP = LOG_DIR / "bia_stage39l_upload.zip"
FAIL_ZIP = LOG_DIR / "fail_bia_stage39l_upload.zip"
REPORT_PATH = OUT / "stage39l_report.json"

# Proven Unicode lookup and actual wide renderer from Stage39J/static BIAON.
UNICODE_LOOKUP = 0x08C7F2FC
WIDE_LOOKUP_RETURN = 0x08972368       # BIAON + 0x16E368
WIDE_RECORD_U0 = 0x0897237C           # lwc1 f12,8(a0)
WIDE_RENDER_RECORD = 0x08972500        # lwc1 f16,8(a0), after page select

CP_S = 0xC2A4
CP_TO = 0xD1A0
CP_RI = 0xB9AC

# Production and original glyph arrays.
NEW_GLYPH_PTR = 0x098F5020
OLD_GLYPH_PTR = 0x09723FD8
GLYPH_REC_SIZE = 24

# Visible Stage39H first sprite = original U+00EC glyph index 135.
LATIN_EC_INDEX = 135
LATIN_ED_INDEX = 136

NEW_EC_REC = NEW_GLYPH_PTR + LATIN_EC_INDEX * GLYPH_REC_SIZE
OLD_EC_REC = OLD_GLYPH_PTR + LATIN_EC_INDEX * GLYPH_REC_SIZE
OLD_ED_REC = OLD_GLYPH_PTR + LATIN_ED_INDEX * GLYPH_REC_SIZE

NEW_EC_UV = NEW_EC_REC + 8
OLD_EC_UV = OLD_EC_REC + 8
OLD_ED_UV = OLD_ED_REC + 8

PROD_S_REC = NEW_GLYPH_PTR + 154 * GLYPH_REC_SIZE

# Correct Stage39F source state.
DISPLAY1_ADDR = 0x093B1B40
DISPLAY2_ADDR = 0x093B1BF0
META1_ADDR = 0x095EC774
META2_ADDR = 0x095F1758
UTF8 = "스토리".encode("utf-8")
UTF8_NUL = UTF8 + b"\x00"
EXPECTED_META1 = (DISPLAY1_ADDR, 10, 10)
EXPECTED_META2 = (DISPLAY2_ADDR, 10, 10)

MENU_OPEN_MARKER = (
    "sceIoOpen(disc0:/PSP_GAME/USRDIR/SYSTEM/RAWFILES/MENUINT0.RAW"
)

# Generic MDI decompressor false-positive region observed in Stage39K.
DECOMPRESSOR_PC_LO = 0x0881BC00
DECOMPRESSOR_PC_HI = 0x0881C400

# Font object layout.
FONT_GLYPH_COUNT = 0x50
FONT_GLYPH_PTR = 0x54
FONT_PAGE_TABLE = 0x58
FONT_WIDTHS = 0x474
FONT_HEIGHTS = 0x478
FONT_TEXTURES = 0x488

MEMCHECK_SIZE = 16
MAX_FALSE_HITS = 128

GPR_NAMES = [
    "zero","at","v0","v1","a0","a1","a2","a3",
    "t0","t1","t2","t3","t4","t5","t6","t7",
    "s0","s1","s2","s3","s4","s5","s6","s7",
    "t8","t9","k0","k1","gp","sp","fp","ra","pc",
]


def log(msg):
    print(msg, flush=True)


def load_helpers():
    p = BASE_TOOLS / "bia_stage39b_compiled_mdi_text.py"
    if not p.exists():
        raise RuntimeError(f"Missing Stage39B helper: {p}")
    sys.path.insert(0, str(BASE_TOOLS))
    spec = importlib.util.spec_from_file_location("bia_stage39b_local", p)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    b = getattr(mod, "b", None)
    if b is None and hasattr(mod, "s39"):
        b = getattr(mod.s39, "b", None)
    if b is None:
        raise RuntimeError("Could not resolve helper module")
    return mod, b


def read_ws(ws, addr, size):
    r = ws.request(
        "memory.read", timeout=10, address=addr, size=size
    )
    return base64.b64decode(r["base64"])


def u16(ws, addr):
    return struct.unpack("<H", read_ws(ws, addr, 2))[0]


def u32(ws, addr):
    return struct.unpack("<I", read_ws(ws, addr, 4))[0]


def regs_to_dict(resp):
    out = {}
    for cat in resp.get("categories", []):
        for n, v in zip(
            cat.get("registerNames", []),
            cat.get("uintValues", []),
        ):
            out[n.lower()] = int(v) & 0xFFFFFFFF
    return out


def disasm(ws, addr, count=48):
    try:
        return ws.request(
            "memory.disasm",
            timeout=10,
            address=addr & 0xFFFFFFFF,
            count=count,
            displaySymbols=True,
            compact=False,
        )
    except Exception as e:
        return {"error": str(e)}


def resume(ws):
    try:
        ws.request("cpu.resume", timeout=1)
    except Exception:
        pass


def remove_cpu_bp(ws, addr):
    try:
        ws.request("cpu.breakpoint.remove", timeout=5, address=addr)
    except Exception:
        pass


def wait_pause(ws, timeout=60.0):
    end = time.time() + timeout
    last = None
    while time.time() < end:
        try:
            last = ws.request("cpu.status", timeout=3)
            if last.get("stepping", False):
                return last
        except Exception:
            pass
        time.sleep(0.03)
    return None


def wait_menu_open(ws, log_path, timeout=180.0):
    end = time.time() + timeout
    last_press = 0.0
    presses = 0

    while time.time() < end:
        if log_path.exists():
            txt = log_path.read_text(
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
        time.sleep(0.1)

    return {"opened": False, "start_presses": presses}


def wait_source(ws, timeout=60.0):
    end = time.time() + timeout
    last = {}
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
        time.sleep(0.12)
    last["ok"] = False
    return last


def launch(b, log_path, interpreter=False):
    exe = b.find_ppsspp_exe()
    cfg = OUT / (
        "stage39l_interpreter.ini"
        if interpreter else "stage39l_jit.ini"
    )
    cfg.write_text(
        "[Debugger]\nShowDeveloperMenu = True\n\n"
        "[Graphics]\nReplaceTextures = False\nSaveNewTextures = False\n",
        encoding="utf-8",
    )

    if log_path.exists():
        log_path.unlink()

    try:
        b.close_existing_ppsspp(timeout=3.0)
    except Exception:
        pass

    port = b.choose_free_port()
    cmd = [str(exe)]
    if interpreter:
        cmd.append("-i")
    cmd += [
        "-d",
        f"--log={log_path}",
        "--windowed",
        f"--appendconfig={cfg}",
        f"--debugger={port}",
        str(ISO),
    ]

    proc = subprocess.Popen(cmd)
    cleanup = b.register_ppsspp_auto_close(proc)
    hwnd = b.find_ppsspp_hwnd(60 if interpreter else 30)
    if not hwnd:
        cleanup()
        raise RuntimeError("PPSSPP window did not appear")

    actual_port = b.wait_for_actual_debugger_port(
        log_path, 60 if interpreter else 30
    )
    ws, host = b.connect_debugger(actual_port)

    return {
        "proc": proc,
        "cleanup": cleanup,
        "hwnd": hwnd,
        "ws": ws,
        "host": host,
        "port": actual_port,
        "exe": str(exe),
    }


def font_object_snapshot(ws, font):
    out = {
        "address": f"0x{font:08X}",
        "glyph_count": u16(ws, font + FONT_GLYPH_COUNT),
        "glyph_ptr": f"0x{u32(ws, font + FONT_GLYPH_PTR):08X}",
        "page_table": f"0x{font + FONT_PAGE_TABLE:08X}",
    }

    wp = u32(ws, font + FONT_WIDTHS)
    hp = u32(ws, font + FONT_HEIGHTS)
    tp = u32(ws, font + FONT_TEXTURES)

    out["widths_ptr"] = f"0x{wp:08X}"
    out["heights_ptr"] = f"0x{hp:08X}"
    out["textures_ptr"] = f"0x{tp:08X}"

    out["widths"] = list(struct.unpack("<4H", read_ws(ws, wp, 8)))
    out["heights"] = list(struct.unpack("<4H", read_ws(ws, hp, 8)))
    out["textures"] = [
        f"0x{x:08X}"
        for x in struct.unpack("<4I", read_ws(ws, tp, 16))
    ]
    return out


def pass_wide_renderer(b):
    """
    Target the *actual* Stage39J renderer call, identified by:
      Unicode lookup RA = 0x08972368.

    This resolves the critical register Stage39J did not capture: s2 is the
    font object used by the renderer at BIAON+0x16E360.
    """
    log_path = OUT / "stage39l_wide_renderer.log"
    run = launch(b, log_path, interpreter=False)
    ws = run["ws"]

    result = {
        "mode": "normal JIT",
        "debugger_host": run["host"],
        "debugger_port": run["port"],
        "target_lookup_ra": f"0x{WIDE_LOOKUP_RETURN:08X}",
    }

    try:
        menu = wait_menu_open(ws, log_path, timeout=120.0)
        result["menu_resource_open"] = menu
        if not menu["opened"]:
            raise RuntimeError("MENUINT0.RAW did not open")

        source = wait_source(ws)
        result["source_resident"] = source
        if not source.get("ok"):
            raise RuntimeError("Correct source did not become resident")

        # Install only the U+C2A4 condition.  If a hidden/measurement path hits
        # first, resume until the RA is the known actual renderer.
        ws.request(
            "cpu.breakpoint.add",
            timeout=10,
            address=UNICODE_LOOKUP,
            enabled=True,
            log=False,
            condition=f"a1 == 0x{CP_S:04X}",
        )

        try:
            ws.request(
                "input.buttons.press",
                timeout=5,
                button="start",
                duration=2,
            )
            result["main_menu_start_sent"] = True
        except Exception as e:
            result["main_menu_start_error"] = str(e)

        target_regs = None
        hits = []

        for _ in range(12):
            p = wait_pause(ws, timeout=15.0)
            if p is None:
                break

            regs = regs_to_dict(
                ws.request("cpu.getAllRegs", timeout=10)
            )
            hit = {
                "pc": f"0x{regs.get('pc',0):08X}",
                "ra": f"0x{regs.get('ra',0):08X}",
                "a0": f"0x{regs.get('a0',0):08X}",
                "a1": f"0x{regs.get('a1',0):08X}",
                "s0": f"0x{regs.get('s0',0):08X}",
                "s2": f"0x{regs.get('s2',0):08X}",
            }
            hits.append(hit)

            if regs.get("ra") == WIDE_LOOKUP_RETURN:
                target_regs = regs
                break
            resume(ws)

        result["lookup_hits"] = hits

        if target_regs is None:
            raise RuntimeError(
                "Did not observe U+C2A4 with RA 0x08972368"
            )

        s0 = target_regs["s0"]
        s2 = target_regs["s2"]

        result["actual_renderer_lookup"] = {
            "string_ptr_s0": f"0x{s0:08X}",
            "string_utf16_16": read_ws(ws, s0, 16).hex(),
            "font_object_s2": f"0x{s2:08X}",
            "font": font_object_snapshot(ws, s2),
            "lookup_page_table_a0":
                f"0x{target_regs.get('a0',0):08X}",
            "caller_disasm":
                disasm(ws, WIDE_LOOKUP_RETURN - 8, 44),
        }

        # Now break on the static renderer's first glyph-record U0 access.
        remove_cpu_bp(ws, UNICODE_LOOKUP)
        ws.request(
            "cpu.breakpoint.add",
            timeout=10,
            address=WIDE_RECORD_U0,
            enabled=True,
            log=False,
        )
        resume(ws)
        p2 = wait_pause(ws, timeout=8.0)

        if p2 is not None:
            r2 = regs_to_dict(
                ws.request("cpu.getAllRegs", timeout=10)
            )
            result["record_u0_hit"] = {
                "pc": f"0x{r2.get('pc',0):08X}",
                "a0_record": f"0x{r2.get('a0',0):08X}",
                "expected_prod_s_record":
                    f"0x{PROD_S_REC:08X}",
                "record_hex":
                    read_ws(ws, r2.get("a0", 0), 24).hex()
                    if 0x08800000 <= r2.get("a0",0) < 0x0A800000
                    else None,
                "s0_string": f"0x{r2.get('s0',0):08X}",
                "s2_font": f"0x{r2.get('s2',0):08X}",
            }
        else:
            result["record_u0_hit"] = {"hit": False}

        remove_cpu_bp(ws, WIDE_RECORD_U0)

        # A second static point where the renderer has already derived the page
        # selector and is scaling U/V using page widths/heights.
        ws.request(
            "cpu.breakpoint.add",
            timeout=10,
            address=WIDE_RENDER_RECORD,
            enabled=True,
            log=False,
        )
        resume(ws)
        p3 = wait_pause(ws, timeout=8.0)

        if p3 is not None:
            r3 = regs_to_dict(
                ws.request("cpu.getAllRegs", timeout=10)
            )
            result["render_record_hit"] = {
                "pc": f"0x{r3.get('pc',0):08X}",
                "a0_record": f"0x{r3.get('a0',0):08X}",
                "a1": f"0x{r3.get('a1',0):08X}",
                "a2": f"0x{r3.get('a2',0):08X}",
                "s0_string": f"0x{r3.get('s0',0):08X}",
                "s2_font": f"0x{r3.get('s2',0):08X}",
                "disasm":
                    disasm(ws, WIDE_RENDER_RECORD - 24, 32),
            }
        else:
            result["render_record_hit"] = {"hit": False}

        remove_cpu_bp(ws, WIDE_RENDER_RECORD)
        result["completed"] = True
        return result

    finally:
        try:
            ws.close()
        except Exception:
            pass
        try:
            run["cleanup"]()
            result["ppsspp_closed"] = True
        except Exception as e:
            result["ppsspp_close_error"] = str(e)


def add_memcheck(ws, addr, label):
    ws.request(
        "memory.breakpoint.add",
        timeout=10,
        address=addr,
        size=MEMCHECK_SIZE,
        enabled=True,
        log=True,
        read=True,
        write=False,
        change=False,
        logFormat=(
            f"BIA39L_{label} "
            "pc={{pc}} ra={{ra}} "
            "a0={{a0}} a1={{a1}} a2={{a2}} a3={{a3}} "
            "s0={{s0}} s1={{s1}} s2={{s2}} s3={{s3}}"
        ),
    )


def remove_memcheck(ws, addr):
    try:
        ws.request(
            "memory.breakpoint.remove",
            timeout=5,
            address=addr,
            size=MEMCHECK_SIZE,
        )
    except Exception:
        pass


def step_over_memcheck(ws, addr):
    """
    Interpreter memcheck pauses before the read. Remove it, single-step the
    instruction, re-add later.
    """
    remove_memcheck(ws, addr)
    try:
        ws.request("cpu.stepInto", timeout=0.5)
    except Exception:
        pass

    end = time.time() + 4
    while time.time() < end:
        try:
            st = ws.request("cpu.status", timeout=2)
            if st.get("stepping", False):
                return st
        except Exception:
            pass
        time.sleep(0.01)
    return None


def classify_pc(ws, pc):
    d = disasm(ws, pc, 1)
    lines = d.get("lines", [])
    if lines:
        return lines[0].get("function")
    return None


def ptr_samples(ws, regs):
    out = []
    for n in GPR_NAMES:
        if n not in regs:
            continue
        v = regs[n]
        if not (0x08800000 <= v < 0x0A800000):
            continue
        base = max(0x08800000, v - 48)
        try:
            raw = read_ws(ws, base, 128)
        except Exception:
            continue
        p = raw.find(UTF8)
        out.append({
            "register": n,
            "value": f"0x{v:08X}",
            "sample_base": f"0x{base:08X}",
            "utf8_story_address":
                None if p < 0 else f"0x{base+p:08X}",
            "sample_hex": raw.hex(),
        })
    return out


def trace_uv_after_menu(ws, addr, label, timeout=90.0):
    """
    Install the memcheck only after the menu has already been on screen for
    several seconds. Skip any remaining openseason_data_decode hit and keep
    waiting for a non-decompressor consumer.
    """
    add_memcheck(ws, addr, label)

    false_hits = []
    end = time.time() + timeout

    while time.time() < end and len(false_hits) < MAX_FALSE_HITS:
        resume(ws)
        p = wait_pause(ws, timeout=min(8.0, max(0.1, end-time.time())))
        if p is None:
            continue

        regs = regs_to_dict(
            ws.request("cpu.getAllRegs", timeout=10)
        )
        pc = regs.get("pc", int(p.get("pc", 0)))
        ra = regs.get("ra", 0)
        fn = classify_pc(ws, pc)

        is_loader = (
            DECOMPRESSOR_PC_LO <= pc < DECOMPRESSOR_PC_HI
            or fn == "openseason_data_decode"
        )

        if is_loader:
            false_hits.append({
                "pc": f"0x{pc:08X}",
                "ra": f"0x{ra:08X}",
                "function": fn,
            })
            step_over_memcheck(ws, addr)
            add_memcheck(ws, addr, label)
            continue

        hit = {
            "hit": True,
            "pc": f"0x{pc:08X}",
            "ra": f"0x{ra:08X}",
            "function": fn,
            "registers": {
                k: f"0x{v:08X}"
                for k, v in regs.items()
                if isinstance(v, int)
            },
            "pointer_samples": ptr_samples(ws, regs),
            "instruction_window":
                disasm(ws, max(0, pc-0x60), 56),
            "caller_window":
                disasm(ws, max(0, ra-0x40), 40)
                if ra else None,
            "skipped_loader_hits": false_hits,
        }
        remove_memcheck(ws, addr)
        return hit

    remove_memcheck(ws, addr)
    return {
        "hit": False,
        "skipped_loader_hits": false_hits,
    }


def pass_old_array(b):
    """
    Test the key Stage39K follow-up hypothesis:

    the visible legacy/narrow menu renderer may still use the ORIGINAL glyph
    array at 0x09723FD8, while the wide renderer uses the relocated production
    array at 0x098F5020.

    Stage39K watched the NEW array and only saw the MDI loader.
    """
    log_path = OUT / "stage39l_old_array.log"
    run = launch(b, log_path, interpreter=True)
    ws = run["ws"]

    result = {
        "mode": "MIPS interpreter",
        "debugger_host": run["host"],
        "debugger_port": run["port"],
        "old_glyph_ptr": f"0x{OLD_GLYPH_PTR:08X}",
        "new_glyph_ptr": f"0x{NEW_GLYPH_PTR:08X}",
    }

    try:
        menu = wait_menu_open(ws, log_path, timeout=180.0)
        result["menu_resource_open"] = menu
        if not menu["opened"]:
            raise RuntimeError("MENUINT0.RAW did not open")

        source = wait_source(ws)
        result["source_resident"] = source
        if not source.get("ok"):
            raise RuntimeError("Correct source did not become resident")

        # Enter the menu first with NO memcheck.  The UI redraws continuously,
        # so we can safely install the watch after decompression/loading settles.
        try:
            ws.request(
                "input.buttons.press",
                timeout=5,
                button="start",
                duration=2,
            )
            result["main_menu_start_sent"] = True
        except Exception as e:
            result["main_menu_start_error"] = str(e)

        time.sleep(8.0)

        result["old_ec_uv_trace"] = trace_uv_after_menu(
            ws, OLD_EC_REC + 8, "OLD_GLYPH135_UV", timeout=90.0
        )

        # If the old EC path is real, the next UTF-8 chunk ED should normally
        # traverse the same renderer. Trace independently.
        result["old_ed_uv_trace"] = trace_uv_after_menu(
            ws, OLD_ED_REC + 8, "OLD_GLYPH136_UV", timeout=45.0
        )

        # Control: watch the relocated copy after the menu is already stable.
        # This distinguishes "old array visible path" from a generic loader hit.
        result["new_ec_uv_control"] = trace_uv_after_menu(
            ws, NEW_EC_REC + 8, "NEW_GLYPH135_UV", timeout=30.0
        )

        old1 = result["old_ec_uv_trace"]
        old2 = result["old_ed_uv_trace"]
        new1 = result["new_ec_uv_control"]

        result["analysis"] = {
            "old_array_renderer_hit":
                bool(old1.get("hit")),
            "old_ec_ed_same_pc":
                bool(
                    old1.get("hit")
                    and old2.get("hit")
                    and old1.get("pc") == old2.get("pc")
                ),
            "new_array_renderer_hit":
                bool(new1.get("hit")),
            "old_pointer_hypothesis_supported":
                bool(
                    old1.get("hit")
                    and not new1.get("hit")
                ),
        }

        result["completed"] = True
        return result

    finally:
        try:
            ws.close()
        except Exception:
            pass
        try:
            run["cleanup"]()
            result["ppsspp_closed"] = True
        except Exception as e:
            result["ppsspp_close_error"] = str(e)


def make_zip(path):
    if path.exists():
        path.unlink()
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(OUT.rglob("*")):
            if p.is_file():
                z.write(p, p.relative_to(OUT).as_posix())


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    for p in OUT.iterdir():
        if p.is_file():
            p.unlink()

    if not ISO.exists():
        raise RuntimeError(f"Missing ISO: {ISO}")

    _, b = load_helpers()

    report = {
        "stage": "39L",
        "purpose":
            "Resolve which font object/glyph array the actual wide renderer "
            "uses, and test whether the visibly corrupted legacy path still "
            "reads the original pre-relocation glyph array.",
        "stage39k_result":
            "The UV memcheck on the relocated glyph135 record hit only "
            "openseason_data_decode at 0x0881BF54. This is another loader "
            "false-positive and does NOT identify the visible renderer.",
        "new_static_fact":
            "Stage39J's RA 0x08972368 is BIAON+0x16E368, immediately after "
            "the actual wide renderer calls the proven Unicode lookup. "
            "In this function s2 is the font object and s0 is the UTF-16 cursor.",
        "old_glyph_array_hypothesis": {
            "old_ptr": f"0x{OLD_GLYPH_PTR:08X}",
            "new_ptr": f"0x{NEW_GLYPH_PTR:08X}",
            "reason":
                "The visible narrow renderer may retain the original glyph "
                "array pointer even though the production/wide font object "
                "was redirected to the relocated 847-record array.",
        },
        "iso_patch": False,
        "runtime_patch": False,
    }

    try:
        log("[Stage39L] Pass A - actual wide renderer font object")
        report["wide_renderer"] = pass_wide_renderer(b)
    except Exception as e:
        report["wide_renderer_error"] = str(e)
        report["wide_renderer_traceback"] = traceback.format_exc()

    try:
        log("[Stage39L] Pass B - old-vs-new glyph array visible path")
        report["old_array_trace"] = pass_old_array(b)
    except Exception as e:
        report["old_array_trace_error"] = str(e)
        report["old_array_traceback"] = traceback.format_exc()

    wide_ok = bool(
        report.get("wide_renderer", {}).get("completed")
    )
    old_ok = bool(
        report.get("old_array_trace", {}).get("completed")
    )
    report["completed"] = wide_ok or old_ok

    REPORT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    target = SUCCESS_ZIP if report["completed"] else FAIL_ZIP
    make_zip(target)

    if not report["completed"]:
        raise RuntimeError(f"Stage39L failed. See {FAIL_ZIP}")

    log("[Stage39L] COMPLETE")
    log(f"[Stage39L] Upload ZIP: {SUCCESS_ZIP}")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        OUT.mkdir(parents=True, exist_ok=True)
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        (OUT / "FAILURE.txt").write_text(
            traceback.format_exc(), encoding="utf-8"
        )
        try:
            make_zip(FAIL_ZIP)
        except Exception:
            pass
        print(traceback.format_exc(), flush=True)
        print(f"STAGE 39L FAILED: {FAIL_ZIP}", flush=True)
        raise SystemExit(1)
