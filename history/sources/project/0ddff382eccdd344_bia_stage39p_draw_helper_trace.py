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

OUT = ROOT / "analysis" / "stage39p_draw_helper_trace"
LOG_DIR = ROOT / "log"

SUCCESS_ZIP = LOG_DIR / "bia_stage39p_upload.zip"
FAIL_ZIP = LOG_DIR / "fail_bia_stage39p_upload.zip"
REPORT_PATH = OUT / "stage39p_report.json"
PPSSPP_LOG = OUT / "stage39p_ppsspp.log"

# BIAON module base = 0x08804000.
# Static draw helper PRX+0x2F2324, called from eight known sites.
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

# Stage39H PPDMP proves the visibly corrupted top label is exactly nine
# byte-glyph sprites.  These are the first, fallback and fourth glyph UVs.
VISIBLE_FIRST_UV = (107.0, 0.0, 114.0, 16.0)   # U+00EC
VISIBLE_FALLBACK_UV = (75.0, 200.0, 87.0, 215.0)
VISIBLE_FOURTH_UV = (107.0, 16.0, 114.0, 32.0) # U+00ED

# Screen rectangle from the first Stage39H sprite.  Used only as a secondary
# score: draw-helper f12..f15 may contain the same screen geometry.
VISIBLE_FIRST_XY = (169.0, 68.0, 175.0, 85.0)

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

RAM_START = 0x08800000
RAM_END = 0x0A800000

MAX_HELPER_HITS = 2500
TRACE_TIMEOUT = 90.0

# Exact helper-entry UV matching tolerance.  Pixel-space UVs in the game are
# normally integers represented as floats, but allow a small half-pixel bias.
UV_TOLERANCE_PER_COMPONENT = 1.25
UV_DISTANCE_LIMIT = 3.0

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
        raise RuntimeError("Could not resolve Stage39B helper module")

    return mod, b


def read_ws(ws, address, size):
    r = ws.request(
        "memory.read",
        timeout=10,
        address=address,
        size=size,
    )
    return base64.b64decode(r["base64"])


def disasm(ws, address, count=80):
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


def parse_all_regs(resp):
    """
    Keep both raw uint32 and PPSSPP's float representation for every category.
    cpu.getAllRegs explicitly returns floatValues for FPRs.
    """
    uints = {}
    floats = {}
    categories = []

    for cat in resp.get("categories", []):
        names = cat.get("registerNames", [])
        uvals = cat.get("uintValues", [])
        fvals = cat.get("floatValues", [])

        categories.append({
            "id": cat.get("id"),
            "name": cat.get("name"),
            "names": names,
        })

        for i, name in enumerate(names):
            lname = name.lower()

            if i < len(uvals):
                uints[lname] = int(uvals[i]) & 0xFFFFFFFF

            if i < len(fvals):
                try:
                    floats[lname] = float(fvals[i])
                except Exception:
                    floats[lname] = None

    return uints, floats, categories


def resume(ws):
    try:
        ws.request("cpu.resume", timeout=0.5)
    except Exception:
        pass


def wait_pause(ws, timeout=12.0):
    end = time.time() + timeout
    last = None

    while time.time() < end:
        try:
            last = ws.request("cpu.status", timeout=2)
            if last.get("stepping", False):
                return last
        except Exception:
            pass
        time.sleep(0.02)

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


def add_draw_bp(ws):
    remove_bp(ws, DRAW_HELPER)
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
            text = PPSSPP_LOG.read_text(
                encoding="utf-8",
                errors="replace",
            )
            if MENU_OPEN_MARKER in text:
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


def tuple_from_fprs(float_regs, names):
    values = []
    for n in names:
        v = float_regs.get(n)
        if v is None or not math.isfinite(v):
            return None
        values.append(float(v))
    return tuple(values)


def distance(a, b):
    if a is None:
        return float("inf")
    return sum(abs(x-y) for x, y in zip(a, b))


def component_close(a, b, tol):
    if a is None:
        return False
    return all(abs(x-y) <= tol for x, y in zip(a, b))


def pointer_samples(ws, uint_regs):
    """
    Search around every PSP-RAM GPR for the exact UTF-8 Story bytes.
    This often reveals the caller's source/cursor pointer even if the helper
    itself only receives geometry and texture arguments.
    """
    out = []

    for name in GPR_NAMES:
        if name not in uint_regs:
            continue

        value = uint_regs[name]
        if not (RAM_START <= value < RAM_END):
            continue

        sample_base = max(RAM_START, value - 128)

        try:
            raw = read_ws(ws, sample_base, 384)
        except Exception:
            continue

        p = raw.find(UTF8)

        out.append({
            "register": name,
            "value": f"0x{value:08X}",
            "sample_base": f"0x{sample_base:08X}",
            "utf8_story_address":
                None if p < 0
                else f"0x{sample_base+p:08X}",
            "sample_hex": raw.hex(),
        })

    return out


def stack_sample(ws, uint_regs):
    sp = uint_regs.get("sp", 0)

    if not (RAM_START <= sp < RAM_END):
        return None

    base = max(RAM_START, sp - 0x100)

    try:
        raw = read_ws(ws, base, 0x600)
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
        "utf8_story_hits": hits,
        "hex": raw.hex(),
    }


def caller_name(ra):
    return KNOWN_CALLERS.get(
        ra,
        "unknown draw-helper caller",
    )


def compact_hit(uints, floats):
    ra = uints.get("ra", 0)

    uv = tuple_from_fprs(
        floats,
        ["f16", "f17", "f18", "f19"],
    )
    xy = tuple_from_fprs(
        floats,
        ["f12", "f13", "f14", "f15"],
    )

    return {
        "ra": f"0x{ra:08X}",
        "caller": caller_name(ra),
        "uv": uv,
        "xy": xy,
        "uv_first_distance":
            distance(uv, VISIBLE_FIRST_UV),
        "uv_fallback_distance":
            distance(uv, VISIBLE_FALLBACK_UV),
        "uv_fourth_distance":
            distance(uv, VISIBLE_FOURTH_UV),
        "xy_first_distance":
            distance(xy, VISIBLE_FIRST_XY),
        "texture_object_a1":
            f"0x{uints.get('a1',0):08X}",
        "render_context_a0":
            f"0x{uints.get('a0',0):08X}",
        "color_ptr_a2":
            f"0x{uints.get('a2',0):08X}",
    }


def full_hit(ws, uints, floats, categories):
    c = compact_hit(uints, floats)
    pc = uints.get("pc", DRAW_HELPER)
    ra = uints.get("ra", 0)

    c.update({
        "pc": f"0x{pc:08X}",
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
        "register_categories": categories,
        "pointer_samples":
            pointer_samples(ws, uints),
        "stack_sample":
            stack_sample(ws, uints),
        "helper_disasm":
            disasm(ws, DRAW_HELPER, 36),
        "caller_disasm":
            disasm(
                ws,
                max(0, ra - 0x100),
                112,
            ) if ra else None,
    })

    return c


def wait_matching_call(
    ws,
    target_uv,
    required_ra=None,
    timeout=25.0,
    max_hits=700,
):
    """
    Continue through draw-helper calls until UV geometry matches target.
    Uses normal CPU breakpoints, not memory breakpoints.
    """
    add_draw_bp(ws)

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

        regs_resp = ws.request(
            "cpu.getAllRegs",
            timeout=10,
        )
        uints, floats, cats = parse_all_regs(
            regs_resp
        )

        seen += 1
        ra = uints.get("ra", 0)

        uv = tuple_from_fprs(
            floats,
            ["f16", "f17", "f18", "f19"],
        )
        d = distance(uv, target_uv)

        near = {
            "hit_index": seen,
            "ra": f"0x{ra:08X}",
            "caller": caller_name(ra),
            "uv": uv,
            "distance": d,
        }

        nearest.append(near)
        nearest = sorted(
            nearest,
            key=lambda x: x["distance"],
        )[:20]

        ra_ok = (
            required_ra is None
            or ra == required_ra
        )

        if (
            ra_ok
            and component_close(
                uv,
                target_uv,
                UV_TOLERANCE_PER_COMPONENT,
            )
            and d <= UV_DISTANCE_LIMIT
        ):
            remove_bp(ws, DRAW_HELPER)
            return {
                "matched": True,
                "seen": seen,
                "hit": full_hit(
                    ws,
                    uints,
                    floats,
                    cats,
                ),
                "nearest": nearest,
            }

    remove_bp(ws, DRAW_HELPER)
    return {
        "matched": False,
        "seen": seen,
        "nearest": nearest,
    }


def discover_visible_first(ws):
    """
    Initial broad pass.  Record caller histogram and stop on the first helper
    call whose UVs match Stage39H's first corrupted sprite.
    """
    add_draw_bp(ws)

    deadline = time.time() + TRACE_TIMEOUT

    hits = 0
    caller_counts = Counter()
    caller_samples = {}
    nearest = []

    while (
        time.time() < deadline
        and hits < MAX_HELPER_HITS
    ):
        resume(ws)
        paused = wait_pause(
            ws,
            timeout=min(
                5.0,
                max(0.2, deadline-time.time()),
            ),
        )

        if paused is None:
            continue

        regs_resp = ws.request(
            "cpu.getAllRegs",
            timeout=10,
        )
        uints, floats, cats = parse_all_regs(
            regs_resp
        )

        hits += 1
        ra = uints.get("ra", 0)
        caller_counts[ra] += 1

        c = compact_hit(uints, floats)

        if ra not in caller_samples:
            caller_samples[ra] = c

        d = c["uv_first_distance"]

        nearest.append({
            "hit_index": hits,
            **c,
        })
        nearest = sorted(
            nearest,
            key=lambda x: x[
                "uv_first_distance"
            ],
        )[:30]

        uv = c["uv"]

        if (
            component_close(
                uv,
                VISIBLE_FIRST_UV,
                UV_TOLERANCE_PER_COMPONENT,
            )
            and d <= UV_DISTANCE_LIMIT
        ):
            remove_bp(ws, DRAW_HELPER)

            return {
                "matched": True,
                "hits_seen": hits,
                "caller_histogram": {
                    f"0x{k:08X} {caller_name(k)}":
                        v
                    for k, v in
                    caller_counts.most_common()
                },
                "caller_first_samples": {
                    f"0x{k:08X} {caller_name(k)}":
                        v
                    for k, v in
                    caller_samples.items()
                },
                "nearest": nearest,
                "visible_first": full_hit(
                    ws,
                    uints,
                    floats,
                    cats,
                ),
            }

    remove_bp(ws, DRAW_HELPER)

    return {
        "matched": False,
        "hits_seen": hits,
        "caller_histogram": {
            f"0x{k:08X} {caller_name(k)}":
                v
            for k, v in
            caller_counts.most_common()
        },
        "caller_first_samples": {
            f"0x{k:08X} {caller_name(k)}":
                v
            for k, v in
            caller_samples.items()
        },
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

    _, b = load_helpers()
    exe = b.find_ppsspp_exe()

    cfg = OUT / "stage39p_append.ini"
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

    # CPU execution breakpoint only; normal JIT is sufficient and much faster
    # than interpreter for potentially hundreds of draw-helper calls.
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
        "[Stage39P] Launching PPSSPP normal JIT"
    )

    proc = subprocess.Popen(cmd)
    cleanup = b.register_ppsspp_auto_close(
        proc
    )

    report = {
        "stage": "39P",
        "purpose":
            "Trace the common textured-quad draw helper directly and identify "
            "the caller that submits the visibly corrupted U+00EC sprite.",
        "stage39o_result":
            "Even with CPU frozen, the recorded Stage39H VERTICES batch was "
            "not resident in main RAM or VRAM at arbitrary sampled instants. "
            "PPSSPP records raw vertex bytes at the exact PRIM event, so the "
            "buffer is too transient to locate reliably by asynchronous snapshots.",
        "new_strategy":
            "Break at the game's common draw helper 0x08AF6324. Its entry "
            "receives pixel-space UV rectangle in f16..f19. Match the exact "
            "Stage39H visible sprite UV instead of trying to find the later "
            "GE vertex ring buffer.",
        "draw_helper": f"0x{DRAW_HELPER:08X}",
        "visible_first_uv": VISIBLE_FIRST_UV,
        "visible_fallback_uv": VISIBLE_FALLBACK_UV,
        "visible_fourth_uv": VISIBLE_FOURTH_UV,
        "known_callers": {
            f"0x{k:08X}": v
            for k, v in KNOWN_CALLERS.items()
        },
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

            menu = wait_menu_open(ws)
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

            # Install breakpoint before entering the selectable menu.
            add_draw_bp(ws)

            try:
                ws.request(
                    "input.buttons.press",
                    timeout=5,
                    button="start",
                    duration=2,
                )
                report[
                    "main_menu_start_sent"
                ] = True
            except Exception as e:
                report[
                    "main_menu_start_error"
                ] = str(e)

            first = discover_visible_first(ws)
            report["first_visible_trace"] = first

            if not first.get("matched"):
                report["completed"] = False
                raise RuntimeError(
                    "No draw-helper call matched visible UV "
                    "(107,0)-(114,16)"
                )

            first_hit = first["visible_first"]
            first_ra = int(
                first_hit["ra"], 16
            )

            # Same caller should immediately draw unsupported bytes as fallback.
            fallback = wait_matching_call(
                ws,
                VISIBLE_FALLBACK_UV,
                required_ra=first_ra,
                timeout=30.0,
                max_hits=900,
            )
            report["same_caller_fallback_trace"] = (
                fallback
            )

            # And the fourth UTF-8 byte ED should use the next original glyph.
            fourth = wait_matching_call(
                ws,
                VISIBLE_FOURTH_UV,
                required_ra=first_ra,
                timeout=30.0,
                max_hits=900,
            )
            report["same_caller_fourth_trace"] = (
                fourth
            )

            report["analysis"] = {
                "visible_caller_ra":
                    first_hit["ra"],
                "visible_caller_name":
                    first_hit["caller"],
                "fallback_same_caller_confirmed":
                    bool(fallback.get("matched")),
                "fourth_same_caller_confirmed":
                    bool(fourth.get("matched")),
                "visible_path_is_wide_unicode_renderer":
                    first_ra == 0x089726C0,
            }

            # The primary goal is the first exact visible draw call.
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
        report.setdefault("completed", False)

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
            f"Stage39P failed. See {FAIL_ZIP}"
        )

    log("[Stage39P] COMPLETE")
    log(
        f"[Stage39P] Upload ZIP: {SUCCESS_ZIP}"
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
            f"STAGE 39P FAILED: {FAIL_ZIP}",
            flush=True,
        )
        raise SystemExit(1)
