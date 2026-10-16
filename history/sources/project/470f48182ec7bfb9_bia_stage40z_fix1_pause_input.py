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

OUT = ROOT / "analysis" / "stage40z_fix1_pause_input"
LOG_DIR = ROOT / "log"

SUCCESS_ZIP = LOG_DIR / "bia_stage40z_fix1_upload.zip"
FAIL_ZIP = LOG_DIR / "fail_bia_stage40z_fix1_upload.zip"
REPORT_PATH = OUT / "stage40z_fix1_report.json"
PPSSPP_LOG = OUT / "stage40z_fix1_ppsspp.log"

# Proven menu renderer path (Stage39U/40G/40O).
MENU_LOOKUP = 0x08C7F2FC
MENU_RENDER_LOOKUP_RA = 0x08972368
MENU_STORY_CP = 0xD1A0  # 토 in 스토리
MENU_RENDER_CALL = 0x08972360
MENU_RENDER_WORD = 0x0E3310E4  # bytes e4 10 33 0e

# Proven campaign Stage40R/Y runtime hooks.
CAMPAIGN_LOOKUP = 0x08C5CED4
CAMPAIGN_RENDER_CALL = 0x0898E354
CAMPAIGN_RENDER_WORD = 0x0E327D1A
CAMPAIGN_WIDTH_CALL1 = 0x08852B3C
CAMPAIGN_WIDTH_CALL2 = 0x088520C0
CAMPAIGN_WIDTH_WORD1 = 0x0E327D58
CAMPAIGN_WIDTH_WORD2 = 0x0E327D98

# "챕터 계속" probe.
PAUSE_PROBE_CP = 0xCC55

FONT_OBJECTS = [
    0x09C1AF84,
    0x09C1D11C,
]
EXPECTED_GLYPH_COUNT = 847
EXPECTED_GLYPH_PTR = 0x09E6B020

FRAMEBUFFERS = [
    0x04000000,
    0x04044000,
]
FB_STRIDE = 512
FB_W = 480
FB_H = 272
FB_BYTES = FB_STRIDE * FB_H * 2


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
        raise RuntimeError("Could not resolve helper object")
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
            f"Incomplete memory.read 0x{address:08X}: {len(data)} != {size}"
        )
    return data


def read_u32(ws, address):
    return struct.unpack("<I", read_ws(ws, address, 4))[0]


def request_safe(ws, event, **kwargs):
    try:
        return {
            "ok": True,
            "response": ws.request(
                event,
                timeout=5,
                **kwargs,
            ),
        }
    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
        }


def wait_cpu_ready(ws, timeout=25):
    end = time.time() + timeout
    attempts = 0
    last_error = None

    while time.time() < end:
        attempts += 1
        try:
            s = ws.request("cpu.status", timeout=2)
            read_ws(ws, 0x08800000, 4)
            return {
                "ready": True,
                "attempts": attempts,
                "status": s,
            }
        except Exception as e:
            last_error = str(e)
        time.sleep(0.05)

    return {
        "ready": False,
        "attempts": attempts,
        "last_error": last_error,
    }


def release_buttons(ws):
    return request_safe(
        ws,
        "input.buttons.send",
        buttons={
            "start": False,
            "cross": False,
            "circle": False,
            "down": False,
            "up": False,
            "left": False,
            "right": False,
        },
    )


def button_hold(ws, button, hold=0.16, settle=0.45):
    events = []

    events.append({
        "phase": "neutral",
        **release_buttons(ws),
    })

    events.append({
        "phase": "down",
        **request_safe(
            ws,
            "input.buttons.send",
            buttons={button: True},
        ),
    })

    time.sleep(hold)

    events.append({
        "phase": "up",
        **request_safe(
            ws,
            "input.buttons.send",
            buttons={button: False},
        ),
    })

    time.sleep(settle)
    return events


def legacy_press(ws, button, duration=2, settle=0.45):
    release_buttons(ws)
    r = request_safe(
        ws,
        "input.buttons.press",
        button=button,
        duration=duration,
    )
    time.sleep(settle)
    release_buttons(ws)
    return r


def analog_pulse(ws, y, hold=0.25, settle=0.45):
    events = []
    events.append(
        request_safe(
            ws,
            "input.analog.send",
            x=0.0,
            y=0.0,
        )
    )
    events.append(
        request_safe(
            ws,
            "input.analog.send",
            x=0.0,
            y=float(y),
        )
    )
    time.sleep(hold)
    events.append(
        request_safe(
            ws,
            "input.analog.send",
            x=0.0,
            y=0.0,
        )
    )
    time.sleep(settle)
    return events


def remove_bp(ws, address):
    try:
        ws.request(
            "cpu.breakpoint.remove",
            timeout=5,
            address=address,
        )
    except Exception:
        pass


def resume_cpu(ws):
    try:
        ws.request("cpu.resume", timeout=0.6)
    except Exception:
        try:
            ws.send_json({"event": "cpu.resume"})
        except Exception:
            pass


def wait_pause_state(ws, timeout=8):
    end = time.time() + timeout

    while time.time() < end:
        try:
            s = ws.request("cpu.status", timeout=2)
            if s.get("stepping", False):
                return True
        except Exception:
            pass
        time.sleep(0.015)

    return False


def arm_lookup(ws, address, codepoint, ra=None):
    remove_bp(ws, address)

    cond = f"a1 == 0x{codepoint:X}"
    if ra is not None:
        cond += f" && ra == 0x{ra:08X}"

    return request_safe(
        ws,
        "cpu.breakpoint.add",
        address=address,
        enabled=True,
        log=False,
        condition=cond,
    )


def rgb565_image(raw):
    rgb = bytearray(FB_W * FB_H * 3)
    o = 0

    for y in range(FB_H):
        base = y * FB_STRIDE * 2

        for x in range(FB_W):
            v = struct.unpack_from(
                "<H",
                raw,
                base + x * 2,
            )[0]

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


def underline(im):
    px = im.load()
    best = (0, None)

    for y in range(48, 228):
        n = 0

        for x in range(120, 360):
            r, g, b = px[x, y]

            if (
                r >= 90
                and r >= int(g * 1.4)
                and r >= int(b * 1.4)
                and r - g >= 30
            ):
                n += 1

        if n > best[0]:
            best = (n, y)

    if best[0] < 20:
        return {
            "found": False,
            "row": None,
            "red_pixels": best[0],
        }

    return {
        "found": True,
        "row": best[1],
        "red_pixels": best[0],
    }


def capture(ws, name):
    rows = []

    for addr in FRAMEBUFFERS:
        raw = read_ws(ws, addr, FB_BYTES)
        im = rgb565_image(raw)
        path = OUT / f"{name}_{addr:08X}.png"
        im.save(path)

        visible = bytearray()
        for y in range(FB_H):
            off = y * FB_STRIDE * 2
            visible.extend(raw[off:off + FB_W * 2])

        rows.append({
            "address": f"0x{addr:08X}",
            "path": str(path),
            "visible_sha1":
                hashlib.sha1(bytes(visible)).hexdigest(),
            "underline": underline(im),
        })

    best = max(
        rows,
        key=lambda x: x["underline"]["red_pixels"],
    )

    return {
        "buffers": rows,
        "best_address": best["address"],
        "underline": best["underline"],
    }


def selection_moved(a, b, threshold=12):
    x = a["underline"]
    y = b["underline"]

    return (
        x.get("found")
        and y.get("found")
        and abs(int(y["row"]) - int(x["row"])) >= threshold
    )


def wait_menu_story_and_skip_intro(ws, timeout=150):
    """
    Stage40Z failed because it waited for a MENUINT0.RAW log line that this run
    never emits. Meanwhile the unskipped Bink logo/movie consumed ~11 minutes
    under the software renderer.

    Here the REAL Stage40O/40G menu renderer is the state oracle:
      lookup 0x08C7F2FC, Story '토', RA 0x08972368.
    START is pulsed while waiting, so movies/title screens are skipped.
    """
    arm = arm_lookup(
        ws,
        MENU_LOOKUP,
        MENU_STORY_CP,
        MENU_RENDER_LOOKUP_RA,
    )

    attempts = []
    end = time.time() + timeout
    next_start = 0.0

    while time.time() < end:
        if wait_pause_state(ws, timeout=0.08):
            attempts.append({
                "event": "story_breakpoint_hit",
                "elapsed":
                    timeout - max(0.0, end - time.time()),
            })

            remove_bp(ws, MENU_LOOKUP)
            resume_cpu(ws)
            time.sleep(0.5)

            return {
                "ok": True,
                "arm": arm,
                "events": attempts,
                "capture": capture(
                    ws,
                    "main_menu_detected",
                ),
            }

        now = time.time()

        if now >= next_start:
            attempts.append({
                "event": "start_pulse",
                "result":
                    button_hold(
                        ws,
                        "start",
                        hold=0.14,
                        settle=0.12,
                    ),
            })
            next_start = time.time() + 1.4

        time.sleep(0.04)

    remove_bp(ws, MENU_LOOKUP)
    resume_cpu(ws)

    return {
        "ok": False,
        "arm": arm,
        "events": attempts,
        "capture": capture(
            ws,
            "main_menu_timeout",
        ),
    }


def wait_word(ws, address, expected, timeout):
    end = time.time() + timeout
    samples = []

    while time.time() < end:
        try:
            word = read_u32(ws, address)

            if len(samples) < 30:
                samples.append(
                    f"0x{word:08X}"
                )

            if word == expected:
                return {
                    "ok": True,
                    "word": f"0x{word:08X}",
                    "samples": samples,
                }
        except Exception as e:
            if len(samples) < 30:
                samples.append(
                    "ERR:" + str(e)
                )

        time.sleep(0.18)

    return {
        "ok": False,
        "samples": samples,
    }


def enter_campaign(ws):
    """
    Main menu is already confirmed with Story selected.
    Try Continue first. If the campaign module does not appear, fall back to
    New Game -> Normal while continuing to pulse START to skip movies.
    """
    result = {
        "main_story_cross":
            button_hold(
                ws,
                "cross",
                hold=0.16,
                settle=0.7,
            ),
    }

    # Default Story submenu item is Continue on the user's existing progress.
    result["continue_cross"] = button_hold(
        ws,
        "cross",
        hold=0.16,
        settle=0.6,
    )

    end = time.time() + 45
    pulses = []

    while time.time() < end:
        w = wait_word(
            ws,
            CAMPAIGN_RENDER_CALL,
            CAMPAIGN_RENDER_WORD,
            timeout=0.35,
        )

        if w["ok"]:
            result["path"] = "Continue"
            result["campaign_word"] = w
            result["skip_pulses"] = pulses
            return result

        pulses.append(
            button_hold(
                ws,
                "start",
                hold=0.12,
                settle=0.08,
            )
        )
        time.sleep(0.55)

    # We did not reach BIAOFF. Try returning to Story submenu/main path and
    # selecting New Game one row below Continue.
    result["continue_failed_capture"] = capture(
        ws,
        "continue_failed",
    )
    result["fallback_circle"] = button_hold(
        ws,
        "circle",
        hold=0.16,
        settle=0.55,
    )
    result["fallback_story_cross"] = button_hold(
        ws,
        "cross",
        hold=0.16,
        settle=0.55,
    )
    result["fallback_newgame_down"] = button_hold(
        ws,
        "down",
        hold=0.22,
        settle=0.45,
    )
    result["fallback_newgame_cross"] = button_hold(
        ws,
        "cross",
        hold=0.16,
        settle=0.7,
    )

    # Existing profile may ask confirmation. Cross once, then move to Normal.
    result["fallback_confirm_cross"] = button_hold(
        ws,
        "cross",
        hold=0.16,
        settle=0.65,
    )
    result["fallback_normal_down"] = button_hold(
        ws,
        "down",
        hold=0.22,
        settle=0.45,
    )
    result["fallback_normal_cross"] = button_hold(
        ws,
        "cross",
        hold=0.16,
        settle=0.65,
    )

    end = time.time() + 70
    pulses = []

    while time.time() < end:
        w = wait_word(
            ws,
            CAMPAIGN_RENDER_CALL,
            CAMPAIGN_RENDER_WORD,
            timeout=0.35,
        )

        if w["ok"]:
            result["path"] = "NewGameNormal"
            result["campaign_word"] = w
            result["skip_pulses_fallback"] = pulses
            return result

        pulses.append(
            button_hold(
                ws,
                "start",
                hold=0.12,
                settle=0.08,
            )
        )
        time.sleep(0.55)

    result["path"] = None
    result["final_capture"] = capture(
        ws,
        "campaign_entry_failed",
    )
    return result


def verify_campaign(ws):
    result = {
        "renderer_call": {
            "actual":
                f"0x{read_u32(ws, CAMPAIGN_RENDER_CALL):08X}",
            "expected":
                f"0x{CAMPAIGN_RENDER_WORD:08X}",
        },
        "width_call1": {
            "actual":
                f"0x{read_u32(ws, CAMPAIGN_WIDTH_CALL1):08X}",
            "expected":
                f"0x{CAMPAIGN_WIDTH_WORD1:08X}",
        },
        "width_call2": {
            "actual":
                f"0x{read_u32(ws, CAMPAIGN_WIDTH_CALL2):08X}",
            "expected":
                f"0x{CAMPAIGN_WIDTH_WORD2:08X}",
        },
        "fonts": [],
    }

    for addr in FONT_OBJECTS:
        count = struct.unpack(
            "<H",
            read_ws(ws, addr + 0x50, 2),
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


def open_pause(ws, prefix, attempts=14):
    records = []

    for i in range(attempts):
        arm = arm_lookup(
            ws,
            CAMPAIGN_LOOKUP,
            PAUSE_PROBE_CP,
        )

        ev = button_hold(
            ws,
            "start",
            hold=0.16,
            settle=0.12,
        )

        hit = wait_pause_state(
            ws,
            timeout=2.7,
        )

        rec = {
            "attempt": i + 1,
            "arm": arm,
            "input": ev,
            "hit": hit,
        }

        if hit:
            remove_bp(
                ws,
                CAMPAIGN_LOOKUP,
            )
            resume_cpu(ws)
            time.sleep(0.65)

            rec["capture"] = capture(
                ws,
                f"{prefix}_opened_{i+1}",
            )
            records.append(rec)

            return {
                "ok": True,
                "records": records,
            }

        remove_bp(
            ws,
            CAMPAIGN_LOOKUP,
        )
        resume_cpu(ws)
        time.sleep(0.65)

        c = capture(
            ws,
            f"{prefix}_attempt_{i+1}",
        )
        rec["capture"] = c
        records.append(rec)

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

    return {
        "ok": False,
        "records": records,
    }


METHODS = [
    {
        "name": "legacy_duration_2",
        "kind": "legacy",
        "duration": 2,
    },
    {
        "name": "legacy_duration_8",
        "kind": "legacy",
        "duration": 8,
    },
    {
        "name": "send_080ms",
        "kind": "send",
        "hold": 0.08,
    },
    {
        "name": "send_220ms",
        "kind": "send",
        "hold": 0.22,
    },
    {
        "name": "send_600ms",
        "kind": "send",
        "hold": 0.60,
    },
    {
        "name": "analog_plus",
        "kind": "analog",
        "y": 0.85,
    },
    {
        "name": "analog_minus",
        "kind": "analog",
        "y": -0.85,
    },
]


def apply_method(ws, method, direction):
    if method["kind"] == "legacy":
        return legacy_press(
            ws,
            direction,
            duration=method["duration"],
        )

    if method["kind"] == "send":
        return button_hold(
            ws,
            direction,
            hold=method["hold"],
            settle=0.5,
        )

    if method["kind"] == "analog":
        y = method["y"]

        if direction == "up":
            y = -y

        return analog_pulse(
            ws,
            y,
            hold=0.28,
            settle=0.5,
        )

    raise RuntimeError("Unknown method")


def test_methods(ws, prefix):
    attempts = []

    for method in METHODS:
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

        attempts.append({
            "method": method,
            "events": events,
            "before": before,
            "after": after,
            "moved": moved,
        })

        if moved:
            return {
                "working_method": method,
                "attempts": attempts,
            }

        release_buttons(ws)
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
    }


def reset_top(ws, method, prefix):
    apply_method(
        ws,
        method,
        "up",
    )
    c = capture(
        ws,
        prefix + "_up",
    )

    if (
        c["underline"].get("found")
        and 60 <= int(c["underline"]["row"]) <= 82
    ):
        return {
            "ok": True,
            "via": "up",
            "capture": c,
        }

    # Pause toggle resets selection in the observed Stage40Y behavior.
    button_hold(
        ws,
        "start",
        hold=0.16,
        settle=0.65,
    )
    button_hold(
        ws,
        "start",
        hold=0.16,
        settle=0.65,
    )

    c = capture(
        ws,
        prefix + "_toggle",
    )

    return {
        "ok": (
            c["underline"].get("found")
            and 60 <= int(c["underline"]["row"]) <= 82
        ),
        "via": "pause_toggle",
        "capture": c,
    }


def wait_menu_module(ws, timeout=25):
    return wait_word(
        ws,
        MENU_RENDER_CALL,
        MENU_RENDER_WORD,
        timeout,
    )


def prove_returned_main_menu(ws):
    module = wait_menu_module(
        ws,
        timeout=20,
    )

    if not module["ok"]:
        return {
            "ok": False,
            "menu_module": module,
        }

    # Once menu executable is back, prove selectable main menu by catching Story.
    story = wait_menu_story_and_skip_intro(
        ws,
        timeout=35,
    )

    return {
        "ok": story["ok"],
        "menu_module": module,
        "story": story,
    }


def exit_to_main_menu(ws, method):
    nav = []

    # Assumes selection is reset to 챕터 계속.
    for i in range(4):
        ev = apply_method(
            ws,
            method,
            "down",
        )
        c = capture(
            ws,
            f"chapter_end_down_{i+1}",
        )
        nav.append({
            "step": i + 1,
            "events": ev,
            "capture": c,
        })

    # Open Chapter End confirmation.
    open_ev = button_hold(
        ws,
        "cross",
        hold=0.16,
        settle=0.65,
    )
    open_cap = capture(
        ws,
        "chapter_end_confirm_open",
    )

    decisions = []

    # Default may be No; try likely alternatives while returning to the same
    # Chapter End selection if cancellation occurs.
    for name, moves in [
        ("default", []),
        ("down", ["down"]),
        ("up", ["up"]),
        ("left", ["left"]),
        ("right", ["right"]),
    ]:
        if name != "default":
            # Re-open confirmation after the previous cancel attempt.
            button_hold(
                ws,
                "cross",
                hold=0.16,
                settle=0.55,
            )

        move_events = []

        for b in moves:
            move_events.append({
                "button": b,
                "events": button_hold(
                    ws,
                    b,
                    hold=0.18,
                    settle=0.25,
                ),
            })

        # Arm no breakpoint here; module swap can invalidate it. Confirm first,
        # then detect menu executable word and Story renderer.
        confirm = button_hold(
            ws,
            "cross",
            hold=0.16,
            settle=0.25,
        )

        returned = prove_returned_main_menu(
            ws,
        )

        rec = {
            "decision": name,
            "moves": move_events,
            "confirm": confirm,
            "returned": returned,
        }

        if returned["ok"]:
            decisions.append(rec)

            return {
                "returned": True,
                "navigation": nav,
                "confirmation_open": {
                    "events": open_ev,
                    "capture": open_cap,
                },
                "decisions": decisions,
            }

        rec["capture"] = capture(
            ws,
            f"chapter_end_after_{name}",
        )
        decisions.append(rec)

    return {
        "returned": False,
        "navigation": nav,
        "confirmation_open": {
            "events": open_ev,
            "capture": open_cap,
        },
        "decisions": decisions,
    }


def launch(b):
    exe = b.find_ppsspp_exe()

    cfg = OUT / "stage40z_fix1_append.ini"
    cfg.write_text(
        "[General]\n"
        "WindowX = 100\n"
        "WindowY = 100\n"
        "WindowWidth = 960\n"
        "WindowHeight = 544\n"
        "[Graphics]\n"
        "SoftwareRenderer = True\n"
        "ReplaceTextures = False\n"
        "SaveNewTextures = False\n",
        encoding="utf-8",
    )

    if PPSSPP_LOG.exists():
        PPSSPP_LOG.unlink()

    port = b.choose_free_port()

    p = subprocess.Popen([
        str(exe),
        "--loglevel=4",
        f"--log={PPSSPP_LOG}",
        "--windowed",
        f"--appendconfig={cfg}",
        f"--debugger={port}",
        str(SOURCE_ISO),
    ])

    return p


def cleanup(p, ws):
    if ws is not None:
        try:
            ws.close()
        except Exception:
            pass

    if p is not None:
        try:
            p.terminate()
            p.wait(timeout=5)
        except Exception:
            try:
                p.kill()
                p.wait(timeout=5)
            except Exception:
                pass


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

    report = {
        "stage": "40Z-fix1",
        "purpose":
            "Fix Stage40Z startup detection, then reproduce/resolve the later "
            "pause Down-input symptom and prove main-menu return if possible.",
        "previous_failure": {
            "cause":
                "Stage40Z waited for a MENUINT0.RAW log marker that was never "
                "emitted in this run and sent no input while waiting.",
            "effect":
                "The opening Bink sequence ran under software renderer for "
                "about 11 minutes; campaign navigation never started.",
            "evidence":
                "PPSSPP booted Stage40Y and the debugger was healthy, but "
                "menu_marker_count stayed 0 and BIAOFF campaign hook remained "
                "unloaded (0x0898E354 read 0x14A00007).",
            "stage40y_not_implicated":
                True,
        },
        "source_iso": str(SOURCE_ISO),
        "modifies_iso": False,
    }

    p = None
    ws = None

    try:
        if not SOURCE_ISO.exists():
            raise RuntimeError(
                f"Missing Stage40Y ISO: {SOURCE_ISO}"
            )

        _, b = load_helpers()

        p = launch(b)
        report["ppsspp_pid"] = p.pid

        hwnd = b.find_ppsspp_hwnd(30)
        if not hwnd:
            raise RuntimeError(
                "PPSSPP window did not appear"
            )

        actual_port = b.wait_for_actual_debugger_port(
            PPSSPP_LOG,
            30,
        )
        ws, host = b.connect_debugger(
            actual_port
        )

        report["debugger_host"] = host
        report["debugger_port"] = actual_port

        ready = wait_cpu_ready(ws)
        report["cpu_ready"] = ready
        if not ready["ready"]:
            raise RuntimeError(
                "CPU did not become ready"
            )

        # New startup oracle: actual Story renderer, with START pulses to skip
        # Bink/title sequences.
        main_menu = wait_menu_story_and_skip_intro(
            ws,
            timeout=150,
        )
        report["main_menu_entry"] = main_menu

        if not main_menu["ok"]:
            raise RuntimeError(
                "Could not reach proven Story renderer on the main menu"
            )

        campaign = enter_campaign(ws)
        report["campaign_entry"] = campaign

        if campaign.get("path") is None:
            raise RuntimeError(
                "Could not load campaign BIAOFF executable"
            )

        # Allow D0_0130 resources/font objects to settle. START pulses during
        # pause-open attempts also skip any first-mission movie.
        time.sleep(2.0)

        first_pause = open_pause(
            ws,
            "first_pause",
            attempts=16,
        )
        report["first_pause_open"] = first_pause

        if not first_pause["ok"]:
            raise RuntimeError(
                "Could not reach first Stage40Y pause menu"
            )

        report["campaign_invariants"] = verify_campaign(
            ws
        )

        if not report["campaign_invariants"]["ok"]:
            raise RuntimeError(
                "Stage40Y campaign hooks/fonts are not intact"
            )

        first_methods = test_methods(
            ws,
            "first",
        )
        report["first_pause_down_methods"] = first_methods

        first_method = first_methods["working_method"]

        if first_method is None:
            report["diagnosis"] = (
                "Even the first pause rejected all tested official input "
                "methods in this fresh run. The problem is debugger input "
                "injection/emulator state, not specifically the later Stage40Y "
                "pause state."
            )
            report["issue_resolved"] = False
            report["main_menu_returned"] = False
            report["completed"] = True

        else:
            reset = reset_top(
                ws,
                first_method,
                "first_reset",
            )
            report["first_pause_reset"] = reset

            if not reset["ok"]:
                raise RuntimeError(
                    "Could not reset first pause selection"
                )

            # Close pause and reproduce the handoff's gameplay + horizontal turn.
            button_hold(
                ws,
                "start",
                hold=0.16,
                settle=0.8,
            )

            report["gameplay_before_turn"] = capture(
                ws,
                "gameplay_before_turn",
            )

            report["turn_input"] = [
                request_safe(
                    ws,
                    "input.analog.send",
                    x=0.82,
                    y=0.0,
                )
            ]
            time.sleep(1.10)
            report["turn_input"].append(
                request_safe(
                    ws,
                    "input.analog.send",
                    x=0.0,
                    y=0.0,
                )
            )
            time.sleep(0.55)

            report["gameplay_after_turn"] = capture(
                ws,
                "gameplay_after_turn",
            )

            later_pause = open_pause(
                ws,
                "later_pause",
                attempts=6,
            )
            report["later_pause_open"] = later_pause

            if not later_pause["ok"]:
                raise RuntimeError(
                    "Could not reopen later pause"
                )

            release_buttons(ws)
            request_safe(
                ws,
                "input.analog.send",
                x=0.0,
                y=0.0,
            )
            time.sleep(0.25)

            later_methods = test_methods(
                ws,
                "later",
            )
            report["later_pause_down_methods"] = later_methods

            later_method = later_methods["working_method"]

            if later_method is None:
                report["diagnosis"] = (
                    "Reproduced the handoff symptom: first pause accepts Down, "
                    "but after resume + horizontal analog turn the reopened "
                    "pause rejects legacy press, explicit send/release, and both "
                    "analog vertical polarities. This is now a reproducible "
                    "later-pause input-path/state problem, not a localization "
                    "rendering failure."
                )
                report["issue_resolved"] = False
                report["main_menu_returned"] = False
                report["completed"] = True

            else:
                report["diagnosis"] = (
                    "Later pause accepted an explicit input method. The original "
                    "stuck selection was an input injection/timing/state issue, "
                    "not Stage40Y text/resource corruption."
                )

                reset2 = reset_top(
                    ws,
                    later_method,
                    "later_reset",
                )
                report["later_pause_reset"] = reset2

                if not reset2["ok"]:
                    raise RuntimeError(
                        "Later pause moved but could not reset selection"
                    )

                exit_result = exit_to_main_menu(
                    ws,
                    later_method,
                )
                report["exit_to_main_menu"] = exit_result
                report["main_menu_returned"] = (
                    exit_result["returned"]
                )
                report["issue_resolved"] = (
                    exit_result["returned"]
                )
                report["completed"] = True

    except Exception as e:
        report["exception"] = str(e)
        report["traceback"] = traceback.format_exc()
        report["completed"] = False

    finally:
        cleanup(p, ws)
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
            f"Stage40Z-fix1 technical failure. See {FAIL_ZIP}"
        )

    log("[Stage40Z-fix1] diagnostic complete")
    log(
        f"[Stage40Z-fix1] issue_resolved={report.get('issue_resolved')}"
    )
    log(
        f"[Stage40Z-fix1] main_menu_returned="
        f"{report.get('main_menu_returned')}"
    )
    log(
        f"[Stage40Z-fix1] Upload ZIP: {SUCCESS_ZIP}"
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

        if not REPORT_PATH.exists():
            REPORT_PATH.write_text(
                json.dumps(
                    {
                        "stage": "40Z-fix1",
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
            f"STAGE40Z-FIX1 FAILED: {FAIL_ZIP}",
            flush=True,
        )
        raise SystemExit(1)
