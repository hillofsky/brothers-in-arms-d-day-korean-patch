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

OUT = ROOT / "analysis" / "stage40z_fix2_pause_input"
LOG_DIR = ROOT / "log"

SUCCESS_ZIP = LOG_DIR / "bia_stage40z_fix2_upload.zip"
FAIL_ZIP = LOG_DIR / "fail_bia_stage40z_fix2_upload.zip"
REPORT_PATH = OUT / "stage40z_fix2_report.json"
PPSSPP_LOG = OUT / "stage40z_fix2_ppsspp.log"

# Proven Stage40O menu path.
MENU_LOOKUP = 0x08C7F2FC
MENU_RENDER_LOOKUP_RA = 0x08972368
MENU_STORY_CP = 0xD1A0       # 토 in 스토리
MENU_SKIRMISH_CP = 0xCEE4    # 커 in 스커미시
MENU_CONTINUE_CP = 0xACC4    # 계 in 계속
MENU_RENDER_CALL = 0x08972360
MENU_RENDER_WORD = 0x0E3310E4

# Proven Stage40R/Y campaign path.
CAMPAIGN_LOOKUP = 0x08C5CED4
CAMPAIGN_RENDER_CALL = 0x0898E354
CAMPAIGN_RENDER_WORD = 0x0E327D1A
CAMPAIGN_WIDTH_CALL1 = 0x08852B3C
CAMPAIGN_WIDTH_CALL2 = 0x088520C0
CAMPAIGN_WIDTH_WORD1 = 0x0E327D58
CAMPAIGN_WIDTH_WORD2 = 0x0E327D98
PAUSE_PROBE_CP = 0xCC55      # 챕 in 챕터 계속

# Proven Stage40Y first-mission resources.
FONT_OBJECTS = [
    0x09C1AF84,
    0x09C1D11C,
]
EXPECTED_GLYPH_COUNT = 847
EXPECTED_GLYPH_PTR = 0x09E6B020
ATLAS_ADDR = 0x09DF3020
ATLAS_BYTES = 0x20000
ATLAS_SHA1 = "b58e6ef06af9555a23d8be1f70a0e8d65b2ce4c6"

PAUSE_PAYLOAD_ADDR = 0x09E76FC4
PAUSE_PAYLOAD = "챕터 계속".encode("utf-8") + b"\x00"

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
        "phase": "press",
        **request_safe(
            ws,
            "input.buttons.send",
            buttons={button: True},
        ),
    })

    time.sleep(hold)

    events.append({
        "phase": "release",
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
            rgb[o + 1] = g
            rgb[o + 2] = b
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
        raw = read_ws(
            ws,
            addr,
            FB_BYTES,
        )

        im = rgb565_image(raw)
        path = OUT / f"{name}_{addr:08X}.png"
        im.save(path)

        visible = bytearray()

        for y in range(FB_H):
            off = y * FB_STRIDE * 2
            visible.extend(
                raw[off:off + FB_W * 2]
            )

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
        and abs(
            int(y["row"]) - int(x["row"])
        ) >= threshold
    )


def wait_title_story_preload(ws, timeout=150):
    """
    Stage40Z-fix1 showed that Story/토 can render while the title screen is
    still visible. We keep this as a PRELOAD oracle only, not as proof that
    the selectable main menu is already open.
    """
    arm = arm_lookup(
        ws,
        MENU_LOOKUP,
        MENU_STORY_CP,
        MENU_RENDER_LOOKUP_RA,
    )

    events = []
    end = time.time() + timeout
    next_start = 0.0

    while time.time() < end:
        if wait_break(ws, timeout=0.08):
            remove_bp(ws, MENU_LOOKUP)
            resume_cpu(ws)
            time.sleep(0.35)

            return {
                "ok": True,
                "arm": arm,
                "events": events,
                "capture": capture(
                    ws,
                    "title_story_preload",
                ),
            }

        now = time.time()

        if now >= next_start:
            events.append(
                button_hold(
                    ws,
                    "start",
                    hold=0.14,
                    settle=0.10,
                )
            )
            next_start = time.time() + 1.35

        time.sleep(0.03)

    remove_bp(ws, MENU_LOOKUP)
    resume_cpu(ws)

    return {
        "ok": False,
        "arm": arm,
        "events": events,
        "capture": capture(
            ws,
            "title_story_preload_timeout",
        ),
    }


def enter_selectable_main_menu(ws, attempts=5):
    """
    Exact Stage40G-style proof:
    arm the unselected Skirmish character BEFORE title->menu Start.
    A hit means the first selectable-menu render really happened.
    """
    records = []

    for i in range(attempts):
        arm = arm_lookup(
            ws,
            MENU_LOOKUP,
            MENU_SKIRMISH_CP,
            MENU_RENDER_LOOKUP_RA,
        )

        ev = button_hold(
            ws,
            "start",
            hold=0.16,
            settle=0.10,
        )

        hit = wait_break(
            ws,
            timeout=4.5,
        )

        rec = {
            "attempt": i + 1,
            "arm": arm,
            "start": ev,
            "hit": hit,
        }

        if hit:
            remove_bp(ws, MENU_LOOKUP)
            resume_cpu(ws)
            time.sleep(0.55)

            rec["capture"] = capture(
                ws,
                "selectable_main_menu",
            )
            records.append(rec)

            return {
                "ok": True,
                "records": records,
            }

        remove_bp(ws, MENU_LOOKUP)
        resume_cpu(ws)
        time.sleep(0.5)

        rec["capture"] = capture(
            ws,
            f"selectable_menu_try_{i+1}",
        )
        records.append(rec)

    return {
        "ok": False,
        "records": records,
    }


def enter_story_continue(ws):
    """
    From confirmed selectable main menu:
      Cross -> Story submenu
      wait for Korean Continue/계 renderer
      Cross -> Continue
    """
    result = {}

    result["story_cross"] = button_hold(
        ws,
        "cross",
        hold=0.16,
        settle=0.18,
    )

    arm = arm_lookup(
        ws,
        MENU_LOOKUP,
        MENU_CONTINUE_CP,
        MENU_RENDER_LOOKUP_RA,
    )

    hit = wait_break(
        ws,
        timeout=6.0,
    )

    result["continue_renderer_hit"] = hit

    if hit:
        remove_bp(ws, MENU_LOOKUP)
        resume_cpu(ws)
        time.sleep(0.45)
        result["story_submenu_capture"] = capture(
            ws,
            "story_submenu",
        )
    else:
        remove_bp(ws, MENU_LOOKUP)
        resume_cpu(ws)
        result["story_submenu_capture"] = capture(
            ws,
            "story_submenu_no_probe",
        )

    result["continue_cross"] = button_hold(
        ws,
        "cross",
        hold=0.16,
        settle=0.45,
    )

    return result


def wait_campaign_module(ws, timeout=90):
    end = time.time() + timeout
    pulses = []
    samples = []

    while time.time() < end:
        try:
            word = read_u32(
                ws,
                CAMPAIGN_RENDER_CALL,
            )

            if len(samples) < 50:
                samples.append(
                    f"0x{word:08X}"
                )

            if word == CAMPAIGN_RENDER_WORD:
                return {
                    "ok": True,
                    "word": f"0x{word:08X}",
                    "samples": samples,
                    "start_pulse_count": len(pulses),
                }

        except Exception as e:
            if len(samples) < 50:
                samples.append(
                    "ERR:" + str(e)
                )

        pulses.append(
            button_hold(
                ws,
                "start",
                hold=0.12,
                settle=0.08,
            )
        )

        time.sleep(0.55)

    return {
        "ok": False,
        "samples": samples,
        "start_pulse_count": len(pulses),
    }


def mission_state(ws):
    fonts = []

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

        fonts.append({
            "object": f"0x{addr:08X}",
            "count": count,
            "ptr": f"0x{ptr:08X}",
            "ok": (
                count == EXPECTED_GLYPH_COUNT
                and ptr == EXPECTED_GLYPH_PTR
            ),
        })

    atlas = read_ws(
        ws,
        ATLAS_ADDR,
        ATLAS_BYTES,
    )
    atlas_sha = hashlib.sha1(
        atlas
    ).hexdigest()

    payload = read_ws(
        ws,
        PAUSE_PAYLOAD_ADDR,
        len(PAUSE_PAYLOAD),
    )

    return {
        "fonts": fonts,
        "atlas_sha1": atlas_sha,
        "atlas_ok": atlas_sha == ATLAS_SHA1,
        "pause_payload_hex": payload.hex(),
        "pause_payload_ok": payload == PAUSE_PAYLOAD,
        "ready": (
            all(x["ok"] for x in fonts)
            and atlas_sha == ATLAS_SHA1
            and payload == PAUSE_PAYLOAD
        ),
    }


def wait_first_mission_resources(ws, timeout=150):
    """
    Fix1 tried pause immediately after BIAOFF loaded. The uploaded result proved
    that was too early: both Stage40Y font objects were still 0/NULL.

    Wait for the actual D0_0130 Stage40Y resources:
      both font objects = 847 / 0x09E6B020
      atlas SHA matches production
      챕터 계속 payload is exact
    while START pulses skip intro movie/title material.
    """
    end = time.time() + timeout
    samples = []
    pulse_count = 0

    while time.time() < end:
        try:
            s = mission_state(ws)

            if len(samples) < 40:
                samples.append(s)

            if s["ready"]:
                release_buttons(ws)
                request_safe(
                    ws,
                    "input.analog.send",
                    x=0.0,
                    y=0.0,
                )
                time.sleep(0.75)

                return {
                    "ok": True,
                    "final": s,
                    "samples": samples,
                    "start_pulse_count": pulse_count,
                    "capture": capture(
                        ws,
                        "first_mission_resources_ready",
                    ),
                }

        except Exception as e:
            if len(samples) < 40:
                samples.append({
                    "error": str(e),
                })

        button_hold(
            ws,
            "start",
            hold=0.12,
            settle=0.08,
        )
        pulse_count += 1
        time.sleep(0.6)

    return {
        "ok": False,
        "samples": samples,
        "start_pulse_count": pulse_count,
        "capture": capture(
            ws,
            "first_mission_resources_timeout",
        ),
    }


def verify_campaign_invariants(ws):
    s = mission_state(ws)

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
        "mission_state": s,
    }

    result["ok"] = (
        result["renderer_call"]["actual"]
        == result["renderer_call"]["expected"]
        and result["width_call1"]["actual"]
        == result["width_call1"]["expected"]
        and result["width_call2"]["actual"]
        == result["width_call2"]["expected"]
        and s["ready"]
    )

    return result


def open_pause(ws, prefix, attempts=10):
    """
    Only an actual U+CC55 lookup counts. No color/VRAM fallback: fix1 showed
    that Bink frames can contain strong red rows and create false positives.
    """
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
            settle=0.08,
        )

        hit = wait_break(
            ws,
            timeout=3.0,
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
            time.sleep(0.55)

            rec["capture"] = capture(
                ws,
                f"{prefix}_opened",
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

        time.sleep(0.45)
        rec["capture"] = capture(
            ws,
            f"{prefix}_try_{i+1}",
        )
        records.append(rec)

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
            settle=0.50,
        )

    if method["kind"] == "analog":
        y = method["y"]

        if direction == "up":
            y = -y

        return analog_pulse(
            ws,
            y,
            hold=0.28,
            settle=0.50,
        )

    raise RuntimeError("Unknown input method")


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

    # Pause toggle as reset fallback.
    button_hold(
        ws,
        "start",
        hold=0.16,
        settle=0.55,
    )
    button_hold(
        ws,
        "start",
        hold=0.16,
        settle=0.55,
    )

    c2 = capture(
        ws,
        prefix + "_toggle",
    )

    return {
        "ok": (
            c2["underline"].get("found")
            and 60 <= int(c2["underline"]["row"]) <= 82
        ),
        "via": "pause_toggle",
        "capture": c2,
    }


def wait_menu_module(ws, timeout=25):
    end = time.time() + timeout
    samples = []

    while time.time() < end:
        try:
            word = read_u32(
                ws,
                MENU_RENDER_CALL,
            )

            if len(samples) < 40:
                samples.append(
                    f"0x{word:08X}"
                )

            if word == MENU_RENDER_WORD:
                return {
                    "ok": True,
                    "word": f"0x{word:08X}",
                    "samples": samples,
                }

        except Exception as e:
            if len(samples) < 40:
                samples.append(
                    "ERR:" + str(e)
                )

        time.sleep(0.20)

    return {
        "ok": False,
        "samples": samples,
    }


def wait_story_renderer_no_input(ws, timeout=15):
    arm = arm_lookup(
        ws,
        MENU_LOOKUP,
        MENU_STORY_CP,
        MENU_RENDER_LOOKUP_RA,
    )

    hit = wait_break(
        ws,
        timeout=timeout,
    )

    result = {
        "arm": arm,
        "hit": hit,
    }

    remove_bp(
        ws,
        MENU_LOOKUP,
    )

    if hit:
        resume_cpu(ws)
        time.sleep(0.45)
        result["capture"] = capture(
            ws,
            "returned_main_menu",
        )

    return result


def prove_main_menu_return(ws):
    module = wait_menu_module(
        ws,
        timeout=20,
    )

    if not module["ok"]:
        return {
            "ok": False,
            "module": module,
        }

    story = wait_story_renderer_no_input(
        ws,
        timeout=15,
    )

    return {
        "ok": story.get("hit", False),
        "module": module,
        "story": story,
    }


def exit_to_main_menu(ws, method):
    nav = []

    # Start at 챕터 계속; Chapter End is four rows down.
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

    open_ev = button_hold(
        ws,
        "cross",
        hold=0.16,
        settle=0.55,
    )

    open_cap = capture(
        ws,
        "chapter_end_confirmation",
    )

    decisions = []

    for name, moves in [
        ("default", []),
        ("down", ["down"]),
        ("up", ["up"]),
        ("left", ["left"]),
        ("right", ["right"]),
    ]:
        if name != "default":
            # Previous attempt likely cancelled: reopen confirmation.
            button_hold(
                ws,
                "cross",
                hold=0.16,
                settle=0.50,
            )

        move_events = []

        for b in moves:
            move_events.append({
                "button": b,
                "events": button_hold(
                    ws,
                    b,
                    hold=0.18,
                    settle=0.22,
                ),
            })

        confirm = button_hold(
            ws,
            "cross",
            hold=0.16,
            settle=0.22,
        )

        returned = prove_main_menu_return(
            ws
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

    cfg = OUT / "stage40z_fix2_append.ini"
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

    return subprocess.Popen([
        str(exe),
        "--loglevel=4",
        f"--log={PPSSPP_LOG}",
        "--windowed",
        f"--appendconfig={cfg}",
        f"--debugger={port}",
        str(SOURCE_ISO),
    ])


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
        for p in sorted(
            OUT.rglob("*")
        ):
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
        "stage": "40Z-fix2",
        "purpose":
            "Correct the two remaining Stage40Z harness mistakes: distinguish "
            "title-screen Story preload from the selectable menu, and wait for "
            "the actual D0_0130 Stage40Y font/atlas/payload resources before "
            "attempting the first pause.",
        "previous_fix1_result": {
            "selectable_menu_not_proven":
                "Story/토 breakpoint fired while VRAM still showed the title screen.",
            "campaign_module_did_load":
                "Fallback path reached BIAOFF and 0x0898E354 became 0x0E327D1A.",
            "pause_test_started_too_early":
                "Both first-mission font objects were still count=0, ptr=0 when "
                "fix1 declared a visual pause fallback.",
            "visual_false_positive":
                "Bink/movie frames contained strong red scanlines, so red-line "
                "detection cannot be used to prove a pause before U+CC55 hits.",
            "stage40y_regression_proven": False,
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

        hwnd = b.find_ppsspp_hwnd(
            30
        )

        if not hwnd:
            raise RuntimeError(
                "PPSSPP window did not appear"
            )

        actual_port = (
            b.wait_for_actual_debugger_port(
                PPSSPP_LOG,
                30,
            )
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

        preload = wait_title_story_preload(
            ws,
            timeout=150,
        )
        report["title_story_preload"] = preload

        if not preload["ok"]:
            raise RuntimeError(
                "Could not reach menu Story preload"
            )

        selectable = enter_selectable_main_menu(
            ws,
            attempts=5,
        )
        report["selectable_main_menu"] = selectable

        if not selectable["ok"]:
            raise RuntimeError(
                "Could not prove selectable main menu via first-frame Skirmish renderer"
            )

        story = enter_story_continue(
            ws
        )
        report["story_continue"] = story

        if not story["continue_renderer_hit"]:
            raise RuntimeError(
                "Story submenu did not render Korean Continue"
            )

        campaign = wait_campaign_module(
            ws,
            timeout=90,
        )
        report["campaign_module"] = campaign

        if not campaign["ok"]:
            raise RuntimeError(
                "Continue did not load the Stage40R/Y campaign executable"
            )

        resources = wait_first_mission_resources(
            ws,
            timeout=150,
        )
        report["first_mission_resources"] = resources

        if not resources["ok"]:
            raise RuntimeError(
                "Stage40Y first-mission font/atlas/payload resources never became ready"
            )

        report["campaign_invariants"] = (
            verify_campaign_invariants(
                ws
            )
        )

        if not report["campaign_invariants"]["ok"]:
            raise RuntimeError(
                "Stage40Y campaign invariants failed after first-mission resource initialization"
            )

        first_pause = open_pause(
            ws,
            "first_pause",
            attempts=10,
        )
        report["first_pause_open"] = first_pause

        if not first_pause["ok"]:
            raise RuntimeError(
                "Could not prove first pause via U+CC55 renderer lookup"
            )

        first_methods = test_methods(
            ws,
            "first",
        )
        report["first_pause_down_methods"] = first_methods

        first_method = first_methods["working_method"]

        if first_method is None:
            report["diagnosis"] = (
                "The verified first pause rejected every tested debugger input "
                "method. This points to PPSSPP input injection/state rather than "
                "the later-pause-only symptom."
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
                    "Could not reset first pause selection to Chapter Continue"
                )

            button_hold(
                ws,
                "start",
                hold=0.16,
                settle=0.75,
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
                    "Could not prove later pause via U+CC55 renderer lookup"
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

            later_method = later_methods[
                "working_method"
            ]

            if later_method is None:
                report["diagnosis"] = (
                    "Reproduced with both pauses proven by the renderer: the "
                    "initial pause accepts Down, but after resume + horizontal "
                    "analog turn the reopened pause rejects every tested legacy, "
                    "explicit send/release, and analog vertical input method."
                )
                report["issue_resolved"] = False
                report["main_menu_returned"] = False
                report["completed"] = True

            else:
                report["diagnosis"] = (
                    "The proven later pause accepts an explicit input method. "
                    "The original stuck selection was debugger injection/timing/"
                    "state related, not Stage40Y localization corruption."
                )

                reset2 = reset_top(
                    ws,
                    later_method,
                    "later_reset",
                )
                report["later_pause_reset"] = reset2

                if not reset2["ok"]:
                    raise RuntimeError(
                        "Later pause moved but could not reset to Chapter Continue"
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
        cleanup(
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

    make_zip(
        target
    )

    if not report.get("completed"):
        raise RuntimeError(
            f"Stage40Z-fix2 technical failure. See {FAIL_ZIP}"
        )

    log("[Stage40Z-fix2] diagnostic complete")
    log(
        f"[Stage40Z-fix2] issue_resolved={report.get('issue_resolved')}"
    )
    log(
        f"[Stage40Z-fix2] main_menu_returned={report.get('main_menu_returned')}"
    )
    log(
        f"[Stage40Z-fix2] Upload ZIP: {SUCCESS_ZIP}"
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
                        "stage": "40Z-fix2",
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
            make_zip(
                FAIL_ZIP
            )
        except Exception:
            pass

        print(
            traceback.format_exc(),
            flush=True,
        )
        print(
            f"STAGE40Z-FIX2 FAILED: {FAIL_ZIP}",
            flush=True,
        )
        raise SystemExit(1)
