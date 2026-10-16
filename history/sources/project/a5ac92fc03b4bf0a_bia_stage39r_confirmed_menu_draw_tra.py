#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import base64
import importlib.util
import json
import math
import struct
import subprocess
import sys
import time
import traceback
import zipfile
from collections import Counter
from pathlib import Path

ROOT = Path(r"PROJECT_ROOT")
BASE_TOOLS = ROOT / "bia_stage39b_tools"
ISO = ROOT / "BIA_STAGE39F_CORRECT_NARROW_METADATA_TEST.iso"

OUT = ROOT / "analysis" / "stage39r_confirmed_menu_draw_trace"
LOG_DIR = ROOT / "log"

SUCCESS_ZIP = LOG_DIR / "bia_stage39r_upload.zip"
FAIL_ZIP = LOG_DIR / "fail_bia_stage39r_upload.zip"
REPORT_PATH = OUT / "stage39r_report.json"
PPSSPP_LOG = OUT / "stage39r_ppsspp.log"

# Common textured-quad helper proven by static BIAON analysis.
DRAW_HELPER = 0x08AF6324

KNOWN_CALLERS = {
    0x089726C0: "wide_unicode_text_renderer +0x16E6C0",
    0x0897441C: "callsite +0x17041C",
    0x089F5704: "callsite +0x1F1704",
    0x089FA134: "callsite +0x1F6134",
    0x08AE908C: "callsite +0x2E508C",
    0x08AF7D70: "callsite +0x2F3D70",
    0x08B7BDE8: "callsite +0x377DE8",
    0x08BD5B54: "callsite +0x3D1B54",
}

# Stage39H GPU proof: visible corrupted first menu sprite.
GPU_FIRST_UV = (107, 0, 114, 16)
GPU_FIRST_XY = (169, 68, 175, 85)
GPU_FALLBACK_UV = (75, 200, 87, 215)
GPU_FOURTH_UV = (107, 16, 114, 32)

# Correct Stage39F narrow source.
DISPLAY1_ADDR = 0x093B1B40
DISPLAY2_ADDR = 0x093B1BF0
META1_ADDR = 0x095EC774
META2_ADDR = 0x095F1758

UTF8 = "스토리".encode("utf-8")
UTF8_NUL = UTF8 + b"\x00"
UTF16_STORY = "스토리".encode("utf-16le")
UTF16_OPTIONS = "Options".encode("utf-16le")
UTF16_PROFILE = "Profile".encode("utf-16le")

EXPECTED_META1 = (DISPLAY1_ADDR, 10, 10)
EXPECTED_META2 = (DISPLAY2_ADDR, 10, 10)

# Stage39H proved these become the actual main-menu dynamic strings only after
# the title screen has been entered and the selectable menu has initialized.
MAINMENU_OPTIONS_ADDR = 0x08E41660
MAINMENU_PROFILE_ADDR = 0x08E41680
MAINMENU_STORY_ADDR = 0x08E416C0

MENU_OPEN_MARKER = (
    "sceIoOpen(disc0:/PSP_GAME/USRDIR/SYSTEM/RAWFILES/MENUINT0.RAW"
)

RAM_START = 0x08800000
RAM_END = 0x0A800000

# Stage39H waited 2 seconds after MENUINT0 opened before pressing Start.
# Stage39Q skipped this wait and its saved "settled menu" screenshot was still
# the title screen. Restore and strengthen the proven timing.
TITLE_SETTLE_SECONDS = 2.5
MAINMENU_WAIT_SECONDS = 14.0
RETRY_START_AFTER = 8.0

MAX_HITS = 2200
TRACE_SECONDS = 95.0
XY_NEAR_TOL = 3

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
        raise RuntimeError(f"Missing helper: {p}")

    sys.path.insert(0, str(BASE_TOOLS))
    spec = importlib.util.spec_from_file_location(
        "bia_stage39b_local", p
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


def find_callable(objects, name):
    for obj in objects:
        if obj is not None and hasattr(obj, name):
            fn = getattr(obj, name)
            if callable(fn):
                return fn
    return None


def read_ws(ws, address, size):
    r = ws.request(
        "memory.read",
        timeout=10,
        address=address,
        size=size,
    )
    return base64.b64decode(r["base64"])


def disasm(ws, address, count=96):
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


def parse_regs(resp):
    uints = {}
    floats = {}

    for cat in resp.get("categories", []):
        names = cat.get("registerNames", [])
        uvals = cat.get("uintValues", [])
        fvals = cat.get("floatValues", [])

        for i, name in enumerate(names):
            n = name.lower()
            if i < len(uvals):
                uints[n] = int(uvals[i]) & 0xFFFFFFFF
            if i < len(fvals):
                try:
                    floats[n] = float(fvals[i])
                except Exception:
                    pass

    return uints, floats


def tuple_f(floats, names):
    vals = []
    for n in names:
        v = floats.get(n)
        if v is None or not math.isfinite(v):
            return None
        vals.append(float(v))
    return tuple(vals)


def quantize_floor(vals):
    if vals is None:
        return None
    return tuple(
        int(math.floor(v + 1.0e-5))
        for v in vals
    )


def resume(ws):
    try:
        ws.request("cpu.resume", timeout=0.5)
    except Exception:
        pass


def wait_pause(ws, timeout=6.0):
    end = time.time() + timeout
    last = None
    while time.time() < end:
        try:
            last = ws.request("cpu.status", timeout=2)
            if last.get("stepping", False):
                return last
        except Exception:
            pass
        time.sleep(0.018)
    return None


def remove_bp(ws):
    try:
        ws.request(
            "cpu.breakpoint.remove",
            timeout=5,
            address=DRAW_HELPER,
        )
    except Exception:
        pass


def add_bp(ws):
    remove_bp(ws)
    return ws.request(
        "cpu.breakpoint.add",
        timeout=10,
        address=DRAW_HELPER,
        enabled=True,
        log=False,
    )


def wait_menu_resource(ws, timeout=180.0):
    """
    During startup only, use Start to skip logo/legal content until the actual
    MENUINT0.RAW open is observed. After this function returns, no more
    repeated startup input is sent.
    """
    end = time.time() + timeout
    last_press = 0.0
    presses = 0

    while time.time() < end:
        if PPSSPP_LOG.exists():
            txt = PPSSPP_LOG.read_text(
                encoding="utf-8",
                errors="replace",
            )
            if MENU_OPEN_MARKER in txt:
                return {
                    "opened": True,
                    "start_presses": presses,
                }

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

    return {
        "opened": False,
        "start_presses": presses,
    }


def wait_source(ws, timeout=60.0):
    end = time.time() + timeout
    last = {}

    while time.time() < end:
        try:
            d1 = read_ws(ws, DISPLAY1_ADDR, 16)
            d2 = read_ws(ws, DISPLAY2_ADDR, 16)
            m1 = struct.unpack(
                "<III", read_ws(ws, META1_ADDR, 12)
            )
            m2 = struct.unpack(
                "<III", read_ws(ws, META2_ADDR, 12)
            )

            last = {
                "display1": d1.hex(),
                "display2": d2.hex(),
                "meta1": [
                    f"0x{m1[0]:08X}", m1[1], m1[2]
                ],
                "meta2": [
                    f"0x{m2[0]:08X}", m2[1], m2[2]
                ],
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

        time.sleep(0.1)

    last["ok"] = False
    return last


def mainmenu_anchors(ws):
    """
    Exact runtime state used by Stage39H:
      0x08E41660 = UTF-16 "Options"
      0x08E41680 = UTF-16 "Profile"
      0x08E416C0 = UTF-16 "스토리"

    Requiring all three prevents title-screen false positives.
    """
    try:
        opt = read_ws(
            ws,
            MAINMENU_OPTIONS_ADDR,
            len(UTF16_OPTIONS) + 2,
        )
        pro = read_ws(
            ws,
            MAINMENU_PROFILE_ADDR,
            len(UTF16_PROFILE) + 2,
        )
        sto = read_ws(
            ws,
            MAINMENU_STORY_ADDR,
            len(UTF16_STORY) + 2,
        )
    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
        }

    return {
        "ok": (
            opt.startswith(UTF16_OPTIONS + b"\x00\x00")
            and pro.startswith(UTF16_PROFILE + b"\x00\x00")
            and sto.startswith(UTF16_STORY + b"\x00\x00")
        ),
        "options_hex": opt.hex(),
        "profile_hex": pro.hex(),
        "story_hex": sto.hex(),
    }


def wait_confirmed_mainmenu(ws):
    """
    Press Start only from the title state.

    First attempt follows the timing that succeeded in Stage39H.
    If no anchors appear after 8 seconds, check anchors again immediately
    before a single retry Start. Because the anchors are still absent, this
    retry cannot accidentally select Story from an already-visible main menu.
    """
    attempts = []

    for attempt in (1, 2):
        before = mainmenu_anchors(ws)
        if before.get("ok"):
            return {
                "confirmed": True,
                "attempts": attempts,
                "anchors": before,
                "start_presses_here": attempt - 1,
            }

        try:
            ws.request(
                "input.buttons.press",
                timeout=5,
                button="start",
                duration=2,
            )
            sent = True
        except Exception as e:
            sent = False
            err = str(e)

        start_time = time.time()
        last = None

        while time.time() - start_time < MAINMENU_WAIT_SECONDS:
            last = mainmenu_anchors(ws)
            if last.get("ok"):
                attempts.append({
                    "attempt": attempt,
                    "sent": sent,
                    "elapsed":
                        time.time() - start_time,
                    "anchors": last,
                })
                return {
                    "confirmed": True,
                    "attempts": attempts,
                    "anchors": last,
                    "start_presses_here": attempt,
                }

            elapsed = time.time() - start_time

            # On first attempt, if 8 seconds have passed and anchors are still
            # absent, return control to the outer loop for ONE retry Start.
            if attempt == 1 and elapsed >= RETRY_START_AFTER:
                break

            time.sleep(0.12)

        attempts.append({
            "attempt": attempt,
            "sent": sent,
            "error": None if sent else err,
            "anchors": last,
        })

    return {
        "confirmed": False,
        "attempts": attempts,
        "anchors": mainmenu_anchors(ws),
        "start_presses_here": 2,
    }


def capture(local_mod, b, hwnd, label):
    fn = find_callable(
        [b, getattr(local_mod, "s39", None), local_mod],
        "capture",
    )
    helper = BASE_TOOLS / "capture_ppsspp.ps1"
    path = OUT / f"stage39r_{label}.png"

    if not fn or not helper.exists():
        return {
            "path": str(path),
            "captured": False,
            "error": "capture helper unavailable",
        }

    try:
        fn(hwnd, path, helper)
        return {
            "path": str(path),
            "captured": path.exists(),
        }
    except Exception as e:
        return {
            "path": str(path),
            "captured": False,
            "error": str(e),
        }


def pointer_samples(ws, uints):
    out = []

    for name in GPR_NAMES:
        if name not in uints:
            continue

        value = uints[name]
        if not (RAM_START <= value < RAM_END):
            continue

        base = max(RAM_START, value - 128)

        try:
            raw = read_ws(ws, base, 384)
        except Exception:
            continue

        p = raw.find(UTF8)

        out.append({
            "register": name,
            "value": f"0x{value:08X}",
            "sample_base": f"0x{base:08X}",
            "utf8_story_address":
                None if p < 0
                else f"0x{base+p:08X}",
            "sample_hex": raw.hex(),
        })

    return out


def full_hit(ws, uints, floats):
    ra = uints.get("ra", 0)
    pc = uints.get("pc", DRAW_HELPER)

    uv = tuple_f(
        floats,
        ["f16","f17","f18","f19"],
    )
    xy = tuple_f(
        floats,
        ["f12","f13","f14","f15"],
    )

    return {
        "pc": f"0x{pc:08X}",
        "ra": f"0x{ra:08X}",
        "caller":
            KNOWN_CALLERS.get(ra, "unknown"),
        "uv_float": uv,
        "uv_floor": quantize_floor(uv),
        "xy_float": xy,
        "xy_floor": quantize_floor(xy),
        "texture_object_a1":
            f"0x{uints.get('a1',0):08X}",
        "render_context_a0":
            f"0x{uints.get('a0',0):08X}",
        "color_ptr_a2":
            f"0x{uints.get('a2',0):08X}",
        "gprs": {
            n: f"0x{uints[n]:08X}"
            for n in GPR_NAMES
            if n in uints
        },
        "fprs": {
            f"f{i}": floats.get(f"f{i}")
            for i in range(32)
            if f"f{i}" in floats
        },
        "pointer_samples":
            pointer_samples(ws, uints),
        "helper_disasm":
            disasm(ws, DRAW_HELPER, 44),
        "caller_disasm":
            disasm(
                ws,
                max(0, ra - 0x140),
                148,
            ) if ra else None,
    }


def geometry_score(q_uv, q_xy):
    uv_exact = (q_uv == GPU_FIRST_UV)

    xy_near = False
    xy_distance = None

    if q_xy is not None:
        xy_distance = sum(
            abs(a-b)
            for a,b in zip(
                q_xy, GPU_FIRST_XY
            )
        )
        xy_near = all(
            abs(a-b) <= XY_NEAR_TOL
            for a,b in zip(
                q_xy, GPU_FIRST_XY
            )
        )

    score = 0
    if uv_exact:
        score += 10000
    if xy_near:
        score += 5000
    if xy_distance is not None:
        score -= xy_distance

    return (
        uv_exact,
        xy_near,
        xy_distance,
        score,
    )


def trace_confirmed_menu(ws):
    """
    Called only AFTER exact Stage39H main-menu memory anchors are present.
    Thus any geometry here belongs to the real selectable main menu state,
    not the title screen.
    """
    add_bp(ws)

    end = time.time() + TRACE_SECONDS
    hits = 0

    caller_counts = Counter()
    best = []

    while time.time() < end and hits < MAX_HITS:
        resume(ws)
        paused = wait_pause(
            ws,
            timeout=min(
                5.0,
                max(0.2, end-time.time()),
            ),
        )
        if paused is None:
            continue

        uints, floats = parse_regs(
            ws.request(
                "cpu.getAllRegs",
                timeout=10,
            )
        )

        hits += 1
        ra = uints.get("ra", 0)
        caller_counts[ra] += 1

        uv = tuple_f(
            floats,
            ["f16","f17","f18","f19"],
        )
        xy = tuple_f(
            floats,
            ["f12","f13","f14","f15"],
        )

        q_uv = quantize_floor(uv)
        q_xy = quantize_floor(xy)

        (
            uv_exact,
            xy_near,
            xy_distance,
            score,
        ) = geometry_score(q_uv, q_xy)

        item = {
            "hit_index": hits,
            "ra": f"0x{ra:08X}",
            "caller":
                KNOWN_CALLERS.get(ra, "unknown"),
            "uv_float": uv,
            "uv_floor": q_uv,
            "xy_float": xy,
            "xy_floor": q_xy,
            "uv_exact": uv_exact,
            "xy_near": xy_near,
            "xy_distance": xy_distance,
            "score": score,
            "texture_object_a1":
                f"0x{uints.get('a1',0):08X}",
        }

        best.append(item)
        best = sorted(
            best,
            key=lambda x: x["score"],
            reverse=True,
        )[:80]

        if uv_exact or xy_near:
            remove_bp(ws)
            return {
                "matched": True,
                "hits_seen": hits,
                "match_reason":
                    "exact_uv"
                    if uv_exact
                    else "near_screen_rect",
                "hit": full_hit(
                    ws, uints, floats
                ),
                "caller_histogram": {
                    f"0x{k:08X} "
                    f"{KNOWN_CALLERS.get(k,'unknown')}":
                        v
                    for k,v in
                    caller_counts.most_common()
                },
                "best_geometry": best,
            }

    remove_bp(ws)

    return {
        "matched": False,
        "hits_seen": hits,
        "caller_histogram": {
            f"0x{k:08X} "
            f"{KNOWN_CALLERS.get(k,'unknown')}":
                v
            for k,v in
            caller_counts.most_common()
        },
        "best_geometry": best,
    }


def wait_same_caller_uv(
    ws,
    caller_ra,
    target_uv,
    timeout=30.0,
    max_hits=1000,
):
    add_bp(ws)

    end = time.time() + timeout
    seen = 0
    nearest = []

    while time.time() < end and seen < max_hits:
        resume(ws)
        paused = wait_pause(
            ws,
            timeout=min(
                5.0,
                max(0.2, end-time.time()),
            ),
        )
        if paused is None:
            continue

        uints, floats = parse_regs(
            ws.request(
                "cpu.getAllRegs",
                timeout=10,
            )
        )
        seen += 1

        if uints.get("ra",0) != caller_ra:
            continue

        uv = tuple_f(
            floats,
            ["f16","f17","f18","f19"],
        )
        q_uv = quantize_floor(uv)

        if q_uv is None:
            continue

        dist = sum(
            abs(a-b)
            for a,b in zip(q_uv, target_uv)
        )

        nearest.append({
            "uv_float": uv,
            "uv_floor": q_uv,
            "distance": dist,
        })
        nearest = sorted(
            nearest,
            key=lambda x: x["distance"],
        )[:30]

        if q_uv == target_uv:
            remove_bp(ws)
            return {
                "matched": True,
                "seen": seen,
                "hit":
                    full_hit(ws, uints, floats),
                "nearest": nearest,
            }

    remove_bp(ws)

    return {
        "matched": False,
        "seen": seen,
        "nearest": nearest,
    }


def make_zip(path):
    if path.exists():
        path.unlink()

    with zipfile.ZipFile(
        path,
        "w",
        zipfile.ZIP_DEFLATED,
    ) as z:
        for p in sorted(OUT.rglob("*")):
            if p.is_file():
                z.write(
                    p,
                    p.relative_to(OUT).as_posix(),
                )


def main():
    OUT.mkdir(
        parents=True,
        exist_ok=True,
    )
    LOG_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    for p in OUT.iterdir():
        if p.is_file():
            p.unlink()

    if not ISO.exists():
        raise RuntimeError(
            f"Missing Stage39F ISO: {ISO}"
        )

    local_mod, b = load_helpers()
    exe = b.find_ppsspp_exe()

    cfg = OUT / "stage39r_append.ini"
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
        b.close_existing_ppsspp(
            timeout=3.0
        )
    except Exception:
        pass

    port = b.choose_free_port()

    cmd = [
        str(exe),
        "-d",
        f"--log={PPSSPP_LOG}",
        "--windowed",
        f"--appendconfig={cfg}",
        f"--debugger={port}",
        str(ISO),
    ]

    log(
        "[Stage39R] Launching PPSSPP normal JIT"
    )

    proc = subprocess.Popen(cmd)
    cleanup = b.register_ppsspp_auto_close(
        proc
    )

    report = {
        "stage": "39R",
        "purpose":
            "Confirm the selectable main menu by exact Stage39H runtime "
            "anchors before installing the draw-helper breakpoint.",
        "stage39q_actual_failure":
            "The saved Stage39Q 'settled_menu' screenshot is still the "
            "BROTHERS IN ARMS title screen, not the selectable Story/Skirmish/"
            "Options/Profile menu. Stage39Q sent Start immediately after the "
            "menu asset became resident, before title input was ready.",
        "stage39h_proven_timing":
            "Stage39H waited two seconds after MENUINT0.RAW opened, then sent "
            "one Start and reached the selectable menu.",
        "main_menu_anchors": {
            f"0x{MAINMENU_OPTIONS_ADDR:08X}":
                "UTF-16 Options",
            f"0x{MAINMENU_PROFILE_ADDR:08X}":
                "UTF-16 Profile",
            f"0x{MAINMENU_STORY_ADDR:08X}":
                "UTF-16 스토리",
        },
        "draw_helper":
            f"0x{DRAW_HELPER:08X}",
        "gpu_first_uv":
            GPU_FIRST_UV,
        "gpu_first_xy":
            GPU_FIRST_XY,
        "iso_patch": False,
        "runtime_patch": False,
    }

    try:
        hwnd = b.find_ppsspp_hwnd(30)
        if not hwnd:
            raise RuntimeError(
                "PPSSPP window did not appear"
            )

        actual_port = (
            b.wait_for_actual_debugger_port(
                PPSSPP_LOG, 30
            )
        )
        ws, host = b.connect_debugger(
            actual_port
        )

        try:
            report["debugger_host"] = host
            report["debugger_port"] = (
                actual_port
            )

            menu = wait_menu_resource(ws)
            report["menu_resource_open"] = menu
            if not menu["opened"]:
                raise RuntimeError(
                    "MENUINT0.RAW did not open"
                )

            source = wait_source(ws)
            report["source_resident"] = source
            if not source.get("ok"):
                raise RuntimeError(
                    "Correct Stage39F source "
                    "did not become resident"
                )

            # Restore the delay that made Stage39H reliable.
            time.sleep(TITLE_SETTLE_SECONDS)

            report["title_capture"] = capture(
                local_mod,
                b,
                hwnd,
                "title_ready",
            )
            report[
                "anchors_before_mainmenu_start"
            ] = mainmenu_anchors(ws)

            state = wait_confirmed_mainmenu(ws)
            report["main_menu_state"] = state

            if not state.get("confirmed"):
                raise RuntimeError(
                    "Selectable main-menu runtime "
                    "anchors never appeared"
                )

            # Let only menu animation finish; no more input.
            time.sleep(1.0)

            report["confirmed_main_menu_capture"] = (
                capture(
                    local_mod,
                    b,
                    hwnd,
                    "confirmed_main_menu",
                )
            )

            report[
                "anchors_before_draw_trace"
            ] = mainmenu_anchors(ws)

            trace = trace_confirmed_menu(ws)
            report["draw_trace"] = trace

            if not trace.get("matched"):
                report["completed"] = False
                raise RuntimeError(
                    "Confirmed main-menu state reached, "
                    "but common draw helper did not "
                    "match the Stage39H first sprite"
                )

            hit = trace["hit"]
            caller_ra = int(hit["ra"], 16)

            report["fallback_same_caller"] = (
                wait_same_caller_uv(
                    ws,
                    caller_ra,
                    GPU_FALLBACK_UV,
                )
            )
            report["fourth_same_caller"] = (
                wait_same_caller_uv(
                    ws,
                    caller_ra,
                    GPU_FOURTH_UV,
                )
            )

            report["analysis"] = {
                "visible_caller_ra":
                    hit["ra"],
                "visible_caller":
                    hit["caller"],
                "visible_is_wide_unicode_renderer":
                    caller_ra == 0x089726C0,
                "fallback_same_caller":
                    bool(
                        report[
                            "fallback_same_caller"
                        ].get("matched")
                    ),
                "fourth_same_caller":
                    bool(
                        report[
                            "fourth_same_caller"
                        ].get("matched")
                    ),
            }

            report["completed"] = True

        finally:
            try:
                ws.close()
            except Exception:
                pass

    except Exception as e:
        report["runtime_exception"] = str(e)
        report["runtime_traceback"] = (
            traceback.format_exc()
        )
        report.setdefault(
            "completed", False
        )

    finally:
        try:
            cleanup()
            report["ppsspp_closed"] = True
        except Exception as e:
            report[
                "ppsspp_close_error"
            ] = str(e)

    REPORT_PATH.write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    target = (
        SUCCESS_ZIP
        if report.get("completed")
        else FAIL_ZIP
    )
    make_zip(target)

    if not report.get("completed"):
        raise RuntimeError(
            f"Stage39R failed. See {FAIL_ZIP}"
        )

    log("[Stage39R] COMPLETE")
    log(
        f"[Stage39R] Upload ZIP: "
        f"{SUCCESS_ZIP}"
    )


if __name__ == "__main__":
    try:
        main()
    except Exception:
        OUT.mkdir(
            parents=True,
            exist_ok=True,
        )
        LOG_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        (OUT / "FAILURE.txt").write_text(
            traceback.format_exc(),
            encoding="utf-8",
        )

        try:
            make_zip(FAIL_ZIP)
        except Exception:
            pass

        print(
            traceback.format_exc(),
            flush=True,
        )
        print(
            f"STAGE 39R FAILED: {FAIL_ZIP}",
            flush=True,
        )
        raise SystemExit(1)
