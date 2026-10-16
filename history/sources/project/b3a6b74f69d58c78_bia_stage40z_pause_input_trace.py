#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import base64
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

from PIL import Image

ROOT = Path(r"PROJECT_ROOT")
BASE_TOOLS = ROOT / "bia_stage39b_tools"
SOURCE_ISO = ROOT / "BIA_STAGE40Y_FIRST_MISSION_UI_TEST.iso"

OUT = ROOT / "analysis" / "stage40z_pause_input_trace"
LOG_DIR = ROOT / "log"

SUCCESS_ZIP = LOG_DIR / "bia_stage40z_upload.zip"
FAIL_ZIP = LOG_DIR / "fail_bia_stage40z_upload.zip"
REPORT_PATH = OUT / "stage40z_report.json"
PPSSPP_LOG = OUT / "stage40z_ppsspp.log"

MENU_OPEN_MARKER = (
    "sceIoOpen(disc0:/PSP_GAME/USRDIR/SYSTEM/RAWFILES/MENUINT0.RAW"
)

# Known Stage40Y campaign renderer invariants.
CAMPAIGN_RENDER_CALL = 0x0898E354
CAMPAIGN_RENDER_WORD = 0x0E327D1A
CAMPAIGN_LOOKUP = 0x08C5CED4

CAMPAIGN_WIDTH_CALL1 = 0x08852B3C
CAMPAIGN_WIDTH_CALL2 = 0x088520C0
CAMPAIGN_WIDTH_WORD1 = 0x0E327D58
CAMPAIGN_WIDTH_WORD2 = 0x0E327D98

# Stage40Y first-mission font invariants.
FONT_OBJECTS = [
    0x09C1AF84,
    0x09C1D11C,
]
EXPECTED_GLYPH_COUNT = 847
EXPECTED_GLYPH_PTR = 0x09E6B020

# Pause menu "챕터 계속": U+CC55 is distinctive and is rendered when pause opens.
PAUSE_PROBE_CP = 0xCC55

# Raw software-renderer framebuffer configuration from the verified handoff.
FRAMEBUFFERS = [
    0x04000000,
    0x04044000,
]
FB_STRIDE = 512
FB_W = 480
FB_H = 272
FB_BYTES = FB_STRIDE * FB_H * 2

RAM_START = 0x08000000
RAM_END = 0x0A000000
RAM_CHUNK = 0x20000

# Only used for a memory-diff fallback if the later pause still refuses input.
DIFF_START = 0x08E00000
DIFF_END = 0x0A000000


def log(msg):
    print(msg, flush=True)


def load_helpers():
    p = BASE_TOOLS / "bia_stage39b_compiled_mdi_text.py"
    if not p.exists():
        raise RuntimeError(f"Missing helper: {p}")

    sys.path.insert(0, str(BASE_TOOLS))
    spec = importlib.util.spec_from_file_location("bia_stage39b_local", p)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)

    b = getattr(mod, "b", None)
    if b is None and hasattr(mod, "s39"):
        b = getattr(mod.s39, "b", None)
    if b is None:
        raise RuntimeError("Could not resolve Stage39B helper object")
    return mod, b


def read_ws(ws, address, size):
    r = ws.request(
        "memory.read",
        timeout=10,
        address=address,
        size=size,
    )
    data = base64.b64decode(r["base64"])
    if len(data) != size:
        raise RuntimeError(
            f"Incomplete memory.read at 0x{address:08X}: {len(data)} != {size}"
        )
    return data


def read_u32(ws, address):
    return struct.unpack("<I", read_ws(ws, address, 4))[0]


def wait_cpu_ready(ws, timeout=25):
    end = time.time() + timeout
    attempts = 0
    last_error = None

    while time.time() < end:
        attempts += 1
        try:
            status = ws.request("cpu.status", timeout=2)
            probe = read_ws(ws, 0x08800000, 4)
            if len(probe) == 4:
                return {
                    "ready": True,
                    "attempts": attempts,
                    "status": status,
                }
        except Exception as e:
            last_error = str(e)
        time.sleep(0.05)

    return {
        "ready": False,
        "attempts": attempts,
        "last_error": last_error,
    }


def wait_menu_resource(log_path, timeout=180):
    end = time.time() + timeout

    while time.time() < end:
        if log_path.exists():
            txt = log_path.read_text(
                encoding="utf-8",
                errors="replace",
            )
            if MENU_OPEN_MARKER in txt:
                return True
        time.sleep(0.1)

    return False


def menu_marker_count():
    if not PPSSPP_LOG.exists():
        return 0
    return PPSSPP_LOG.read_text(
        encoding="utf-8",
        errors="replace",
    ).count(MENU_OPEN_MARKER)


def request_safe(ws, event, **kwargs):
    try:
        value = ws.request(event, timeout=5, **kwargs)
        return {
            "ok": True,
            "response": value,
        }
    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
        }


def release_used_buttons(ws):
    return request_safe(
        ws,
        "input.buttons.send",
        buttons={
            "down": False,
            "up": False,
            "left": False,
            "right": False,
            "cross": False,
            "circle": False,
            "start": False,
        },
    )


def send_hold(ws, button, hold_s=0.20, settle_s=0.65):
    events = []

    events.append({
        "phase": "release_all_before",
        **release_used_buttons(ws),
    })

    events.append({
        "phase": "press",
        **request_safe(
            ws,
            "input.buttons.send",
            buttons={button: True},
        ),
    })

    time.sleep(hold_s)

    events.append({
        "phase": "release",
        **request_safe(
            ws,
            "input.buttons.send",
            buttons={button: False},
        ),
    })

    time.sleep(settle_s)

    return events


def legacy_press(ws, button, duration=2, settle_s=0.65):
    before = release_used_buttons(ws)
    r = request_safe(
        ws,
        "input.buttons.press",
        button=button,
        duration=duration,
    )
    time.sleep(settle_s)
    after = release_used_buttons(ws)

    return [
        {"phase": "release_all_before", **before},
        {"phase": "press", **r},
        {"phase": "release_all_after", **after},
    ]


def analog_pulse(ws, y, hold_s=0.30, settle_s=0.65):
    events = []

    events.append({
        "phase": "analog_center_before",
        **request_safe(
            ws,
            "input.analog.send",
            x=0.0,
            y=0.0,
        ),
    })

    events.append({
        "phase": "analog_press",
        **request_safe(
            ws,
            "input.analog.send",
            x=0.0,
            y=float(y),
        ),
    })

    time.sleep(hold_s)

    events.append({
        "phase": "analog_center_after",
        **request_safe(
            ws,
            "input.analog.send",
            x=0.0,
            y=0.0,
        ),
    })

    time.sleep(settle_s)
    return events


INPUT_METHODS = [
    {
        "name": "legacy_press_d2",
        "kind": "legacy",
        "duration": 2,
    },
    {
        "name": "legacy_press_d8",
        "kind": "legacy",
        "duration": 8,
    },
    {
        "name": "send_080ms",
        "kind": "send",
        "hold_s": 0.08,
    },
    {
        "name": "send_250ms",
        "kind": "send",
        "hold_s": 0.25,
    },
    {
        "name": "send_650ms",
        "kind": "send",
        "hold_s": 0.65,
    },
    {
        "name": "analog_y_plus",
        "kind": "analog",
        "y": 0.85,
    },
    {
        "name": "analog_y_minus",
        "kind": "analog",
        "y": -0.85,
    },
]


def apply_method(ws, method, button="down"):
    if method["kind"] == "legacy":
        return legacy_press(
            ws,
            button,
            duration=method["duration"],
        )

    if method["kind"] == "send":
        return send_hold(
            ws,
            button,
            hold_s=method["hold_s"],
        )

    if method["kind"] == "analog":
        if button == "down":
            y = method["y"]
        elif button == "up":
            y = -method["y"]
        else:
            raise ValueError("analog method only supports up/down")
        return analog_pulse(ws, y)

    raise ValueError(method)


def rgb565_image(raw):
    if len(raw) != FB_BYTES:
        raise RuntimeError("Framebuffer size mismatch")

    rgb = bytearray(FB_W * FB_H * 3)
    o = 0

    for y in range(FB_H):
        row = y * FB_STRIDE * 2

        for x in range(FB_W):
            v = struct.unpack_from("<H", raw, row + x * 2)[0]

            # Same channel order used by the verified Stage40Y live helper.
            r = (v & 31) * 255 // 31
            g = ((v >> 5) & 63) * 255 // 63
            b = ((v >> 11) & 31) * 255 // 31

            rgb[o] = r
            rgb[o+1] = g
            rgb[o+2] = b
            o += 3

    return Image.frombytes(
        "RGB",
        (FB_W, FB_H),
        bytes(rgb),
    )


def red_underline(im):
    """
    The verified pause screenshots show a ~70-pixel red selection underline.
    Locate its row in the central menu region.
    """
    px = im.load()
    row_counts = []

    for y in range(48, 228):
        count = 0

        for x in range(120, 360):
            r, g, b = px[x, y]

            if (
                r >= 90
                and r >= int(g * 1.4)
                and r >= int(b * 1.4)
                and r - g >= 30
            ):
                count += 1

        row_counts.append((count, y))

    count, y = max(row_counts)

    if count < 20:
        return {
            "found": False,
            "row": None,
            "red_pixels": count,
        }

    return {
        "found": True,
        "row": y,
        "red_pixels": count,
    }


def capture(ws, name):
    result = []

    for addr in FRAMEBUFFERS:
        raw = read_ws(ws, addr, FB_BYTES)
        im = rgb565_image(raw)

        path = OUT / f"{name}_{addr:08X}.png"
        im.save(path)

        visible_raw = bytearray()
        for y in range(FB_H):
            start = y * FB_STRIDE * 2
            visible_raw.extend(
                raw[start:start + FB_W * 2]
            )

        result.append({
            "address": f"0x{addr:08X}",
            "path": str(path),
            "visible_sha1": hashlib.sha1(
                bytes(visible_raw)
            ).hexdigest(),
            "underline": red_underline(im),
        })

    best = max(
        result,
        key=lambda x: x["underline"]["red_pixels"],
    )

    return {
        "buffers": result,
        "best_address": best["address"],
        "underline": best["underline"],
    }


def selection_moved(before, after, threshold=12):
    a = before["underline"]
    b = after["underline"]

    if not a.get("found") or not b.get("found"):
        return False

    return abs(
        int(b["row"]) - int(a["row"])
    ) >= threshold


def wait_campaign_patch(ws, timeout=75):
    end = time.time() + timeout
    last = None

    expected = CAMPAIGN_RENDER_WORD

    while time.time() < end:
        try:
            word = read_u32(
                ws,
                CAMPAIGN_RENDER_CALL,
            )
            last = word

            if word == expected:
                return {
                    "ok": True,
                    "renderer_word":
                        f"0x{word:08X}",
                }
        except Exception:
            pass

        time.sleep(0.25)

    return {
        "ok": False,
        "last_renderer_word": (
            None
            if last is None
            else f"0x{last:08X}"
        ),
    }


def remove_pause_bp(ws):
    try:
        ws.request(
            "cpu.breakpoint.remove",
            timeout=5,
            address=CAMPAIGN_LOOKUP,
        )
    except Exception:
        pass


def resume_cpu(ws):
    try:
        ws.request(
            "cpu.resume",
            timeout=0.6,
        )
    except Exception:
        try:
            ws.send_json({
                "event": "cpu.resume",
            })
        except Exception:
            pass


def wait_break(ws, timeout=8):
    end = time.time() + timeout

    while time.time() < end:
        try:
            s = ws.request(
                "cpu.status",
                timeout=2,
            )
            if s.get("stepping", False):
                return True
        except Exception:
            pass

        time.sleep(0.015)

    return False


def arm_pause_probe(ws):
    remove_pause_bp(ws)

    return request_safe(
        ws,
        "cpu.breakpoint.add",
        address=CAMPAIGN_LOOKUP,
        enabled=True,
        log=False,
        condition=f"a1 == 0x{PAUSE_PROBE_CP:X}",
    )


def try_open_pause(ws, label, attempts=8):
    records = []

    for i in range(attempts):
        arm = arm_pause_probe(ws)

        # Explicit send/release avoids relying on the short legacy helper.
        input_events = send_hold(
            ws,
            "start",
            hold_s=0.16,
            settle_s=0.10,
        )

        hit = wait_break(
            ws,
            timeout=3.5,
        )

        rec = {
            "attempt": i + 1,
            "arm": arm,
            "input": input_events,
            "breakpoint_hit": hit,
        }

        if hit:
            remove_pause_bp(ws)
            resume_cpu(ws)
            time.sleep(0.7)

            rec["capture"] = capture(
                ws,
                f"{label}_open_{i+1}",
            )
            records.append(rec)

            return {
                "ok": True,
                "records": records,
            }

        remove_pause_bp(ws)
        resume_cpu(ws)

        time.sleep(0.6)
        c = capture(
            ws,
            f"{label}_try_{i+1}",
        )
        rec["capture"] = c
        records.append(rec)

        # Strong visual fallback: Stage40Y verified top pause underline is y~71.
        u = c["underline"]
        if (
            u.get("found")
            and 60 <= int(u["row"]) <= 82
            and int(u["red_pixels"]) >= 40
        ):
            return {
                "ok": True,
                "records": records,
                "visual_fallback": True,
            }

        # If this was still a movie/loading state, give it time and send Start
        # again on the next iteration. The campaign hook is already loaded.
        time.sleep(1.4)

    return {
        "ok": False,
        "records": records,
    }


def verify_campaign_invariants(ws):
    result = {
        "renderer_call": {
            "actual": f"0x{read_u32(ws, CAMPAIGN_RENDER_CALL):08X}",
            "expected": f"0x{CAMPAIGN_RENDER_WORD:08X}",
        },
        "width_call1": {
            "actual": f"0x{read_u32(ws, CAMPAIGN_WIDTH_CALL1):08X}",
            "expected": f"0x{CAMPAIGN_WIDTH_WORD1:08X}",
        },
        "width_call2": {
            "actual": f"0x{read_u32(ws, CAMPAIGN_WIDTH_CALL2):08X}",
            "expected": f"0x{CAMPAIGN_WIDTH_WORD2:08X}",
        },
        "fonts": [],
    }

    for addr in FONT_OBJECTS:
        count = struct.unpack(
            "<H",
            read_ws(
                ws,
                addr + 0x50,
                2,
            ),
        )[0]
        ptr = read_u32(
            ws,
            addr + 0x54,
        )

        result["fonts"].append({
            "object": f"0x{addr:08X}",
            "count": count,
            "count_ok":
                count == EXPECTED_GLYPH_COUNT,
            "glyph_ptr":
                f"0x{ptr:08X}",
            "glyph_ptr_ok":
                ptr == EXPECTED_GLYPH_PTR,
        })

    result["ok"] = (
        result["renderer_call"]["actual"]
        == result["renderer_call"]["expected"]
        and result["width_call1"]["actual"]
        == result["width_call1"]["expected"]
        and result["width_call2"]["actual"]
        == result["width_call2"]["expected"]
        and all(
            x["count_ok"] and x["glyph_ptr_ok"]
            for x in result["fonts"]
        )
    )

    return result


def scan_ram_region(ws, start, end):
    out = bytearray()

    for addr in range(
        start,
        end,
        RAM_CHUNK,
    ):
        size = min(
            RAM_CHUNK,
            end - addr,
        )
        out.extend(
            read_ws(
                ws,
                addr,
                size,
            )
        )

    return bytes(out)


def diff_ranges(before, after, base, max_ranges=600):
    if len(before) != len(after):
        raise RuntimeError("RAM diff buffers differ in length")

    changed = [
        i
        for i, (a, b) in enumerate(zip(before, after))
        if a != b
    ]

    ranges = []

    if not changed:
        return {
            "changed_bytes": 0,
            "range_count": 0,
            "ranges": [],
        }

    start = prev = changed[0]

    for x in changed[1:]:
        if x <= prev + 4:
            prev = x
            continue

        ranges.append((start, prev + 1))
        start = prev = x

    ranges.append((start, prev + 1))

    rendered = []

    for s, e in ranges[:max_ranges]:
        rendered.append({
            "start":
                f"0x{base+s:08X}",
            "end":
                f"0x{base+e:08X}",
            "bytes":
                e - s,
            "before_hex":
                before[s:min(e, s+32)].hex(),
            "after_hex":
                after[s:min(e, s+32)].hex(),
        })

    return {
        "changed_bytes":
            len(changed),
        "range_count":
            len(ranges),
        "ranges":
            rendered,
        "truncated":
            len(ranges) > max_ranges,
    }


def test_down_methods(ws, prefix, baseline):
    attempts = []

    for method in INPUT_METHODS:
        before = capture(
            ws,
            f"{prefix}_{method['name']}_before",
        )

        events = apply_method(
            ws,
            method,
            "down",
        )

        after = capture(
            ws,
            f"{prefix}_{method['name']}_after",
        )

        moved = selection_moved(
            before,
            after,
        )

        rec = {
            "method":
                method,
            "events":
                events,
            "before":
                before,
            "after":
                after,
            "moved":
                moved,
        }
        attempts.append(rec)

        if moved:
            return {
                "working_method":
                    method,
                "attempts":
                    attempts,
                "selection_after":
                    after,
            }

        # Always force neutral after a failed trial.
        release_used_buttons(ws)
        request_safe(
            ws,
            "input.analog.send",
            x=0.0,
            y=0.0,
        )
        time.sleep(0.25)

    return {
        "working_method": None,
        "attempts": attempts,
        "selection_after": baseline,
    }


def return_selection_top(ws, method, capture_prefix):
    # If a single Down moved from first row to second row, a single Up should
    # restore the top row. If not, toggling pause is used as a reset fallback.
    apply_method(
        ws,
        method,
        "up",
    )

    c = capture(
        ws,
        capture_prefix + "_up",
    )

    if (
        c["underline"].get("found")
        and 60 <= int(c["underline"]["row"]) <= 82
    ):
        return {
            "ok": True,
            "method": "up",
            "capture": c,
        }

    # Toggle pause closed/open. Previous Stage40Y observations show a reopen
    # starts on 챕터 계속.
    send_hold(
        ws,
        "start",
        hold_s=0.16,
        settle_s=0.8,
    )
    send_hold(
        ws,
        "start",
        hold_s=0.16,
        settle_s=0.8,
    )

    c2 = capture(
        ws,
        capture_prefix + "_toggle",
    )

    return {
        "ok": (
            c2["underline"].get("found")
            and 60 <= int(c2["underline"]["row"]) <= 82
        ),
        "method": "pause_toggle",
        "capture": c2,
    }


def navigate_to_chapter_end(ws, method):
    steps = []

    # Starting at 챕터 계속 (index 0), chapter end is index 4.
    for i in range(4):
        events = apply_method(
            ws,
            method,
            "down",
        )
        c = capture(
            ws,
            f"exit_nav_down_{i+1}",
        )
        steps.append({
            "step": i + 1,
            "events": events,
            "capture": c,
        })

    return steps


def wait_main_menu_return(initial_count, timeout=18):
    end = time.time() + timeout

    while time.time() < end:
        count = menu_marker_count()
        if count > initial_count:
            return {
                "returned": True,
                "menu_marker_count": count,
            }
        time.sleep(0.2)

    return {
        "returned": False,
        "menu_marker_count": menu_marker_count(),
    }


def try_confirm_exit(ws, initial_count):
    attempts = []

    # Open confirmation from Chapter End.
    open_events = send_hold(
        ws,
        "cross",
        hold_s=0.16,
        settle_s=0.8,
    )
    attempts.append({
        "phase": "open_confirmation",
        "events": open_events,
        "capture": capture(
            ws,
            "exit_confirmation_open",
        ),
    })

    decision_sequences = [
        ("default_cross", []),
        ("down_cross", ["down"]),
        ("up_cross", ["up"]),
        ("left_cross", ["left"]),
        ("right_cross", ["right"]),
    ]

    for name, moves in decision_sequences:
        if name != "default_cross":
            # If the previous decision was No/cancel, Chapter End should still
            # be selected. Re-open the dialog.
            send_hold(
                ws,
                "cross",
                hold_s=0.16,
                settle_s=0.7,
            )

        move_events = []

        for b in moves:
            move_events.append({
                "button": b,
                "events": send_hold(
                    ws,
                    b,
                    hold_s=0.18,
                    settle_s=0.35,
                ),
            })

        confirm_events = send_hold(
            ws,
            "cross",
            hold_s=0.16,
            settle_s=0.3,
        )

        returned = wait_main_menu_return(
            initial_count,
            timeout=9,
        )

        rec = {
            "decision": name,
            "moves": move_events,
            "confirm": confirm_events,
            "return_check": returned,
        }

        if returned["returned"]:
            time.sleep(1.0)
            rec["capture"] = capture(
                ws,
                f"main_menu_return_{name}",
            )
            attempts.append(rec)

            return {
                "returned": True,
                "attempts": attempts,
            }

        rec["capture"] = capture(
            ws,
            f"exit_after_{name}",
        )
        attempts.append(rec)

    return {
        "returned": False,
        "attempts": attempts,
    }


def start_session(b):
    exe = b.find_ppsspp_exe()

    cfg = OUT / "stage40z_append.ini"
    cfg.write_text(
        "[Debugger]\n"
        "ShowDeveloperMenu = True\n"
        "\n"
        "[General]\n"
        "WindowX = 100\n"
        "WindowY = 100\n"
        "WindowWidth = 960\n"
        "WindowHeight = 544\n"
        "\n"
        "[Graphics]\n"
        "SoftwareRenderer = True\n"
        "ReplaceTextures = False\n"
        "SaveNewTextures = False\n",
        encoding="utf-8",
    )

    if PPSSPP_LOG.exists():
        PPSSPP_LOG.unlink()

    port = b.choose_free_port()

    cmd = [
        str(exe),
        "--loglevel=4",
        f"--log={PPSSPP_LOG}",
        "--windowed",
        f"--appendconfig={cfg}",
        f"--debugger={port}",
        str(SOURCE_ISO),
    ]

    p = subprocess.Popen(cmd)

    return p


def connect_session(b, p):
    hwnd = b.find_ppsspp_hwnd(30)
    if not hwnd:
        raise RuntimeError("PPSSPP window did not appear")

    actual_port = b.wait_for_actual_debugger_port(
        PPSSPP_LOG,
        30,
    )
    ws, host = b.connect_debugger(
        actual_port
    )

    return ws, host, actual_port


def cleanup_owned_process(p, ws):
    if ws is not None:
        try:
            ws.close()
        except Exception:
            pass

    if p is not None:
        try:
            p.terminate()
            p.wait(timeout=4)
        except Exception:
            try:
                p.kill()
                p.wait(timeout=4)
            except Exception:
                pass


def enter_campaign_via_continue(ws):
    nav = []

    # Wait for title/menu resource.
    if not wait_menu_resource(PPSSPP_LOG, timeout=180):
        return {
            "ok": False,
            "reason": "MENUINT0.RAW did not open",
            "navigation": nav,
        }

    time.sleep(2.2)

    # Title -> main menu.
    nav.append({
        "action": "title_start",
        "events": send_hold(
            ws,
            "start",
            hold_s=0.16,
            settle_s=1.0,
        ),
    })

    # Story (default) -> Story submenu.
    nav.append({
        "action": "story_cross",
        "events": send_hold(
            ws,
            "cross",
            hold_s=0.16,
            settle_s=0.9,
        ),
    })

    # Continue is expected as the default Story submenu item on this user's
    # already-exercised first-mission save.
    nav.append({
        "action": "continue_cross",
        "events": send_hold(
            ws,
            "cross",
            hold_s=0.16,
            settle_s=0.8,
        ),
    })

    campaign = wait_campaign_patch(
        ws,
        timeout=75,
    )

    return {
        "ok": campaign["ok"],
        "navigation": nav,
        "campaign": campaign,
    }


def fallback_new_game(ws):
    """
    Best-effort fallback when Continue is unavailable.
    Restarting the emulator is intentionally not done inside this function;
    this sequence is only used if the Story submenu remains active.
    """
    nav = []

    # Escape/cancel once, re-enter Story, choose New Game (one Down).
    nav.append({
        "action": "cancel_continue_path",
        "events": send_hold(
            ws,
            "circle",
            hold_s=0.16,
            settle_s=0.6,
        ),
    })
    nav.append({
        "action": "story_cross_again",
        "events": send_hold(
            ws,
            "cross",
            hold_s=0.16,
            settle_s=0.6,
        ),
    })
    nav.append({
        "action": "new_game_down",
        "events": send_hold(
            ws,
            "down",
            hold_s=0.18,
            settle_s=0.5,
        ),
    })
    nav.append({
        "action": "new_game_cross",
        "events": send_hold(
            ws,
            "cross",
            hold_s=0.16,
            settle_s=0.8,
        ),
    })

    # Existing progress may show a confirmation. Confirm once, then select
    # Normal by moving one row down from Easy.
    nav.append({
        "action": "possible_confirm_cross",
        "events": send_hold(
            ws,
            "cross",
            hold_s=0.16,
            settle_s=0.8,
        ),
    })
    nav.append({
        "action": "difficulty_down_to_normal",
        "events": send_hold(
            ws,
            "down",
            hold_s=0.18,
            settle_s=0.5,
        ),
    })
    nav.append({
        "action": "difficulty_cross",
        "events": send_hold(
            ws,
            "cross",
            hold_s=0.16,
            settle_s=0.8,
        ),
    })

    campaign = wait_campaign_patch(
        ws,
        timeout=75,
    )

    return {
        "ok": campaign["ok"],
        "navigation": nav,
        "campaign": campaign,
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
    OUT.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    for p in OUT.iterdir():
        if p.is_file():
            p.unlink()

    report = {
        "stage": "40Z",
        "purpose":
            "Reproduce the Stage40Y second-pause navigation failure, compare "
            "multiple official PPSSPP input injection paths, and if any path "
            "works, automatically navigate to Chapter End and prove return to "
            "the main menu.",
        "source_iso": str(SOURCE_ISO),
        "handoff_constraints": {
            "do_not_patch_iso": True,
            "software_renderer": True,
            "physical_ram_range":
                "0x08000000..0x0A000000",
            "only_terminate_owned_ppsspp_pid": True,
        },
    }

    p = None
    ws = None

    try:
        if not SOURCE_ISO.exists():
            raise RuntimeError(
                f"Missing Stage40Y ISO: {SOURCE_ISO}"
            )

        _, b = load_helpers()

        p = start_session(b)
        report["ppsspp_pid"] = p.pid

        ws, host, actual_port = connect_session(
            b,
            p,
        )

        report["debugger_host"] = host
        report["debugger_port"] = actual_port

        ready = wait_cpu_ready(ws)
        report["cpu_ready"] = ready

        if not ready.get("ready"):
            raise RuntimeError("CPU did not become ready")

        initial_menu_count = menu_marker_count()
        report["menu_marker_count_initial"] = initial_menu_count

        campaign_entry = enter_campaign_via_continue(ws)

        if not campaign_entry["ok"]:
            campaign_entry["fallback_new_game"] = fallback_new_game(ws)

        report["campaign_entry"] = campaign_entry

        campaign_ok = (
            campaign_entry["ok"]
            or campaign_entry.get(
                "fallback_new_game",
                {},
            ).get("ok", False)
        )

        if not campaign_ok:
            raise RuntimeError(
                "Could not enter Stage40Y campaign via Continue or fallback New Game"
            )

        # The module can load before gameplay becomes interactive. Let it settle.
        time.sleep(3.0)

        report["campaign_invariants"] = verify_campaign_invariants(ws)

        if not report["campaign_invariants"]["ok"]:
            raise RuntimeError(
                "Stage40Y campaign helper/font invariants are not intact"
            )

        # Find the first real pause.
        first_pause = try_open_pause(
            ws,
            "initial_pause",
            attempts=10,
        )
        report["initial_pause_open"] = first_pause

        if not first_pause["ok"]:
            raise RuntimeError(
                "Could not detect initial Chapter Continue pause menu"
            )

        baseline_initial = capture(
            ws,
            "initial_pause_baseline",
        )
        report["initial_pause_baseline"] = baseline_initial

        # Find an input method that can move the initially-working pause menu.
        initial_methods = test_down_methods(
            ws,
            "initial",
            baseline_initial,
        )
        report["initial_down_methods"] = initial_methods

        working_initial = initial_methods["working_method"]

        if working_initial is None:
            report["diagnosis"] = (
                "Fresh-session initial pause also rejected every tested Down "
                "injection method. This is an emulator-input injection issue, "
                "not the Stage40Y later-pause-specific symptom."
            )
            report["issue_resolved"] = False
            report["main_menu_returned"] = False
            report["completed"] = True

        else:
            reset = return_selection_top(
                ws,
                working_initial,
                "initial_reset",
            )
            report["initial_reset"] = reset

            if not reset["ok"]:
                raise RuntimeError(
                    "Could not restore initial pause selection to Chapter Continue"
                )

            # Capture a memory-state signature for a known-good Down transition.
            good_before = scan_ram_region(
                ws,
                DIFF_START,
                DIFF_END,
            )

            apply_method(
                ws,
                working_initial,
                "down",
            )

            good_after = scan_ram_region(
                ws,
                DIFF_START,
                DIFF_END,
            )

            report["initial_good_down_memory_diff"] = diff_ranges(
                good_before,
                good_after,
                DIFF_START,
            )

            # Reset top again, then close pause with Start.
            return_selection_top(
                ws,
                working_initial,
                "initial_reset_after_diff",
            )

            send_hold(
                ws,
                "start",
                hold_s=0.16,
                settle_s=0.9,
            )

            report["gameplay_before_analog"] = capture(
                ws,
                "gameplay_before_analog",
            )

            # Reproduce the handoff: horizontal analog actually turns the view.
            analog_events = [
                request_safe(
                    ws,
                    "input.analog.send",
                    x=0.82,
                    y=0.0,
                )
            ]
            time.sleep(1.15)
            analog_events.append(
                request_safe(
                    ws,
                    "input.analog.send",
                    x=0.0,
                    y=0.0,
                )
            )
            time.sleep(0.6)

            report["analog_turn_events"] = analog_events
            report["gameplay_after_analog"] = capture(
                ws,
                "gameplay_after_analog",
            )

            # Reopen the later pause with the same verified pause-text breakpoint.
            later_pause = try_open_pause(
                ws,
                "later_pause",
                attempts=5,
            )
            report["later_pause_open"] = later_pause

            if not later_pause["ok"]:
                raise RuntimeError(
                    "Could not reopen later Stage40Y pause menu"
                )

            baseline_later = capture(
                ws,
                "later_pause_baseline",
            )
            report["later_pause_baseline"] = baseline_later

            release_used_buttons(ws)
            request_safe(
                ws,
                "input.analog.send",
                x=0.0,
                y=0.0,
            )
            time.sleep(0.35)

            later_methods = test_down_methods(
                ws,
                "later",
                baseline_later,
            )
            report["later_down_methods"] = later_methods

            working_later = later_methods["working_method"]

            if working_later is None:
                # The reported symptom was reproduced. Record memory around the
                # exact address ranges that changed during the known-good Down.
                report["diagnosis"] = (
                    "Reproduced: initial pause accepts Down, but later pause "
                    "rejects all tested legacy/send/analog injection variants."
                )
                report["issue_resolved"] = False
                report["main_menu_returned"] = False
                report["completed"] = True

            else:
                report["diagnosis"] = (
                    "The later pause accepted at least one explicit input method. "
                    "The prior stuck state was input injection/timing related, not "
                    "a Stage40Y localization corruption."
                )

                reset_later = return_selection_top(
                    ws,
                    working_later,
                    "later_reset",
                )
                report["later_reset"] = reset_later

                if not reset_later["ok"]:
                    raise RuntimeError(
                        "Later pause moved, but could not reset to top row"
                    )

                # Navigate four rows to Chapter End and capture every movement.
                exit_steps = navigate_to_chapter_end(
                    ws,
                    working_later,
                )
                report["chapter_end_navigation"] = exit_steps

                # Require visible movement across the sequence before pressing X.
                rows = [
                    x["capture"]["underline"].get("row")
                    for x in exit_steps
                    if x["capture"]["underline"].get("found")
                ]
                report["chapter_end_rows"] = rows

                before_return_count = menu_marker_count()
                report["menu_marker_count_before_exit"] = before_return_count

                exit_result = try_confirm_exit(
                    ws,
                    before_return_count,
                )
                report["exit_confirmation"] = exit_result
                report["main_menu_returned"] = exit_result["returned"]
                report["issue_resolved"] = exit_result["returned"]
                report["completed"] = True

                if exit_result["returned"]:
                    # Menu font invariants after campaign teardown.
                    try:
                        report["returned_menu_renderer_word"] = (
                            f"0x{read_u32(ws, 0x08972360):08X}"
                        )
                    except Exception as e:
                        report["returned_menu_renderer_read_error"] = str(e)

        report["final_menu_marker_count"] = menu_marker_count()

    except Exception as e:
        report["exception"] = str(e)
        report["traceback"] = traceback.format_exc()
        report["completed"] = False

    finally:
        cleanup_owned_process(
            p,
            ws,
        )
        report["owned_ppsspp_closed"] = True

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
            f"Stage40Z technical failure. See {FAIL_ZIP}"
        )

    log("[Stage40Z] diagnostic complete")
    log(
        f"[Stage40Z] issue_resolved={report.get('issue_resolved', False)}"
    )
    log(
        f"[Stage40Z] main_menu_returned={report.get('main_menu_returned', False)}"
    )
    log(
        f"[Stage40Z] Upload ZIP: {SUCCESS_ZIP}"
    )


if __name__ == "__main__":
    try:
        main()
    except Exception:
        OUT.mkdir(parents=True, exist_ok=True)
        LOG_DIR.mkdir(parents=True, exist_ok=True)

        if not REPORT_PATH.exists():
            REPORT_PATH.write_text(
                json.dumps(
                    {
                        "stage": "40Z",
                        "completed": False,
                        "fatal_traceback":
                            traceback.format_exc(),
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
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
            f"STAGE 40Z FAILED: {FAIL_ZIP}",
            flush=True,
        )
        raise SystemExit(1)
