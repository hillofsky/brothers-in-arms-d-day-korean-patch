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
TEST_ISO = ROOT / "BIA_STAGE39U_BOOT_RENDER_UTF8_TEST.iso"

OUT = ROOT / "analysis" / "stage39u_boot_renderer_utf8"
LOG_DIR = ROOT / "log"

SUCCESS_ZIP = LOG_DIR / "bia_stage39u_upload.zip"
FAIL_ZIP = LOG_DIR / "fail_bia_stage39u_upload.zip"
REPORT_PATH = OUT / "stage39u_report.json"
PPSSPP_LOG = OUT / "stage39u_ppsspp.log"

SCRIPT_DIR = Path(__file__).resolve().parent
HELPER_PATH = SCRIPT_DIR / "utf8_widened_renderer_helper.bin"

BOOT_PATH = ["PSP_GAME", "SYSDIR", "BOOT.BIN"]
EBOOT_PATH = ["PSP_GAME", "SYSDIR", "EBOOT.BIN"]
BIAON_PATH = ["PSP_GAME", "USRDIR", "SYSTEM", "BIAON.PRX"]

SECTOR = 2048

EXPECTED_BOOT_SHA1 = "8c7033ca15103fa51afa9c7ec61f37c531d07ede"
EXPECTED_BIAON_SHA1 = EXPECTED_BOOT_SHA1
EXPECTED_EBOOT_SHA1 = "0ea1b9eeb594440545fe0310b229439cbbd12fa9"

# ELF .text has file bias +0x80.
TEXT_FILE_BIAS = 0x80

# Real visible renderer.
RENDER_CALL_VA = 0x0016E360
RENDER_CALL_FILE = RENDER_CALL_VA + TEXT_FILE_BIAS
RENDER_CALL_RUNTIME = 0x08804000 + RENDER_CALL_VA

# Original on-disk JAL UnicodeLookup(0x47B2FC).
EXPECTED_RENDER_JAL = bytes.fromhex("bfec110c")

# On-disk JAL helper(0x4C0390).
# The existing R_MIPS_26 relocation at 0x16E360 will add the runtime module base.
PATCHED_RENDER_JAL_DISK = bytes.fromhex("e400130c")

# Expected runtime JAL helper(0x08CC4390) after relocation.
PATCHED_RENDER_JAL_RUNTIME = bytes.fromhex("e410330e")

HELPER_VA = 0x004C0390
HELPER_FILE = HELPER_VA + TEXT_FILE_BIAS
HELPER_RUNTIME = 0x08804000 + HELPER_VA
HELPER_SIZE = 232
HELPER_SHA1 = "5b6b493c890ea797f0b59d176a1a7b84fa0913a2"

ORIGINAL_LOOKUP_RUNTIME = 0x08C7F2FC
DRAW_HELPER = 0x08AF6324
VISIBLE_RENDER_RA = 0x089726C0

# .rel.text PSP relocation section from this exact BOOT/BIAON build.
REL_TEXT_FILE = 0x005BF54C
REL_TEXT_SIZE = 0x00177848

# These four old C-JIS relocations fall inside the helper overwrite range.
# They would corrupt our injected instructions during ELF relocation.
HELPER_RELOC_RECORDS = {
    0x00734BEC: (0x004C03F0, 5),
    0x00734BF4: (0x004C0414, 6),
    0x00734BFC: (0x004C03F4, 5),
    0x00734C04: (0x004C0418, 6),
}

# The renderer JAL itself has a type-4 J26 relocation and MUST stay active.
RENDER_RELOC_RECORD = 0x006493EC
EXPECTED_RENDER_RELOC = (0x0016E360, 4)

# Correct Stage39F source.
DISPLAY1_ADDR = 0x093B1B40
DISPLAY2_ADDR = 0x093B1BF0
META1_ADDR = 0x095EC774
META2_ADDR = 0x095F1758

UTF8 = "스토리".encode("utf-8")
UTF8_NUL = UTF8 + b"\x00"

EXPECTED_META1 = (DISPLAY1_ADDR, 10, 10)
EXPECTED_META2 = (DISPLAY2_ADDR, 10, 10)

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
        raise RuntimeError("Could not resolve Stage39B helpers")

    return mod, b


def find_callable(objects, name):
    for obj in objects:
        if obj is not None and hasattr(obj, name):
            fn = getattr(obj, name)
            if callable(fn):
                return fn
    return None


# ---------------------------------------------------------------------------
# ISO9660 same-size patch helpers.
# ---------------------------------------------------------------------------

def _norm_name(raw):
    s = raw.decode("ascii", errors="replace")
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
            "is_dir": bool(rec[25] & 2),
            "name": _norm_name(rec[33:33+rec[32]]),
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

        cur = {
            "extent": struct.unpack_from("<I", root, 2)[0],
            "size": struct.unpack_from("<I", root, 10)[0],
            "is_dir": True,
        }

        for i, want in enumerate(parts):
            found = None

            for rec in _dir_records(
                f, cur["extent"], cur["size"]
            ):
                if rec["name"] == want:
                    found = rec
                    break

            if found is None:
                raise FileNotFoundError("/".join(parts))

            if i != len(parts)-1 and not found["is_dir"]:
                raise RuntimeError(f"Not a directory: {want}")

            cur = found

        return cur


def iso_read(path, parts):
    rec = iso_find(path, parts)
    with path.open("rb") as f:
        f.seek(rec["extent"] * SECTOR)
        data = f.read(rec["size"])
    return rec, data


def iso_overwrite(path, parts, data):
    rec = iso_find(path, parts)

    if len(data) != rec["size"]:
        raise RuntimeError(
            f"Same-size overwrite required for {'/'.join(parts)}: "
            f"{len(data)} != {rec['size']}"
        )

    with path.open("r+b") as f:
        f.seek(rec["extent"] * SECTOR)
        f.write(data)
        f.flush()
        os.fsync(f.fileno())

    _, rb = iso_read(path, parts)
    if rb != data:
        raise RuntimeError(
            f"ISO read-back failed: {'/'.join(parts)}"
        )


# ---------------------------------------------------------------------------
# Executable patch.
# ---------------------------------------------------------------------------

def patch_plain_elf(original):
    helper = HELPER_PATH.read_bytes()

    if len(helper) != HELPER_SIZE:
        raise RuntimeError("Helper size mismatch")
    if sha1(helper) != HELPER_SHA1:
        raise RuntimeError("Helper SHA1 mismatch")
    if sha1(original) != EXPECTED_BOOT_SHA1:
        raise RuntimeError(
            f"Unexpected BOOT/BIAON SHA1: {sha1(original)}"
        )

    out = bytearray(original)

    if (
        out[RENDER_CALL_FILE:RENDER_CALL_FILE+4]
        != EXPECTED_RENDER_JAL
    ):
        raise RuntimeError("Renderer JAL bytes mismatch")

    # Verify the renderer relocation remains active.
    rr = struct.unpack_from(
        "<II", out, RENDER_RELOC_RECORD
    )
    if rr != EXPECTED_RENDER_RELOC:
        raise RuntimeError(
            f"Renderer relocation mismatch: {rr}"
        )

    # Verify and disable only the old relocations that fall inside our helper.
    disabled = []

    for rec_off, expected in HELPER_RELOC_RECORDS.items():
        got = struct.unpack_from("<II", out, rec_off)

        if got != expected:
            raise RuntimeError(
                f"Helper relocation mismatch at 0x{rec_off:X}: "
                f"{got} != {expected}"
            )

        # Preserve r_offset, replace relocation type with R_MIPS_NONE (0).
        struct.pack_into(
            "<II", out, rec_off, got[0], 0
        )
        disabled.append({
            "record_file_offset": f"0x{rec_off:X}",
            "target_vaddr": f"0x{got[0]:08X}",
            "old_type": got[1],
            "new_type": 0,
        })

    out[
        RENDER_CALL_FILE:
        RENDER_CALL_FILE+4
    ] = PATCHED_RENDER_JAL_DISK

    out[
        HELPER_FILE:
        HELPER_FILE+len(helper)
    ] = helper

    return bytes(out), disabled


def build_iso():
    if not SOURCE_ISO.exists():
        raise RuntimeError(f"Missing source ISO: {SOURCE_ISO}")

    _, boot = iso_read(SOURCE_ISO, BOOT_PATH)
    _, eboot = iso_read(SOURCE_ISO, EBOOT_PATH)
    _, biaon = iso_read(SOURCE_ISO, BIAON_PATH)

    if sha1(boot) != EXPECTED_BOOT_SHA1:
        raise RuntimeError(f"Unexpected BOOT SHA1: {sha1(boot)}")
    if sha1(biaon) != EXPECTED_BIAON_SHA1:
        raise RuntimeError(f"Unexpected BIAON SHA1: {sha1(biaon)}")
    if sha1(eboot) != EXPECTED_EBOOT_SHA1:
        raise RuntimeError(f"Unexpected EBOOT SHA1: {sha1(eboot)}")
    if eboot[:4] != b"~PSP":
        raise RuntimeError("Original EBOOT does not start with ~PSP")

    patched_boot, disabled = patch_plain_elf(boot)
    patched_biaon, disabled2 = patch_plain_elf(biaon)

    if disabled2 != disabled:
        raise RuntimeError("BOOT/BIAON relocation patch mismatch")

    # PPSSPP normally selects encrypted EBOOT.BIN whenever it starts with
    # "~PSP".  That is why Stage39S never executed our BIAON.PRX patch.
    #
    # For this diagnostic ISO, invalidate ONLY the first four EBOOT bytes.
    # PPSSPP's disc loader then explicitly falls back to SYSDIR/BOOT.BIN.
    patched_eboot = bytearray(eboot)
    patched_eboot[:4] = b"NOPE"

    if TEST_ISO.exists():
        TEST_ISO.unlink()

    shutil.copy2(SOURCE_ISO, TEST_ISO)

    iso_overwrite(TEST_ISO, BOOT_PATH, patched_boot)
    iso_overwrite(TEST_ISO, BIAON_PATH, patched_biaon)
    iso_overwrite(TEST_ISO, EBOOT_PATH, bytes(patched_eboot))

    _, rb_boot = iso_read(TEST_ISO, BOOT_PATH)
    _, rb_biaon = iso_read(TEST_ISO, BIAON_PATH)
    _, rb_eboot = iso_read(TEST_ISO, EBOOT_PATH)

    return {
        "source_boot_sha1": sha1(boot),
        "source_eboot_sha1": sha1(eboot),
        "patched_boot_sha1": sha1(rb_boot),
        "patched_biaon_sha1": sha1(rb_biaon),
        "patched_eboot_magic": rb_eboot[:4].hex(),
        "renderer_jal_disk":
            rb_boot[
                RENDER_CALL_FILE:
                RENDER_CALL_FILE+4
            ].hex(),
        "helper_disk_sha1":
            sha1(
                rb_boot[
                    HELPER_FILE:
                    HELPER_FILE+HELPER_SIZE
                ]
            ),
        "renderer_relocation":
            list(
                struct.unpack_from(
                    "<II",
                    rb_boot,
                    RENDER_RELOC_RECORD,
                )
            ),
        "disabled_helper_relocations": disabled,
        "iso_readback_ok": (
            rb_boot == patched_boot
            and rb_biaon == patched_biaon
            and rb_eboot == bytes(patched_eboot)
        ),
    }


# ---------------------------------------------------------------------------
# Runtime diagnostics.
# ---------------------------------------------------------------------------

def read_ws(ws, address, size):
    r = ws.request(
        "memory.read",
        timeout=10,
        address=address,
        size=size,
    )
    return base64.b64decode(r["base64"])


def wait_cpu_ready(ws, timeout=20.0):
    """
    The debugger webserver becomes reachable before the emulated CPU is started.
    Stage39T connected during that short window and immediately got:
        RuntimeError: CPU not started

    Wait until BOTH:
      1) cpu.status succeeds, and
      2) a real RAM read from the loaded module succeeds.

    This is intentionally independent of wall-clock boot timing.
    """
    end = time.time() + timeout
    attempts = 0
    last_error = None
    last_status = None

    while time.time() < end:
        attempts += 1

        try:
            last_status = ws.request(
                "cpu.status",
                timeout=2,
            )

            probe = ws.request(
                "memory.read",
                timeout=2,
                address=RENDER_CALL_RUNTIME,
                size=4,
            )
            probe_bytes = base64.b64decode(
                probe["base64"]
            )

            if len(probe_bytes) == 4:
                return {
                    "ready": True,
                    "attempts": attempts,
                    "status": last_status,
                    "probe_hex":
                        probe_bytes.hex(),
                }

        except Exception as e:
            last_error = str(e)

        time.sleep(0.05)

    return {
        "ready": False,
        "attempts": attempts,
        "status": last_status,
        "last_error": last_error,
    }


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


def resume(ws):
    try:
        ws.request("cpu.resume", timeout=0.5)
    except Exception:
        pass


def wait_pause(ws, timeout=10.0):
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


def wait_menu_resource(ws, timeout=180.0):
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
        return {
            "ok": False,
            "error": str(e),
        }

    return {
        "ok": (
            opt.startswith(
                UTF16_OPTIONS+b"\x00\x00"
            )
            and pro.startswith(
                UTF16_PROFILE+b"\x00\x00"
            )
            and sto.startswith(
                UTF16_STORY+b"\x00\x00"
            )
        ),
        "options_hex": opt.hex(),
        "profile_hex": pro.hex(),
        "story_hex": sto.hex(),
    }


def enter_main_menu(ws):
    # Same reliable timing as Stage39R.
    time.sleep(2.5)

    attempts = []

    for attempt in (1, 2):
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
        [
            b,
            getattr(local_mod, "s39", None),
            local_mod,
        ],
        "capture",
    )
    helper = BASE_TOOLS / "capture_ppsspp.ps1"
    path = OUT / f"stage39u_{label}.png"

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


def wait_helper_first_byte(ws):
    """
    Break in the injected helper only for the first UTF-8 byte EC.
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
        return {"hit": False}

    uints, _ = parse_regs(
        ws.request(
            "cpu.getAllRegs",
            timeout=10,
        )
    )

    s0 = uints.get("s0", 0)

    hit = {
        "hit": True,
        "pc": f"0x{uints.get('pc',0):08X}",
        "ra": f"0x{uints.get('ra',0):08X}",
        "a0": f"0x{uints.get('a0',0):08X}",
        "a1": f"0x{uints.get('a1',0):08X}",
        "s0_source": f"0x{s0:08X}",
        "s5_before": uints.get("s5"),
        "source_20_hex":
            read_ws(ws, s0, 20).hex()
            if RAM_START <= s0 < RAM_END
            else None,
    }

    remove_bp(ws, HELPER_RUNTIME)

    # Now prove the helper decoded EC 8A A4 -> U+C2A4 and pre-consumed.
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

        hit["decoded_lookup"] = {
            "hit": True,
            "a1":
                f"0x{r2.get('a1',0):08X}",
            "s0_after_preconsume":
                f"0x{r2.get('s0',0):08X}",
            "s5_after_preconsume":
                r2.get("s5"),
            "expected_s0":
                f"0x{(s0+4)&0xFFFFFFFF:08X}",
            "expected_s5":
                (uints.get("s5",0)+2)&0xFFFFFFFF,
            "ra":
                f"0x{r2.get('ra',0):08X}",
        }
    else:
        hit["decoded_lookup"] = {
            "hit": False,
        }

    remove_bp(ws, ORIGINAL_LOOKUP_RUNTIME)

    return hit


def wait_first_decoded_draw(ws, source_ptr):
    """
    At the draw helper, the renderer's preserved s0 has already been advanced
    by +4 inside our helper (past the first two continuation elements), and s5
    has been advanced to 2.  This identifies the FIRST decoded Story glyph
    without assuming any UV value.
    """
    expected_s0 = (source_ptr + 4) & 0xFFFFFFFF

    remove_bp(ws, DRAW_HELPER)

    ws.request(
        "cpu.breakpoint.add",
        timeout=10,
        address=DRAW_HELPER,
        enabled=True,
        log=False,
        condition=(
            f"ra == 0x{VISIBLE_RENDER_RA:08X} && "
            f"s0 == 0x{expected_s0:08X} && "
            "s5 == 2"
        ),
    )

    resume(ws)
    p = wait_pause(ws, timeout=20)

    if p is None:
        remove_bp(ws, DRAW_HELPER)
        return {"hit": False}

    uints, floats = parse_regs(
        ws.request(
            "cpu.getAllRegs",
            timeout=10,
        )
    )

    uv = tuple_f(
        floats,
        ["f16","f17","f18","f19"],
    )
    xy = tuple_f(
        floats,
        ["f12","f13","f14","f15"],
    )

    hit = {
        "hit": True,
        "pc":
            f"0x{uints.get('pc',0):08X}",
        "ra":
            f"0x{uints.get('ra',0):08X}",
        "s0":
            f"0x{uints.get('s0',0):08X}",
        "s5":
            uints.get("s5"),
        "texture":
            f"0x{uints.get('a1',0):08X}",
        "uv_float": uv,
        "uv_floor":
            None
            if uv is None
            else tuple(
                int(math.floor(x+1e-5))
                for x in uv
            ),
        "xy_float": xy,
    }

    remove_bp(ws, DRAW_HELPER)
    return hit


def runtime(local_mod, b):
    exe = b.find_ppsspp_exe()

    cfg = OUT / "stage39u_append.ini"
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

    log("[Stage39U] Launching PPSSPP with BOOT.BIN fallback")
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

            # The WebSocket debugger starts before the emulated CPU. Stage39T
            # failed here because it attempted memory.read during that race.
            cpu_ready = wait_cpu_ready(
                ws,
                timeout=20.0,
            )
            result["cpu_ready"] = cpu_ready

            if not cpu_ready.get("ready"):
                raise RuntimeError(
                    "Debugger connected but CPU did not become ready"
                )

            # Runtime code verification is now mandatory before any behavioral
            # test. Stage39S failed precisely because this was not the code that
            # actually booted.
            runtime_jal = read_ws(
                ws,
                RENDER_CALL_RUNTIME,
                4,
            )
            runtime_helper = read_ws(
                ws,
                HELPER_RUNTIME,
                HELPER_SIZE,
            )

            result["runtime_code"] = {
                "renderer_jal":
                    runtime_jal.hex(),
                "renderer_jal_expected":
                    PATCHED_RENDER_JAL_RUNTIME.hex(),
                "renderer_jal_ok":
                    runtime_jal
                    == PATCHED_RENDER_JAL_RUNTIME,
                "helper_sha1":
                    sha1(runtime_helper),
                "helper_expected_sha1":
                    HELPER_SHA1,
                "helper_ok":
                    sha1(runtime_helper)
                    == HELPER_SHA1,
            }

            # Verify PPSSPP actually fell back to the plaintext BOOT ELF.
            time.sleep(0.5)
            log_text = (
                PPSSPP_LOG.read_text(
                    encoding="utf-8",
                    errors="replace",
                )
                if PPSSPP_LOG.exists()
                else ""
            )

            result["boot_log"] = {
                "loads_boot_bin":
                    "Loading disc0:/PSP_GAME/SYSDIR/BOOT.BIN"
                    in log_text,
                "loads_eboot_bin":
                    "Loading disc0:/PSP_GAME/SYSDIR/EBOOT.BIN"
                    in log_text,
                "decrypting_psp":
                    "Decrypting ~PSP file"
                    in log_text,
            }

            if not (
                result["runtime_code"]["renderer_jal_ok"]
                and result["runtime_code"]["helper_ok"]
            ):
                raise RuntimeError(
                    "Patched BOOT code is still not resident at runtime"
                )

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

            helper_hit = wait_helper_first_byte(ws)
            result["helper_trace"] = helper_hit

            source_ptr = (
                int(helper_hit["s0_source"], 16)
                if helper_hit.get("hit")
                else 0
            )

            draw = (
                wait_first_decoded_draw(
                    ws,
                    source_ptr,
                )
                if source_ptr
                else {"hit": False}
            )
            result["first_decoded_draw"] = draw

            # Remove all breakpoints and allow the corrected menu to render.
            remove_bp(ws, HELPER_RUNTIME)
            remove_bp(ws, ORIGINAL_LOOKUP_RUNTIME)
            remove_bp(ws, DRAW_HELPER)
            resume(ws)

            time.sleep(1.2)

            result["menu_capture"] = capture(
                local_mod,
                b,
                hwnd,
                "main_menu",
            )

            decoded = helper_hit.get(
                "decoded_lookup", {}
            )

            result["completed"] = (
                helper_hit.get("hit", False)
                and decoded.get("hit", False)
                and decoded.get(
                    "s0_after_preconsume"
                ) == decoded.get("expected_s0")
                and decoded.get(
                    "s5_after_preconsume"
                ) == decoded.get("expected_s5")
                and draw.get("hit", False)
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
        "stage": "39U",
        "purpose":
            "Repeat the corrected BOOT.BIN executable test with an explicit "
            "debugger CPU-start gate before runtime code verification.",
        "stage39t_failure_root_cause":
            "Stage39T successfully forced PPSSPP to load patched BOOT.BIN, but "
            "the debugger WebSocket became available roughly 0.3 seconds before "
            "the emulated CPU started. Its first memory.read therefore failed "
            "with 'CPU not started'. The PPSSPP log later shows user_main started; "
            "SELF-POWERDOWN was the test script cleanup after that exception.",
        "stage39s_failure_root_cause": {
            "iso_biaon_patch":
                "The Stage39S BIAON.PRX file was correctly patched on disc.",
            "runtime_renderer_bytes":
                "bffc310e = original relocated JAL 0x08C7F2FC",
            "runtime_helper_sha1":
                "did not match the injected helper",
            "reason":
                "PPSSPP boots PSP_GAME/SYSDIR/EBOOT.BIN. BIAON.PRX is merely "
                "a plaintext copy of BOOT.BIN and was not the executable being run.",
        },
        "executable_relationship": {
            "BOOT_BIN_SHA1":
                EXPECTED_BOOT_SHA1,
            "BIAON_PRX_SHA1":
                EXPECTED_BIAON_SHA1,
            "BOOT_equals_BIAON":
                True,
            "EBOOT_BIN_SHA1":
                EXPECTED_EBOOT_SHA1,
            "EBOOT_magic":
                "~PSP encrypted wrapper",
        },
        "relocation_fix":
            "The chosen C-JIS helper region had four original HI16/LO16 "
            "relocation records. Stage39U changes those four records to "
            "R_MIPS_NONE so they cannot corrupt the helper. The renderer J26 "
            "relocation remains active so its on-disc JAL is relocated to "
            "runtime 0x08CC4390.",
        "source_iso": str(SOURCE_ISO),
        "test_iso": str(TEST_ISO),
        "ppsspp_only_boot_override":
            "Diagnostic ISO invalidates the encrypted EBOOT magic so PPSSPP "
            "uses patched plaintext SYSDIR/BOOT.BIN. This is not yet the "
            "real-hardware packaging method.",
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
            f"Stage39U failed. See {FAIL_ZIP}"
        )

    log("[Stage39U] COMPLETE")
    log(f"[Stage39U] ISO: {TEST_ISO}")
    log(f"[Stage39U] Upload ZIP: {SUCCESS_ZIP}")


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
        print(
            f"STAGE 39U FAILED: {FAIL_ZIP}",
            flush=True,
        )
        raise SystemExit(1)
