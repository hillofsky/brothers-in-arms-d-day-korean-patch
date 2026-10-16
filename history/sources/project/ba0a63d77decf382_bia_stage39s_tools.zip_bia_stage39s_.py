#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import math
import os
import shutil
import struct
import subprocess
import sys
import time
import traceback
import zipfile
from pathlib import Path

ROOT = Path(r"PROJECT_ROOT")
BASE_TOOLS = ROOT / "bia_stage39b_tools"

SOURCE_ISO = ROOT / "BIA_STAGE39F_CORRECT_NARROW_METADATA_TEST.iso"
TEST_ISO = ROOT / "BIA_STAGE39S_RENDER_UTF8_TEST.iso"

OUT = ROOT / "analysis" / "stage39s_renderer_utf8_fix"
LOG_DIR = ROOT / "log"

SUCCESS_ZIP = LOG_DIR / "bia_stage39s_upload.zip"
FAIL_ZIP = LOG_DIR / "fail_bia_stage39s_upload.zip"
REPORT_PATH = OUT / "stage39s_report.json"
PPSSPP_LOG = OUT / "stage39s_ppsspp.log"

SCRIPT_DIR = Path(__file__).resolve().parent
HELPER_PATH = SCRIPT_DIR / "utf8_widened_renderer_helper.bin"

TARGET_PRX = ["PSP_GAME", "USRDIR", "SYSTEM", "BIAON.PRX"]
SECTOR = 2048

EXPECTED_ORIGINAL_BIAON_SHA1 = "8c7033ca15103fa51afa9c7ec61f37c531d07ede"

# ELF .text: file off 0x80, vaddr 0.
ELF_TEXT_FILE_BIAS = 0x80

# Real visible renderer from Stage39R:
#   PRX 0x16E360  jal original Unicode lookup
#   runtime        0x08972360
RENDER_LOOKUP_CALL_VA = 0x0016E360
RENDER_LOOKUP_CALL_FILE = RENDER_LOOKUP_CALL_VA + ELF_TEXT_FILE_BIAS
RENDER_LOOKUP_CALL_RUNTIME = 0x08804000 + RENDER_LOOKUP_CALL_VA

EXPECTED_RENDER_JAL = bytes.fromhex("bfec110c")  # jal 0x47B2FC
PATCHED_RENDER_JAL = bytes.fromhex("e400130c")   # jal 0x4C0390

# Diagnostic helper replaces the unused-for-this-path C-JIS branch body.
HELPER_VA = 0x004C0390
HELPER_FILE = HELPER_VA + ELF_TEXT_FILE_BIAS
HELPER_RUNTIME = 0x08804000 + HELPER_VA
HELPER_ORIGINAL_SHA1 = "588ac2a13e15bb85145e24dd5fad9880f0c49d93"
HELPER_PATCH_SHA1 = "aeadae01df32c385fb5b149ed83144522d4527f2"

ORIGINAL_LOOKUP_RUNTIME = 0x08C7F2FC
DRAW_HELPER = 0x08AF6324
VISIBLE_RENDER_RA = 0x089726C0

# Correct Stage39F source.
DISPLAY1_ADDR = 0x093B1B40
DISPLAY2_ADDR = 0x093B1BF0
META1_ADDR = 0x095EC774
META2_ADDR = 0x095F1758
UTF8 = "스토리".encode("utf-8")
UTF8_NUL = UTF8 + b"\x00"

EXPECTED_META1 = (DISPLAY1_ADDR, 10, 10)
EXPECTED_META2 = (DISPLAY2_ADDR, 10, 10)

# Stage39R exact visible widened-string buffer.
VISIBLE_WIDE_BUF = 0x08E4E85C
WIDENED_UTF8 = b"".join(bytes((x,0)) for x in UTF8)

# Proven selectable-menu anchors.
MAINMENU_OPTIONS_ADDR = 0x08E41660
MAINMENU_PROFILE_ADDR = 0x08E41680
MAINMENU_STORY_ADDR = 0x08E416C0

UTF16_OPTIONS = "Options".encode("utf-16le")
UTF16_PROFILE = "Profile".encode("utf-16le")
UTF16_STORY = "스토리".encode("utf-16le")

MENU_OPEN_MARKER = (
    "sceIoOpen(disc0:/PSP_GAME/USRDIR/SYSTEM/RAWFILES/MENUINT0.RAW"
)

# Production glyph154 "스" pixel-space UV at helper entry:
# u0=1.00390625, v0=1.501953125, u1=1.13671875, v1=1.564453125
# widths=128, heights=256
EXPECTED_S_UV_FLOOR = (128, 384, 145, 400)

RAM_START = 0x08800000
RAM_END = 0x0A800000


def log(msg):
    print(msg, flush=True)


def sha1(data):
    return hashlib.sha1(data).hexdigest()


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


def find_callable(objects, name):
    for obj in objects:
        if obj is not None and hasattr(obj, name):
            fn = getattr(obj, name)
            if callable(fn):
                return fn
    return None


# ---------------------------------------------------------------------------
# Self-contained ISO9660 same-size file patcher.
# ---------------------------------------------------------------------------

def _norm_iso_name(name):
    s = name.decode("ascii", errors="replace")
    if s in ("\x00", "\x01"):
        return s
    if ";" in s:
        s = s.split(";", 1)[0]
    return s.upper()


def _dir_records(f, extent, size):
    f.seek(extent * SECTOR)
    data = f.read(size)
    pos = 0

    while pos < len(data):
        rec_len = data[pos]
        if rec_len == 0:
            pos = ((pos // SECTOR) + 1) * SECTOR
            continue

        rec = data[pos:pos+rec_len]
        if len(rec) < 34:
            break

        yield {
            "extent": struct.unpack_from("<I", rec, 2)[0],
            "size": struct.unpack_from("<I", rec, 10)[0],
            "flags": rec[25],
            "is_dir": bool(rec[25] & 2),
            "name": _norm_iso_name(
                rec[33:33+rec[32]]
            ),
        }
        pos += rec_len


def iso_find(path, parts):
    parts = [x.upper() for x in parts]

    with path.open("rb") as f:
        f.seek(16 * SECTOR)
        pvd = f.read(SECTOR)

        if pvd[0] != 1 or pvd[1:6] != b"CD001":
            raise RuntimeError("ISO PVD not found")

        root_len = pvd[156]
        root = pvd[156:156+root_len]

        current = {
            "extent": struct.unpack_from("<I", root, 2)[0],
            "size": struct.unpack_from("<I", root, 10)[0],
            "is_dir": True,
        }

        for i, want in enumerate(parts):
            found = None
            for rec in _dir_records(
                f, current["extent"], current["size"]
            ):
                if rec["name"] == want:
                    found = rec
                    break

            if found is None:
                raise FileNotFoundError("/".join(parts))

            if i != len(parts)-1 and not found["is_dir"]:
                raise RuntimeError(
                    f"Not a directory: {want}"
                )
            current = found

        return current


def iso_read(path, parts):
    rec = iso_find(path, parts)
    with path.open("rb") as f:
        f.seek(rec["extent"] * SECTOR)
        data = f.read(rec["size"])
    return rec, data


def iso_overwrite_same_size(path, parts, data):
    rec = iso_find(path, parts)

    if len(data) != rec["size"]:
        raise RuntimeError(
            f"Same-size overwrite required: {len(data)} != {rec['size']}"
        )

    with path.open("r+b") as f:
        f.seek(rec["extent"] * SECTOR)
        f.write(data)
        f.flush()
        os.fsync(f.fileno())

    _, rb = iso_read(path, parts)
    if rb != data:
        raise RuntimeError("ISO read-back mismatch")


# ---------------------------------------------------------------------------
# Patch build.
# ---------------------------------------------------------------------------

def build_iso():
    if not SOURCE_ISO.exists():
        raise RuntimeError(f"Missing source ISO: {SOURCE_ISO}")

    helper = HELPER_PATH.read_bytes()
    if sha1(helper) != HELPER_PATCH_SHA1:
        raise RuntimeError("Helper blob SHA1 mismatch")

    _, prx = iso_read(SOURCE_ISO, TARGET_PRX)

    if sha1(prx) != EXPECTED_ORIGINAL_BIAON_SHA1:
        raise RuntimeError(
            f"Unexpected source BIAON SHA1: {sha1(prx)}"
        )

    if (
        prx[
            RENDER_LOOKUP_CALL_FILE:
            RENDER_LOOKUP_CALL_FILE+4
        ] != EXPECTED_RENDER_JAL
    ):
        raise RuntimeError("Renderer JAL bytes mismatch")

    original_helper = prx[
        HELPER_FILE:
        HELPER_FILE + len(helper)
    ]
    if sha1(original_helper) != HELPER_ORIGINAL_SHA1:
        raise RuntimeError(
            "Original helper-overwrite region mismatch"
        )

    patched = bytearray(prx)
    patched[
        RENDER_LOOKUP_CALL_FILE:
        RENDER_LOOKUP_CALL_FILE+4
    ] = PATCHED_RENDER_JAL

    patched[
        HELPER_FILE:
        HELPER_FILE+len(helper)
    ] = helper

    if TEST_ISO.exists():
        TEST_ISO.unlink()

    shutil.copy2(SOURCE_ISO, TEST_ISO)
    iso_overwrite_same_size(
        TEST_ISO, TARGET_PRX, bytes(patched)
    )

    _, rb = iso_read(TEST_ISO, TARGET_PRX)

    return {
        "source_biaon_sha1": sha1(prx),
        "patched_biaon_sha1": sha1(rb),
        "renderer_call_file_offset":
            f"0x{RENDER_LOOKUP_CALL_FILE:X}",
        "renderer_call_before":
            EXPECTED_RENDER_JAL.hex(),
        "renderer_call_after":
            rb[
                RENDER_LOOKUP_CALL_FILE:
                RENDER_LOOKUP_CALL_FILE+4
            ].hex(),
        "helper_file_offset":
            f"0x{HELPER_FILE:X}",
        "helper_size": len(helper),
        "helper_sha1": sha1(helper),
        "iso_readback_ok": rb == bytes(patched),
    }


# ---------------------------------------------------------------------------
# Runtime.
# ---------------------------------------------------------------------------

def read_ws(ws, address, size):
    r = ws.request(
        "memory.read",
        timeout=10,
        address=address,
        size=size,
    )
    return base64.b64decode(r["base64"])


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


def floor_tuple(vals):
    if vals is None:
        return None
    return tuple(
        int(math.floor(x + 1e-5))
        for x in vals
    )


def resume(ws):
    try:
        ws.request("cpu.resume", timeout=0.5)
    except Exception:
        pass


def wait_pause(ws, timeout=10):
    end = time.time() + timeout
    last = None

    while time.time() < end:
        try:
            last = ws.request(
                "cpu.status", timeout=2
            )
            if last.get("stepping", False):
                return last
        except Exception:
            pass
        time.sleep(0.02)

    return None


def remove_bp(ws, addr):
    try:
        ws.request(
            "cpu.breakpoint.remove",
            timeout=5,
            address=addr,
        )
    except Exception:
        pass


def wait_menu_resource(ws, timeout=180):
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


def wait_source(ws, timeout=60):
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


def menu_anchors(ws):
    try:
        opt = read_ws(
            ws,
            MAINMENU_OPTIONS_ADDR,
            len(UTF16_OPTIONS)+2,
        )
        pro = read_ws(
            ws,
            MAINMENU_PROFILE_ADDR,
            len(UTF16_PROFILE)+2,
        )
        sto = read_ws(
            ws,
            MAINMENU_STORY_ADDR,
            len(UTF16_STORY)+2,
        )
    except Exception as e:
        return {"ok": False, "error": str(e)}

    return {
        "ok": (
            opt.startswith(UTF16_OPTIONS+b"\x00\x00")
            and pro.startswith(UTF16_PROFILE+b"\x00\x00")
            and sto.startswith(UTF16_STORY+b"\x00\x00")
        ),
        "options_hex": opt.hex(),
        "profile_hex": pro.hex(),
        "story_hex": sto.hex(),
    }


def enter_main_menu(ws):
    time.sleep(2.5)

    attempts = []

    for attempt in (1,2):
        before = menu_anchors(ws)
        if before.get("ok"):
            return {
                "confirmed": True,
                "anchors": before,
                "attempts": attempts,
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

        start = time.time()

        while time.time()-start < 14:
            a = menu_anchors(ws)
            if a.get("ok"):
                attempts.append({
                    "attempt": attempt,
                    "sent": sent,
                    "elapsed": time.time()-start,
                })
                return {
                    "confirmed": True,
                    "anchors": a,
                    "attempts": attempts,
                }

            if (
                attempt == 1
                and time.time()-start >= 8
            ):
                break

            time.sleep(0.12)

        attempts.append({
            "attempt": attempt,
            "sent": sent,
            "error": None if sent else err,
        })

    return {
        "confirmed": False,
        "anchors": menu_anchors(ws),
        "attempts": attempts,
    }


def capture(local_mod, b, hwnd, label):
    fn = find_callable(
        [b, getattr(local_mod, "s39", None), local_mod],
        "capture",
    )
    helper = BASE_TOOLS / "capture_ppsspp.ps1"
    path = OUT / f"stage39s_{label}.png"

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


def trace_decoder(ws):
    """
    Visible Stage39R string:
      0x08E4E85C = 00EC 008A 00A4 ...

    Catch helper at byte EC, then the original lookup at decoded U+C2A4.
    """
    remove_bp(ws, HELPER_RUNTIME)

    ws.request(
        "cpu.breakpoint.add",
        timeout=10,
        address=HELPER_RUNTIME,
        enabled=True,
        log=False,
        condition="a1 == 0xEC",
    )

    resume(ws)
    p = wait_pause(ws, timeout=30)

    if p is None:
        remove_bp(ws, HELPER_RUNTIME)
        return {
            "helper_hit": False,
        }

    uints, _ = parse_regs(
        ws.request(
            "cpu.getAllRegs",
            timeout=10,
        )
    )

    helper_hit = {
        "helper_hit": True,
        "pc": f"0x{uints.get('pc',0):08X}",
        "a0_page_table":
            f"0x{uints.get('a0',0):08X}",
        "a1_first_byte":
            f"0x{uints.get('a1',0):04X}",
        "s0_string_ptr":
            f"0x{uints.get('s0',0):08X}",
        "s4_total_elements":
            uints.get("s4"),
        "s5_consumed_before":
            uints.get("s5"),
        "visible_buffer_hex":
            read_ws(
                ws,
                uints.get("s0",VISIBLE_WIDE_BUF),
                20,
            ).hex(),
    }

    remove_bp(ws, HELPER_RUNTIME)

    ws.request(
        "cpu.breakpoint.add",
        timeout=10,
        address=ORIGINAL_LOOKUP_RUNTIME,
        enabled=True,
        log=False,
        condition="a1 == 0xC2A4",
    )

    resume(ws)
    p2 = wait_pause(ws, timeout=10)

    if p2 is not None:
        r2, _ = parse_regs(
            ws.request(
                "cpu.getAllRegs",
                timeout=10,
            )
        )
        helper_hit["decoded_lookup"] = {
            "hit": True,
            "a1": f"0x{r2.get('a1',0):04X}",
            "s0_after_preconsume":
                f"0x{r2.get('s0',0):08X}",
            "s5_after_preconsume":
                r2.get("s5"),
            "ra":
                f"0x{r2.get('ra',0):08X}",
        }
    else:
        helper_hit["decoded_lookup"] = {
            "hit": False,
        }

    remove_bp(ws, ORIGINAL_LOOKUP_RUNTIME)
    resume(ws)

    return helper_hit


def trace_visible_korean_draw(ws):
    """
    Production glyph154 "스" should now reach the exact visible renderer draw.
    Require both:
      RA = wide renderer
      floor UV = (128,384,145,400)
    and record s0, which should be within the old widened Story buffer.
    """
    remove_bp(ws, DRAW_HELPER)

    ws.request(
        "cpu.breakpoint.add",
        timeout=10,
        address=DRAW_HELPER,
        enabled=True,
        log=False,
    )

    end = time.time() + 35
    seen = 0
    nearest = []

    while time.time() < end and seen < 1000:
        resume(ws)
        p = wait_pause(
            ws,
            timeout=min(5,max(.2,end-time.time())),
        )
        if p is None:
            continue

        uints, floats = parse_regs(
            ws.request(
                "cpu.getAllRegs",
                timeout=10,
            )
        )
        seen += 1

        if uints.get("ra") != VISIBLE_RENDER_RA:
            continue

        uv = tuple_f(
            floats,
            ["f16","f17","f18","f19"],
        )
        q = floor_tuple(uv)

        if q is None:
            continue

        dist = sum(
            abs(a-b)
            for a,b in zip(
                q, EXPECTED_S_UV_FLOOR
            )
        )

        nearest.append({
            "uv": uv,
            "floor": q,
            "distance": dist,
            "s0": f"0x{uints.get('s0',0):08X}",
        })
        nearest = sorted(
            nearest,
            key=lambda x:x["distance"],
        )[:20]

        if q == EXPECTED_S_UV_FLOOR:
            remove_bp(ws, DRAW_HELPER)
            return {
                "matched": True,
                "seen": seen,
                "uv": uv,
                "uv_floor": q,
                "s0":
                    f"0x{uints.get('s0',0):08X}",
                "s4_total":
                    uints.get("s4"),
                "s5_index":
                    uints.get("s5"),
                "texture":
                    f"0x{uints.get('a1',0):08X}",
                "nearest": nearest,
            }

    remove_bp(ws, DRAW_HELPER)

    return {
        "matched": False,
        "seen": seen,
        "nearest": nearest,
    }


def runtime(local_mod, b):
    exe = b.find_ppsspp_exe()

    cfg = OUT / "stage39s_append.ini"
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
        str(TEST_ISO),
    ]

    proc = subprocess.Popen(cmd)
    cleanup = b.register_ppsspp_auto_close(proc)

    result = {
        "pid": proc.pid,
        "normal_jit": True,
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
            result["debugger_host"] = host
            result["debugger_port"] = actual_port

            result["runtime_patch_bytes"] = {
                "renderer_jal":
                    read_ws(
                        ws,
                        RENDER_LOOKUP_CALL_RUNTIME,
                        4,
                    ).hex(),
                "helper_sha1":
                    sha1(
                        read_ws(
                            ws,
                            HELPER_RUNTIME,
                            len(HELPER_PATH.read_bytes()),
                        )
                    ),
            }

            menu = wait_menu_resource(ws)
            result["menu_resource_open"] = menu
            if not menu["opened"]:
                raise RuntimeError("MENUINT0.RAW did not open")

            source = wait_source(ws)
            result["source_resident"] = source
            if not source.get("ok"):
                raise RuntimeError(
                    "Correct Stage39F source did not become resident"
                )

            state = enter_main_menu(ws)
            result["main_menu_state"] = state
            if not state.get("confirmed"):
                raise RuntimeError(
                    "Selectable main menu did not appear"
                )

            result["visible_buffer_before_trace"] = {
                "address":
                    f"0x{VISIBLE_WIDE_BUF:08X}",
                "bytes":
                    read_ws(
                        ws,
                        VISIBLE_WIDE_BUF,
                        len(WIDENED_UTF8)+2,
                    ).hex(),
                "expected_widened_prefix":
                    WIDENED_UTF8.hex(),
            }

            result["decoder_trace"] = trace_decoder(ws)

            # Let a full frame draw with the renderer fix.
            time.sleep(1.0)

            result["visible_korean_draw"] = (
                trace_visible_korean_draw(ws)
            )
            resume(ws)

            time.sleep(0.5)
            result["menu_capture"] = capture(
                local_mod,
                b,
                hwnd,
                "main_menu",
            )

            result["completed"] = (
                result["decoder_trace"].get(
                    "helper_hit", False
                )
                and result["decoder_trace"].get(
                    "decoded_lookup", {}
                ).get("hit", False)
                and result["visible_korean_draw"].get(
                    "matched", False
                )
            )

        finally:
            try:
                ws.close()
            except Exception:
                pass

    finally:
        try:
            cleanup()
            result["ppsspp_closed"] = True
        except Exception as e:
            result["ppsspp_close_error"] = str(e)

    return result


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

    local_mod, b = load_helpers()

    report = {
        "stage": "39S",
        "purpose":
            "Diagnostic renderer-side UTF-8 decoder: decode the exact widened "
            "UTF-8 u16 sequence that Stage39R proved is visibly rendered.",
        "stage39r_decisive_proof": {
            "visible_caller":
                "0x089726C0 wide Unicode renderer",
            "visible_string_ptr":
                "0x08E4E85C",
            "visible_string_u16":
                "00EC 008A 00A4 00ED 0086 00A0 00EB 00A6 00AC",
            "first_sprite":
                "U+00EC -> original glyph135",
            "second_sprite":
                "U+008A -> fallback glyph0",
            "fourth_sprite":
                "U+00ED -> original glyph136",
            "renderer_element_count": 9,
        },
        "fix_design":
            "Intercept the renderer Unicode lookup. If the current u16 element "
            "is actually the first byte of a widened 2/3-byte UTF-8 sequence, "
            "decode it to the true Unicode codepoint and pre-advance s0/s5 so "
            "the existing loop consumes 2/3 source elements but renders one glyph.",
        "diagnostic_code_cave":
            "PRX 0x4C0390 C-JIS-specific branch body. Stage39D already proved "
            "this region is not used by the English main-menu path. This is a "
            "diagnostic location; a final production build can relocate the helper.",
        "source_iso": str(SOURCE_ISO),
        "test_iso": str(TEST_ISO),
    }

    try:
        report["build"] = build_iso()
        report["runtime"] = runtime(local_mod, b)
        report["completed"] = bool(
            report["runtime"].get(
                "completed", False
            )
        )
    except Exception as e:
        report["runtime_exception"] = str(e)
        report["runtime_traceback"] = traceback.format_exc()
        report["completed"] = False

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
        if report["completed"]
        else FAIL_ZIP
    )
    make_zip(target)

    if not report["completed"]:
        raise RuntimeError(
            f"Stage39S failed. See {FAIL_ZIP}"
        )

    log("[Stage39S] COMPLETE")
    log(f"[Stage39S] ISO: {TEST_ISO}")
    log(f"[Stage39S] Upload ZIP: {SUCCESS_ZIP}")


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
        print(f"STAGE 39S FAILED: {FAIL_ZIP}", flush=True)
        raise SystemExit(1)
