#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import base64
import importlib.util
import json
import os
import subprocess
import sys
import time
import traceback
import zipfile
from pathlib import Path

ROOT = Path(r"PROJECT_ROOT")
BASE_TOOLS = ROOT / "bia_stage39b_tools"

ISO = ROOT / "BIA_STAGE39F_CORRECT_NARROW_METADATA_TEST.iso"

OUT = ROOT / "analysis" / "stage39i_render_path_trace"
LOG_DIR = ROOT / "log"

SUCCESS_ZIP = LOG_DIR / "bia_stage39i_upload.zip"
FAIL_ZIP = LOG_DIR / "fail_bia_stage39i_upload.zip"

REPORT_PATH = OUT / "stage39i_report.json"

# Correct Stage39F narrow display value and metadata.
DISPLAY1_ADDR = 0x093B1B40
DISPLAY1_SIZE = 10
META1_ADDR = 0x095EC774
META1_SIZE = 12

TEST_TEXT = "\uc2a4\ud1a0\ub9ac"
UTF8 = TEST_TEXT.encode("utf-8")
UTF16 = TEST_TEXT.encode("utf-16le")

# The proven BIA Unicode lookup used by the production TMR18 renderer.
UNICODE_LOOKUP = 0x08C7F2FC

# Visual Stage39H result strongly suggests the nine UTF-8 bytes are reaching
# the renderer as individual 0x00xx codepoints.  The first byte is 0xEC.
BAD_FIRST_CODEPOINT = 0x00EC
GOOD_FIRST_CODEPOINT = 0xC2A4

MENU_OPEN_MARKER = (
    "sceIoOpen(disc0:/PSP_GAME/USRDIR/SYSTEM/RAWFILES/MENUINT0.RAW"
)

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
        raise RuntimeError("Could not resolve Stage39B base helpers")

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
        vals = cat.get("uintValues", [])
        for n, v in zip(names, vals):
            out[n.lower()] = int(v) & 0xFFFFFFFF
    return out


def disasm(ws, addr, count=28):
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


def log_has_menu_open(path: Path):
    if not path.exists():
        return False
    try:
        txt = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return False
    return MENU_OPEN_MARKER in txt


def wait_menu_open(ws, log_path: Path, timeout=120.0):
    end = time.time() + timeout
    last_press = 0.0
    presses = 0

    while time.time() < end:
        if log_has_menu_open(log_path):
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
        time.sleep(0.04)
    return None


def tail_matching(path: Path, patterns, max_lines=80):
    if not path.exists():
        return []
    txt = path.read_text(encoding="utf-8", errors="replace")
    lines = txt.splitlines()
    hits = []
    for line in lines:
        if any(p.lower() in line.lower() for p in patterns):
            hits.append(line)
    return hits[-max_lines:]


def pointer_candidates(ws, regs):
    """
    Record registers that directly point at, or very near, the known narrow
    value / metadata / known dynamic UTF-16 copies.
    """
    regions = [
        ("narrow_display1", DISPLAY1_ADDR - 0x40, DISPLAY1_ADDR + 0x80),
        ("metadata1", META1_ADDR - 0x40, META1_ADDR + 0x80),
        ("dynamic_story_area", 0x08E41600, 0x08E43300),
    ]

    out = []
    for name, val in regs.items():
        if not isinstance(val, int):
            continue
        for role, lo, hi in regions:
            if lo <= val < hi:
                sample = None
                try:
                    sample = read_ws(ws, val, 32).hex()
                except Exception:
                    pass
                out.append({
                    "register": name,
                    "value": f"0x{val:08X}",
                    "role": role,
                    "memory_32": sample,
                })
    return out


def launch(b, log_path: Path, interpreter=False):
    exe = b.find_ppsspp_exe()

    cfg = OUT / (
        "stage39i_interpreter.ini"
        if interpreter else "stage39i_jit.ini"
    )
    cfg.write_text(
        "[Debugger]\n"
        "ShowDeveloperMenu = True\n"
        "\n"
        "[Graphics]\n"
        "ReplaceTextures = False\n"
        "SaveNewTextures = False\n",
        encoding="utf-8",
    )

    if log_path.exists():
        log_path.unlink()

    try:
        b.close_existing_ppsspp(timeout=3.0)
    except Exception:
        pass

    port_requested = b.choose_free_port()

    cmd = [
        str(exe),
    ]
    if interpreter:
        cmd.append("-i")
    cmd += [
        "-d",
        f"--log={log_path}",
        "--windowed",
        f"--appendconfig={cfg}",
        f"--debugger={port_requested}",
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
        "exe": str(exe),
        "proc": proc,
        "cleanup": cleanup,
        "hwnd": hwnd,
        "ws": ws,
        "host": host,
        "port": actual_port,
    }


def trace_source_read(b):
    """
    Trace the first actual consumer of the corrected narrow Story value AFTER
    MENUINT0.RAW is open.  Installing the read memcheck this late avoids the
    Stage39C false hit in the generic asset loader.
    """
    log_path = OUT / "stage39i_source_read_ppsspp.log"
    run = launch(b, log_path, interpreter=True)

    ws = run["ws"]
    result = {
        "mode": "MIPS interpreter",
        "log": str(log_path),
        "debugger_host": run["host"],
        "debugger_port": run["port"],
    }

    try:
        menu = wait_menu_open(ws, log_path, timeout=180.0)
        result["menu_resource_open"] = menu
        if not menu["opened"]:
            raise RuntimeError("MENUINT0.RAW did not open")

        # Confirm the on-disc UTF-8 value is resident before installing the
        # breakpoint.
        src = read_ws(ws, DISPLAY1_ADDR, 16)
        meta = read_ws(ws, META1_ADDR, 12)
        result["source_before_trace"] = src.hex()
        result["metadata_before_trace"] = meta.hex()

        # Read-only memcheck on the exact corrected display value.
        ws.request(
            "memory.breakpoint.add",
            timeout=10,
            address=DISPLAY1_ADDR,
            size=DISPLAY1_SIZE,
            enabled=True,
            log=True,
            read=True,
            write=False,
            change=False,
            logFormat=(
                "BIA39I_SOURCE_READ "
                "pc={pc} ra={ra} "
                "a0={a0} a1={a1} a2={a2} a3={a3} "
                "s0={s0} s1={s1} s2={s2} s3={s3} "
                "t0={t0} t1={t1} t2={t2} t3={t3}"
            ),
        )

        # Enter the selectable main menu.  Do not send any further Start.
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

        paused = wait_pause(ws, timeout=90.0)
        result["paused"] = paused

        if paused is None:
            result["hit"] = False
            return result

        regs = regs_to_dict(
            ws.request("cpu.getAllRegs", timeout=10)
        )
        pc = regs.get("pc", int(paused.get("pc", 0)))
        ra = regs.get("ra", 0)

        result["hit"] = True
        result["pc"] = f"0x{pc:08X}"
        result["ra"] = f"0x{ra:08X}"
        result["registers"] = {
            k: f"0x{v:08X}" for k, v in regs.items()
            if isinstance(v, int)
        }
        result["pointer_candidates"] = pointer_candidates(ws, regs)
        result["instruction_window"] = disasm(
            ws, max(0, pc - 0x30), 32
        )
        result["caller_window"] = (
            disasm(ws, max(0, ra - 0x30), 32)
            if ra else None
        )

        result["matching_log_tail"] = tail_matching(
            log_path,
            ["BIA39I_SOURCE_READ", "CHK Read"],
        )

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


def trace_renderer_codepoint(b):
    """
    Trace the first bad rendered codepoint U+00EC at the proven Unicode lookup
    entry.  This directly tests the visual Stage39H interpretation:
    UTF-8 EC 8A A4 ... is being rendered byte-by-byte.
    """
    log_path = OUT / "stage39i_renderer_ppsspp.log"
    run = launch(b, log_path, interpreter=False)

    ws = run["ws"]
    result = {
        "mode": "normal JIT",
        "log": str(log_path),
        "debugger_host": run["host"],
        "debugger_port": run["port"],
        "breakpoint": f"0x{UNICODE_LOOKUP:08X}",
        "condition": f"a1 == 0x{BAD_FIRST_CODEPOINT:04X}",
    }

    try:
        menu = wait_menu_open(ws, log_path, timeout=120.0)
        result["menu_resource_open"] = menu
        if not menu["opened"]:
            raise RuntimeError("MENUINT0.RAW did not open")

        # Install before entering the selectable main menu so the first visual
        # render of the Korean label can be caught.
        ws.request(
            "cpu.breakpoint.add",
            timeout=10,
            address=UNICODE_LOOKUP,
            enabled=True,
            log=True,
            condition=f"a1 == 0x{BAD_FIRST_CODEPOINT:04X}",
            logFormat=(
                "BIA39I_BAD_CODEPOINT "
                "pc={pc} ra={ra} a0={a0} a1={a1} "
                "a2={a2} a3={a3} "
                "s0={s0} s1={s1} s2={s2} s3={s3}"
            ),
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

        paused = wait_pause(ws, timeout=45.0)
        result["paused"] = paused

        if paused is None:
            result["bad_codepoint_hit"] = False

            # Record whether the correct U+C2A4 would hit instead.
            try:
                ws.request(
                    "cpu.breakpoint.remove",
                    timeout=5,
                    address=UNICODE_LOOKUP,
                )
            except Exception:
                pass

            try:
                ws.request(
                    "cpu.breakpoint.add",
                    timeout=10,
                    address=UNICODE_LOOKUP,
                    enabled=True,
                    log=True,
                    condition=f"a1 == 0x{GOOD_FIRST_CODEPOINT:04X}",
                    logFormat=(
                        "BIA39I_GOOD_CODEPOINT "
                        "pc={pc} ra={ra} a0={a0} a1={a1}"
                    ),
                )
                paused2 = wait_pause(ws, timeout=20.0)
            except Exception:
                paused2 = None

            result["good_codepoint_hit"] = paused2 is not None
            if paused2 is not None:
                regs = regs_to_dict(
                    ws.request("cpu.getAllRegs", timeout=10)
                )
                result["good_hit_registers"] = {
                    k: f"0x{v:08X}" for k, v in regs.items()
                    if isinstance(v, int)
                }
            return result

        regs = regs_to_dict(
            ws.request("cpu.getAllRegs", timeout=10)
        )
        pc = regs.get("pc", int(paused.get("pc", 0)))
        ra = regs.get("ra", 0)

        result["bad_codepoint_hit"] = True
        result["a1"] = f"0x{regs.get('a1', 0):08X}"
        result["pc"] = f"0x{pc:08X}"
        result["ra"] = f"0x{ra:08X}"
        result["registers"] = {
            k: f"0x{v:08X}" for k, v in regs.items()
            if isinstance(v, int)
        }
        result["pointer_candidates"] = pointer_candidates(ws, regs)
        result["lookup_window"] = disasm(
            ws, UNICODE_LOOKUP, 28
        )
        result["caller_window"] = (
            disasm(ws, max(0, ra - 0x40), 40)
            if ra else None
        )
        result["matching_log_tail"] = tail_matching(
            log_path,
            ["BIA39I_BAD_CODEPOINT"],
        )

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


def make_zip(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
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
        raise RuntimeError(f"Missing Stage39F ISO: {ISO}")

    _, b = load_helpers()

    report = {
        "stage": "39I",
        "purpose":
            "Trace the actual consumer/render path for the visually corrupted "
            "Korean main-menu label after Stage39H.",
        "stage39h_visual_result": {
            "automatic_structural_checks": "PASS",
            "visual_korean_render": "FAIL",
            "observed":
                "Top menu item renders as Latin-1/control-like glyphs and boxes, "
                "consistent with the 9 UTF-8 bytes being treated as individual "
                "single-byte/low-16-bit characters instead of 3 Hangul codepoints.",
            "expected_visible_text": TEST_TEXT,
            "utf8_bytes": UTF8.hex(),
            "correct_utf16": UTF16.hex(),
        },
        "runtime_patch": False,
        "iso_patch": False,
        "uses_old_fixed_story_slot": False,
    }

    try:
        log("[Stage39I] Pass A: tracing corrected narrow source read")
        report["source_read_trace"] = trace_source_read(b)
    except Exception as e:
        report["source_read_trace_error"] = str(e)
        report["source_read_traceback"] = traceback.format_exc()

    try:
        log("[Stage39I] Pass B: tracing bad renderer codepoint U+00EC")
        report["renderer_trace"] = trace_renderer_codepoint(b)
    except Exception as e:
        report["renderer_trace_error"] = str(e)
        report["renderer_traceback"] = traceback.format_exc()

    source_hit = bool(
        report.get("source_read_trace", {}).get("hit", False)
    )
    bad_hit = bool(
        report.get("renderer_trace", {}).get(
            "bad_codepoint_hit", False
        )
    )
    good_hit = bool(
        report.get("renderer_trace", {}).get(
            "good_codepoint_hit", False
        )
    )

    report["completed"] = source_hit or bad_hit or good_hit

    REPORT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    if report["completed"]:
        make_zip(SUCCESS_ZIP)
        log("[Stage39I] COMPLETE")
        log(f"[Stage39I] Upload ZIP: {SUCCESS_ZIP}")
        return

    make_zip(FAIL_ZIP)
    raise RuntimeError(
        f"Stage39I captured neither source consumer nor renderer codepoint. "
        f"See {FAIL_ZIP}"
    )


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
        print(f"STAGE 39I FAILED: {FAIL_ZIP}", flush=True)
        raise SystemExit(1)
