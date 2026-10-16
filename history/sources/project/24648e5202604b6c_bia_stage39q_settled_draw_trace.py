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

OUT = ROOT / "analysis" / "stage39q_settled_draw_trace"
LOG_DIR = ROOT / "log"

SUCCESS_ZIP = LOG_DIR / "bia_stage39q_upload.zip"
FAIL_ZIP = LOG_DIR / "fail_bia_stage39q_upload.zip"
REPORT_PATH = OUT / "stage39q_report.json"
PPSSPP_LOG = OUT / "stage39q_ppsspp.log"

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

# Stage39H PPDMP visible top-label first sprite.
GPU_FIRST_UV = (107, 0, 114, 16)
GPU_FIRST_XY = (169, 68, 175, 85)

GPU_FALLBACK_UV = (75, 200, 87, 215)
GPU_FOURTH_UV = (107, 16, 114, 32)

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

RAM_START = 0x08800000
RAM_END = 0x0A800000

SETTLE_SECONDS = 8.0
MAX_HITS = 1600
TRACE_SECONDS = 70.0

# GPU raw integer coords correspond to helper floats with the usual +0.5
# texel/pixel bias.  Quantizing with floor recovers the PPDMP integers.
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
    return tuple(int(math.floor(v + 1.0e-5)) for v in vals)


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


def wait_menu_open(ws, timeout=180.0):
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

        time.sleep(0.1)

    last["ok"] = False
    return last


def capture(local_mod, b, hwnd, label):
    fn = find_callable(
        [b, getattr(local_mod, "s39", None), local_mod],
        "capture",
    )
    helper = BASE_TOOLS / "capture_ppsspp.ps1"
    path = OUT / f"stage39q_{label}.png"

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


def score_geometry(q_uv, q_xy):
    uv_exact = (q_uv == GPU_FIRST_UV)

    xy_distance = None
    xy_near = False
    if q_xy is not None:
        xy_distance = sum(
            abs(a-b)
            for a, b in zip(q_xy, GPU_FIRST_XY)
        )
        xy_near = all(
            abs(a-b) <= XY_NEAR_TOL
            for a, b in zip(q_xy, GPU_FIRST_XY)
        )

    # Prefer exact UV.  Exact/near screen rectangle is an independent route
    # in case UVs are scaled/biased by another helper state.
    score = 0
    if uv_exact:
        score += 1000
    if xy_near:
        score += 500
    if xy_distance is not None:
        score -= xy_distance

    return uv_exact, xy_near, xy_distance, score


def full_hit(ws, uints, floats):
    ra = uints.get("ra", 0)
    pc = uints.get("pc", DRAW_HELPER)

    uv = tuple_f(floats, ["f16","f17","f18","f19"])
    xy = tuple_f(floats, ["f12","f13","f14","f15"])

    q_uv = quantize_floor(uv)
    q_xy = quantize_floor(xy)

    return {
        "pc": f"0x{pc:08X}",
        "ra": f"0x{ra:08X}",
        "caller": KNOWN_CALLERS.get(ra, "unknown"),
        "uv_float": uv,
        "uv_floor": q_uv,
        "xy_float": xy,
        "xy_floor": q_xy,
        "texture_object_a1": f"0x{uints.get('a1',0):08X}",
        "render_context_a0": f"0x{uints.get('a0',0):08X}",
        "color_ptr_a2": f"0x{uints.get('a2',0):08X}",
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
        "pointer_samples": pointer_samples(ws, uints),
        "helper_disasm": disasm(ws, DRAW_HELPER, 40),
        "caller_disasm":
            disasm(ws, max(0, ra-0x120), 132)
            if ra else None,
    }


def trace_settled_frame(ws):
    add_bp(ws)

    end = time.time() + TRACE_SECONDS
    hits = 0
    caller_counts = Counter()
    uv_counts = Counter()
    xy_counts = Counter()
    best = []

    while time.time() < end and hits < MAX_HITS:
        resume(ws)
        paused = wait_pause(
            ws,
            timeout=min(5.0, max(0.2, end-time.time())),
        )
        if paused is None:
            continue

        uints, floats = parse_regs(
            ws.request("cpu.getAllRegs", timeout=10)
        )

        hits += 1
        ra = uints.get("ra", 0)

        uv = tuple_f(floats, ["f16","f17","f18","f19"])
        xy = tuple_f(floats, ["f12","f13","f14","f15"])

        q_uv = quantize_floor(uv)
        q_xy = quantize_floor(xy)

        caller_counts[ra] += 1
        if q_uv is not None:
            uv_counts[(ra, q_uv)] += 1
        if q_xy is not None:
            xy_counts[(ra, q_xy)] += 1

        uv_exact, xy_near, xy_dist, score = score_geometry(
            q_uv, q_xy
        )

        item = {
            "hit_index": hits,
            "ra": f"0x{ra:08X}",
            "caller": KNOWN_CALLERS.get(ra, "unknown"),
            "uv_float": uv,
            "uv_floor": q_uv,
            "xy_float": xy,
            "xy_floor": q_xy,
            "uv_exact": uv_exact,
            "xy_near": xy_near,
            "xy_distance": xy_dist,
            "score": score,
            "texture_object_a1": f"0x{uints.get('a1',0):08X}",
        }

        best.append(item)
        best = sorted(
            best,
            key=lambda x: x["score"],
            reverse=True,
        )[:50]

        if uv_exact or xy_near:
            remove_bp(ws)
            return {
                "matched": True,
                "hits_seen": hits,
                "match_reason":
                    "exact_uv" if uv_exact else "near_screen_rect",
                "hit": full_hit(ws, uints, floats),
                "caller_histogram": {
                    f"0x{k:08X} {KNOWN_CALLERS.get(k,'unknown')}": v
                    for k, v in caller_counts.most_common()
                },
                "top_geometry_hits": best,
            }

    remove_bp(ws)

    # Compact common geometry summary for diagnosis if no direct match.
    common_uv = []
    for (ra, geom), count in uv_counts.most_common(80):
        common_uv.append({
            "ra": f"0x{ra:08X}",
            "caller": KNOWN_CALLERS.get(ra, "unknown"),
            "uv_floor": geom,
            "count": count,
        })

    common_xy = []
    for (ra, geom), count in xy_counts.most_common(80):
        common_xy.append({
            "ra": f"0x{ra:08X}",
            "caller": KNOWN_CALLERS.get(ra, "unknown"),
            "xy_floor": geom,
            "count": count,
        })

    return {
        "matched": False,
        "hits_seen": hits,
        "caller_histogram": {
            f"0x{k:08X} {KNOWN_CALLERS.get(k,'unknown')}": v
            for k, v in caller_counts.most_common()
        },
        "top_geometry_hits": best,
        "common_uv": common_uv,
        "common_xy": common_xy,
    }


def wait_same_caller_geometry(
    ws,
    caller_ra,
    target_uv,
    timeout=25.0,
    max_hits=700,
):
    add_bp(ws)

    end = time.time() + timeout
    seen = 0
    nearest = []

    while time.time() < end and seen < max_hits:
        resume(ws)
        paused = wait_pause(
            ws,
            timeout=min(5.0, max(0.2, end-time.time())),
        )
        if paused is None:
            continue

        uints, floats = parse_regs(
            ws.request("cpu.getAllRegs", timeout=10)
        )
        seen += 1

        ra = uints.get("ra", 0)
        uv = tuple_f(floats, ["f16","f17","f18","f19"])
        q_uv = quantize_floor(uv)

        if ra != caller_ra or q_uv is None:
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
        )[:20]

        if q_uv == target_uv:
            remove_bp(ws)
            return {
                "matched": True,
                "seen": seen,
                "hit": full_hit(ws, uints, floats),
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
        path, "w", zipfile.ZIP_DEFLATED
    ) as z:
        for p in sorted(OUT.rglob("*")):
            if p.is_file():
                z.write(
                    p,
                    p.relative_to(OUT).as_posix(),
                )


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    for p in OUT.iterdir():
        if p.is_file():
            p.unlink()

    if not ISO.exists():
        raise RuntimeError(f"Missing ISO: {ISO}")

    local_mod, b = load_helpers()
    exe = b.find_ppsspp_exe()

    cfg = OUT / "stage39q_append.ini"
    cfg.write_text(
        "[Debugger]\nShowDeveloperMenu = True\n\n"
        "[Graphics]\nReplaceTextures = False\nSaveNewTextures = False\n",
        encoding="utf-8",
    )

    if PPSSPP_LOG.exists():
        PPSSPP_LOG.unlink()

    try:
        b.close_existing_ppsspp(timeout=3.0)
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

    log("[Stage39Q] Launching PPSSPP normal JIT")
    proc = subprocess.Popen(cmd)
    cleanup = b.register_ppsspp_auto_close(proc)

    report = {
        "stage": "39Q",
        "purpose":
            "Let the selectable main menu fully settle BEFORE installing the "
            "draw-helper breakpoint, then match the actual Stage39H sprite by "
            "quantized UV or screen rectangle.",
        "stage39p_failure":
            "Stage39P installed the draw-helper breakpoint before entering "
            "the main menu. Handling every draw call slowed emulation so much "
            "that only transition/background geometry was observed: 154 calls "
            "from the wide renderer and 23 from the background callsite. "
            "The visible menu-item draw state was never reached.",
        "critical_changes": [
            "No draw breakpoint during title->menu transition",
            "Wait 8 seconds with game running normally",
            "Capture the settled state before tracing",
            "Quantize helper floats with floor to match raw PPDMP integer UV/XY",
            "Accept exact UV OR near screen rectangle for the first visible sprite",
        ],
        "draw_helper": f"0x{DRAW_HELPER:08X}",
        "gpu_first_uv": GPU_FIRST_UV,
        "gpu_first_xy": GPU_FIRST_XY,
        "iso_patch": False,
        "runtime_patch": False,
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

            menu = wait_menu_open(ws)
            report["menu_resource_open"] = menu
            if not menu["opened"]:
                raise RuntimeError("MENUINT0.RAW did not open")

            source = wait_source(ws)
            report["source_resident"] = source
            if not source.get("ok"):
                raise RuntimeError(
                    "Correct Stage39F source did not become resident"
                )

            # IMPORTANT: no draw breakpoint yet.
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

            time.sleep(SETTLE_SECONDS)

            report["settled_capture"] = capture(
                local_mod, b, hwnd, "settled_menu"
            )

            # Only now begin tracing continuously-redrawn menu geometry.
            first = trace_settled_frame(ws)
            report["settled_draw_trace"] = first

            if not first.get("matched"):
                report["completed"] = False
                raise RuntimeError(
                    "Settled main-menu draw helper did not match the "
                    "Stage39H top-item UV or screen rectangle"
                )

            hit = first["hit"]
            caller_ra = int(hit["ra"], 16)

            report["fallback_same_caller"] = wait_same_caller_geometry(
                ws,
                caller_ra,
                GPU_FALLBACK_UV,
                timeout=25.0,
            )

            report["fourth_same_caller"] = wait_same_caller_geometry(
                ws,
                caller_ra,
                GPU_FOURTH_UV,
                timeout=25.0,
            )

            report["analysis"] = {
                "visible_caller_ra": hit["ra"],
                "visible_caller": hit["caller"],
                "visible_is_wide_unicode_renderer":
                    caller_ra == 0x089726C0,
                "fallback_same_caller":
                    bool(report["fallback_same_caller"].get("matched")),
                "fourth_same_caller":
                    bool(report["fourth_same_caller"].get("matched")),
            }

            report["completed"] = True

        finally:
            try:
                ws.close()
            except Exception:
                pass

    except Exception as e:
        report["runtime_exception"] = str(e)
        report["runtime_traceback"] = traceback.format_exc()
        report.setdefault("completed", False)

    finally:
        try:
            cleanup()
            report["ppsspp_closed"] = True
        except Exception as e:
            report["ppsspp_close_error"] = str(e)

    REPORT_PATH.write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    target = SUCCESS_ZIP if report.get("completed") else FAIL_ZIP
    make_zip(target)

    if not report.get("completed"):
        raise RuntimeError(f"Stage39Q failed. See {FAIL_ZIP}")

    log("[Stage39Q] COMPLETE")
    log(f"[Stage39Q] Upload ZIP: {SUCCESS_ZIP}")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        OUT.mkdir(parents=True, exist_ok=True)
        LOG_DIR.mkdir(parents=True, exist_ok=True)

        (OUT / "FAILURE.txt").write_text(
            traceback.format_exc(),
            encoding="utf-8",
        )

        try:
            make_zip(FAIL_ZIP)
        except Exception:
            pass

        print(traceback.format_exc(), flush=True)
        print(f"STAGE 39Q FAILED: {FAIL_ZIP}", flush=True)
        raise SystemExit(1)
