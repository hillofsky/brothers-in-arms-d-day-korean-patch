#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import base64
import csv
import hashlib
import importlib.util
import json
import shutil
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
OUTPUT_ISO = ROOT / "BIA_STAGE41A_FIRST_MOVIE_KO_SUB_TEST.iso"

OUT = ROOT / "analysis" / "stage41a_first_movie_subtitle"
LOG_DIR = ROOT / "log"
SUCCESS_ZIP = LOG_DIR / "bia_stage41a_upload.zip"
FAIL_ZIP = LOG_DIR / "fail_bia_stage41a_upload.zip"
REPORT_PATH = OUT / "stage41a_report.json"
PPSSPP_LOG = OUT / "stage41a_ppsspp.log"

TOOL_DIR = Path(__file__).resolve().parent
TSV = TOOL_DIR / "stage41a_first_movie_subtitles.tsv"

TARGET_ST1 = [
    "PSP_GAME",
    "USRDIR",
    "SYSTEM",
    "FM_0115EAGLESJUMP.ST1",
]

EXPECTED_ST1_SIZE = 1482

# Proven menu path.
MENU_LOOKUP = 0x08C7F2FC
MENU_RENDER_LOOKUP_RA = 0x08972368
MENU_STORY_CP = 0xD1A0
MENU_SKIRMISH_CP = 0xCEE4
MENU_CONTINUE_CP = 0xACC4
MENU_NORMAL_CP = 0xBCF4

# Proven Stage40R/Y campaign executable.
CAMPAIGN_LOOKUP = 0x08C5CED4
CAMPAIGN_RENDER_CALL = 0x0898E354
CAMPAIGN_RENDER_WORD = 0x0E327D1A

# Subtitle probes from the newly patched ST1.
SUBTITLE_PROBES = [
    ("title_운", 0xC6B4),   # 운 in 운명의 랑데부
    ("baker_베", 0xBCA0),  # 베 in 베이커
    ("mac_맥", 0xB9E5),    # 맥
]

RAM_START = 0x08000000
RAM_END = 0x0A000000
RAM_CHUNK = 0x20000

FRAMEBUFFERS = [
    0x04000000,
    0x04044000,
]
FB_STRIDE = 512
FB_W = 480
FB_H = 272
FB565_BYTES = FB_STRIDE * FB_H * 2
FB8888_BYTES = FB_STRIDE * FB_H * 4


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


def load_patches():
    rows = []

    with TSV.open("r", encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            rows.append({
                "index": int(r["index"]),
                "english": r["English"],
                "korean": r["한국어"],
                "source_bytes": int(r["source_bytes"]),
                "korean_bytes": int(r["korean_bytes"]),
            })

    return rows


def same_size_replacement(source, korean):
    sb = source.encode("ascii")
    kb = korean.encode("utf-8")

    if len(kb) > len(sb):
        raise RuntimeError(
            f"Korean overflow {len(kb)} > {len(sb)}: {source!r}"
        )

    if source.endswith("^"):
        if not korean.endswith("^"):
            raise RuntimeError("Korean field lost ^ terminator")

        body = korean[:-1].encode("utf-8")
        room = len(sb) - 1

        if len(body) > room:
            raise RuntimeError("Korean body overflow")

        # Keep the ^ delimiter at exactly the original final printable byte.
        return body + (b" " * (room - len(body))) + b"^"

    return kb + (b" " * (len(sb) - len(kb)))


def patch_st1(raw, rows):
    if len(raw) != EXPECTED_ST1_SIZE:
        raise RuntimeError(
            f"Unexpected ST1 size: {len(raw)} != {EXPECTED_ST1_SIZE}"
        )

    out = bytearray(raw)
    report = []

    for r in rows:
        src = r["english"].encode("ascii")
        positions = []
        start = 0

        while True:
            pos = raw.find(src, start)
            if pos < 0:
                break
            positions.append(pos)
            start = pos + 1

        if len(positions) != 1:
            raise RuntimeError(
                f"Expected one source occurrence for row {r['index']}, got "
                f"{len(positions)}: {r['english']!r}"
            )

        pos = positions[0]
        repl = same_size_replacement(
            r["english"],
            r["korean"],
        )

        if len(repl) != len(src):
            raise RuntimeError("Internal same-size patch failure")

        out[pos:pos+len(src)] = repl

        report.append({
            "index": r["index"],
            "offset": f"0x{pos:X}",
            "field_bytes": len(src),
            "korean_bytes": len(r["korean"].encode("utf-8")),
            "english": r["english"],
            "korean": r["korean"],
            "replacement_hex": repl.hex(),
        })

    return bytes(out), report


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
            "response": ws.request(event, timeout=5, **kwargs),
        }
    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
        }


def wait_cpu_ready(ws, timeout=25):
    end = time.time() + timeout
    attempts = 0

    while time.time() < end:
        attempts += 1
        try:
            status = ws.request("cpu.status", timeout=2)
            read_ws(ws, 0x08800000, 4)
            return {
                "ready": True,
                "attempts": attempts,
                "status": status,
            }
        except Exception:
            pass
        time.sleep(0.05)

    return {
        "ready": False,
        "attempts": attempts,
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


def button_hold(ws, button, hold=0.16, settle=0.4):
    release_buttons(ws)

    down = request_safe(
        ws,
        "input.buttons.send",
        buttons={button: True},
    )

    time.sleep(hold)

    up = request_safe(
        ws,
        "input.buttons.send",
        buttons={button: False},
    )

    time.sleep(settle)

    return {
        "down": down,
        "up": up,
    }


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


def wait_break(ws, timeout=5):
    end = time.time() + timeout

    while time.time() < end:
        try:
            s = ws.request("cpu.status", timeout=2)
            if s.get("stepping", False):
                return True
        except Exception:
            pass
        time.sleep(0.012)

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
            v = struct.unpack_from("<H", raw, base + x * 2)[0]
            r = (v & 31) * 255 // 31
            g = ((v >> 5) & 63) * 255 // 63
            b = ((v >> 11) & 31) * 255 // 31
            rgb[o:o+3] = bytes((r, g, b))
            o += 3

    return Image.frombytes("RGB", (FB_W, FB_H), bytes(rgb))


def rgba8888_image(raw):
    # PSP GE 8888 memory is commonly ABGR little-endian.  Convert the first
    # visible 480 pixels of each 512-pixel row to RGB.
    rgb = bytearray(FB_W * FB_H * 3)
    o = 0

    for y in range(FB_H):
        base = y * FB_STRIDE * 4

        for x in range(FB_W):
            v = struct.unpack_from("<I", raw, base + x * 4)[0]
            r = v & 0xFF
            g = (v >> 8) & 0xFF
            b = (v >> 16) & 0xFF
            rgb[o:o+3] = bytes((r, g, b))
            o += 3

    return Image.frombytes("RGB", (FB_W, FB_H), bytes(rgb))


def capture_dual(ws, name):
    result = []

    for addr in FRAMEBUFFERS:
        raw = read_ws(ws, addr, FB8888_BYTES)

        p565 = OUT / f"{name}_{addr:08X}_rgb565.png"
        p8888 = OUT / f"{name}_{addr:08X}_rgba8888.png"

        rgb565_image(raw[:FB565_BYTES]).save(p565)
        rgba8888_image(raw).save(p8888)

        result.append({
            "address": f"0x{addr:08X}",
            "rgb565": str(p565),
            "rgba8888": str(p8888),
            "raw_sha1": hashlib.sha1(raw).hexdigest(),
        })

    return result


def wait_title_story_preload(ws, timeout=120):
    arm_lookup(
        ws,
        MENU_LOOKUP,
        MENU_STORY_CP,
        MENU_RENDER_LOOKUP_RA,
    )

    end = time.time() + timeout
    next_start = 0.0

    while time.time() < end:
        if wait_break(ws, timeout=0.06):
            remove_bp(ws, MENU_LOOKUP)
            resume_cpu(ws)
            time.sleep(0.3)
            return True

        now = time.time()

        if now >= next_start:
            button_hold(ws, "start", hold=0.12, settle=0.08)
            next_start = time.time() + 1.25

        time.sleep(0.03)

    remove_bp(ws, MENU_LOOKUP)
    resume_cpu(ws)
    return False


def enter_selectable_main_menu(ws):
    for _ in range(5):
        arm_lookup(
            ws,
            MENU_LOOKUP,
            MENU_SKIRMISH_CP,
            MENU_RENDER_LOOKUP_RA,
        )

        button_hold(ws, "start", hold=0.16, settle=0.08)

        if wait_break(ws, timeout=4.5):
            remove_bp(ws, MENU_LOOKUP)
            resume_cpu(ws)
            time.sleep(0.4)
            return True

        remove_bp(ws, MENU_LOOKUP)
        resume_cpu(ws)
        time.sleep(0.4)

    return False


def enter_new_game_to_difficulty(ws):
    # Story
    button_hold(ws, "cross", hold=0.16, settle=0.3)

    # Story submenu proof: Continue/계 renders even if disabled.
    arm_lookup(
        ws,
        MENU_LOOKUP,
        MENU_CONTINUE_CP,
        MENU_RENDER_LOOKUP_RA,
    )
    hit_continue = wait_break(ws, timeout=5.0)
    remove_bp(ws, MENU_LOOKUP)

    if hit_continue:
        resume_cpu(ws)
        time.sleep(0.3)

    # New Game is the selected item in the proven current profile state.
    arm_lookup(
        ws,
        MENU_LOOKUP,
        MENU_NORMAL_CP,
        MENU_RENDER_LOOKUP_RA,
    )

    button_hold(ws, "cross", hold=0.16, settle=0.08)
    hit_normal = wait_break(ws, timeout=5.0)

    if not hit_normal:
        remove_bp(ws, MENU_LOOKUP)
        resume_cpu(ws)

        # Existing-progress confirmation fallback.
        arm_lookup(
            ws,
            MENU_LOOKUP,
            MENU_NORMAL_CP,
            MENU_RENDER_LOOKUP_RA,
        )
        button_hold(ws, "cross", hold=0.16, settle=0.08)
        hit_normal = wait_break(ws, timeout=5.0)

    remove_bp(ws, MENU_LOOKUP)

    if hit_normal:
        resume_cpu(ws)
        time.sleep(0.35)

    return {
        "continue_renderer_hit": hit_continue,
        "difficulty_renderer_hit": hit_normal,
    }


def wait_campaign_word(ws, timeout=30):
    end = time.time() + timeout
    samples = []

    while time.time() < end:
        try:
            word = read_u32(ws, CAMPAIGN_RENDER_CALL)

            if len(samples) < 40:
                samples.append(f"0x{word:08X}")

            if word == CAMPAIGN_RENDER_WORD:
                return {
                    "ok": True,
                    "samples": samples,
                }
        except Exception as e:
            if len(samples) < 40:
                samples.append("ERR:" + str(e))

        time.sleep(0.08)

    return {
        "ok": False,
        "samples": samples,
    }


def wait_subtitle_probe(ws, name, codepoint, timeout=18):
    arm = arm_lookup(
        ws,
        CAMPAIGN_LOOKUP,
        codepoint,
    )

    end = time.time() + timeout
    captures = []
    next_capture = time.time() + 1.0

    while time.time() < end:
        if wait_break(ws, timeout=0.06):
            regs = ws.request("cpu.getAllRegs", timeout=5)
            cap = capture_dual(ws, f"subtitle_hit_{name}")

            remove_bp(ws, CAMPAIGN_LOOKUP)
            resume_cpu(ws)
            time.sleep(0.15)

            return {
                "hit": True,
                "arm": arm,
                "regs": regs,
                "capture": cap,
                "periodic_captures": captures,
            }

        if time.time() >= next_capture and len(captures) < 6:
            captures.append(
                capture_dual(
                    ws,
                    f"subtitle_wait_{name}_{len(captures)+1}",
                )
            )
            next_capture = time.time() + 2.0

        time.sleep(0.03)

    remove_bp(ws, CAMPAIGN_LOOKUP)
    resume_cpu(ws)

    return {
        "hit": False,
        "arm": arm,
        "periodic_captures": captures,
    }


def scan_ram_for(needles):
    # Placeholder replaced at runtime via closure; defined separately below.
    raise NotImplementedError


def ram_scan(ws, patterns):
    hits = {
        name: []
        for name in patterns
    }

    max_len = max(len(v) for v in patterns.values())
    overlap = max_len - 1
    prev = b""

    addr = RAM_START

    while addr < RAM_END:
        size = min(
            RAM_CHUNK,
            RAM_END - addr,
        )

        block = read_ws(ws, addr, size)
        data = prev + block
        base = addr - len(prev)

        for name, needle in patterns.items():
            start = 0

            while len(hits[name]) < 16:
                pos = data.find(needle, start)
                if pos < 0:
                    break

                absolute = base + pos
                h = f"0x{absolute:08X}"

                if h not in hits[name]:
                    hits[name].append(h)

                start = pos + 1

        prev = data[-overlap:] if overlap else b""
        addr += size

    return hits


def launch(b):
    exe = b.find_ppsspp_exe()

    cfg = OUT / "stage41a_append.ini"
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

    try:
        b.close_existing_ppsspp(timeout=3.0)
    except Exception:
        pass

    port = b.choose_free_port()

    return subprocess.Popen([
        str(exe),
        "--loglevel=4",
        f"--log={PPSSPP_LOG}",
        "--windowed",
        f"--appendconfig={cfg}",
        f"--debugger={port}",
        str(OUTPUT_ISO),
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

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
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
        "stage": "41A",
        "purpose":
            "Patch the separate English ST1 subtitle track for the first Bink "
            "movie into Korean without changing ST1 size/record boundaries, "
            "then determine whether the existing Stage40R/Y campaign renderer "
            "and current movie subtitle font can actually render the Korean.",
        "source_iso": str(SOURCE_ISO),
        "output_iso": str(OUTPUT_ISO),
        "target_st1": "\\".join(TARGET_ST1),
        "subtitle_file_model":
            "FM_0115EAGLESJUMP.BIK uses external FM_0115EAGLESJUMP.ST1; "
            "ST2..ST5 are the other European languages.",
    }

    p = None
    ws = None

    try:
        if not SOURCE_ISO.exists():
            raise RuntimeError(
                f"Missing Stage40Y ISO: {SOURCE_ISO}"
            )

        _, b = load_helpers()
        patch_rows = load_patches()

        _, original = b.iso_read_file(
            SOURCE_ISO,
            TARGET_ST1,
        )

        patched, patch_report = patch_st1(
            original,
            patch_rows,
        )

        report["build"] = {
            "original_size": len(original),
            "patched_size": len(patched),
            "original_sha1": hashlib.sha1(original).hexdigest(),
            "patched_sha1": hashlib.sha1(patched).hexdigest(),
            "field_count": len(patch_report),
            "size_preserved": len(original) == len(patched),
            "patches": patch_report,
        }

        if OUTPUT_ISO.exists():
            OUTPUT_ISO.unlink()

        shutil.copy2(
            SOURCE_ISO,
            OUTPUT_ISO,
        )

        b.append_iso_file_and_repoint(
            OUTPUT_ISO,
            TARGET_ST1,
            patched,
        )

        _, readback = b.iso_read_file(
            OUTPUT_ISO,
            TARGET_ST1,
        )

        report["build"]["iso_readback_ok"] = (
            readback == patched
        )

        if readback != patched:
            raise RuntimeError("Patched ST1 ISO readback mismatch")

        # Save exact patched ST1 bytes for inspection.
        (OUT / "FM_0115EAGLESJUMP_KO.ST1").write_bytes(
            patched
        )

        p = launch(b)
        report["ppsspp_pid"] = p.pid

        hwnd = b.find_ppsspp_hwnd(30)
        if not hwnd:
            raise RuntimeError("PPSSPP window did not appear")

        actual_port = b.wait_for_actual_debugger_port(
            PPSSPP_LOG,
            30,
        )
        ws, host = b.connect_debugger(actual_port)

        report["debugger_host"] = host
        report["debugger_port"] = actual_port

        ready = wait_cpu_ready(ws)
        report["cpu_ready"] = ready
        if not ready["ready"]:
            raise RuntimeError("CPU did not become ready")

        report["title_story_preload"] = (
            wait_title_story_preload(ws)
        )

        if not report["title_story_preload"]:
            raise RuntimeError("Could not reach menu Story preload")

        report["selectable_main_menu"] = (
            enter_selectable_main_menu(ws)
        )

        if not report["selectable_main_menu"]:
            raise RuntimeError("Could not prove selectable main menu")

        route = enter_new_game_to_difficulty(ws)
        report["new_game_route"] = route

        if not route["difficulty_renderer_hit"]:
            raise RuntimeError("Could not reach difficulty menu")

        # Arm the first Korean subtitle character before selecting difficulty,
        # so even the earliest movie title subtitle cannot be missed.
        arm_lookup(
            ws,
            CAMPAIGN_LOOKUP,
            SUBTITLE_PROBES[0][1],
        )

        report["difficulty_cross"] = button_hold(
            ws,
            "cross",
            hold=0.16,
            settle=0.05,
        )

        campaign = wait_campaign_word(
            ws,
            timeout=30,
        )
        report["campaign_module"] = campaign

        # The early breakpoint might already have fired while we were polling.
        early_hit = False
        early_regs = None
        try:
            if ws.request("cpu.status", timeout=2).get("stepping", False):
                early_hit = True
                early_regs = ws.request(
                    "cpu.getAllRegs",
                    timeout=5,
                )
        except Exception:
            pass

        if early_hit:
            report["early_title_probe"] = {
                "hit": True,
                "regs": early_regs,
                "capture": capture_dual(
                    ws,
                    "subtitle_hit_title_early",
                ),
            }
            remove_bp(ws, CAMPAIGN_LOOKUP)
            resume_cpu(ws)
        else:
            remove_bp(ws, CAMPAIGN_LOOKUP)
            resume_cpu(ws)
            report["early_title_probe"] = {
                "hit": False,
            }

        if not campaign["ok"]:
            raise RuntimeError(
                "Difficulty selection did not load BIAOFF"
            )

        # Probe the same proven campaign lookup while the Bink movie is active.
        probes = []

        if not early_hit:
            probes.append(
                {
                    "name": SUBTITLE_PROBES[0][0],
                    **wait_subtitle_probe(
                        ws,
                        SUBTITLE_PROBES[0][0],
                        SUBTITLE_PROBES[0][1],
                        timeout=10,
                    ),
                }
            )

        for name, cp in SUBTITLE_PROBES[1:]:
            probes.append(
                {
                    "name": name,
                    **wait_subtitle_probe(
                        ws,
                        name,
                        cp,
                        timeout=14,
                    ),
                }
            )

        report["subtitle_renderer_probes"] = probes

        # Prove the patched ST1 strings are resident, even if the subtitle
        # renderer uses a different path than the normal campaign text lookup.
        patterns = {
            "title_utf8":
                "운명의 랑데부".encode("utf-8"),
            "baker_utf8":
                "베이커: 원한 건 아니지만".encode("utf-8"),
            "title_widened_utf8":
                b"".join(
                    bytes((x, 0))
                    for x in "운명의 랑데부".encode("utf-8")
                ),
            "baker_widened_utf8":
                b"".join(
                    bytes((x, 0))
                    for x in "베이커: 원한 건 아니지만".encode("utf-8")
                ),
        }

        report["ram_subtitle_hits"] = ram_scan(
            ws,
            patterns,
        )

        report["final_capture"] = capture_dual(
            ws,
            "subtitle_final",
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
            f"Stage41A failed. See {FAIL_ZIP}"
        )

    log("[Stage41A] build/runtime diagnostic complete")
    log(f"[Stage41A] output ISO: {OUTPUT_ISO}")
    log(f"[Stage41A] upload ZIP: {SUCCESS_ZIP}")


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
                        "stage": "41A",
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

        print(traceback.format_exc(), flush=True)
        print(
            f"STAGE41A FAILED: {FAIL_ZIP}",
            flush=True,
        )
        raise SystemExit(1)
