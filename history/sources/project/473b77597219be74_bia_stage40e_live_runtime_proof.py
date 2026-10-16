#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import base64
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

SOURCE_ISO = ROOT / "BIA_STAGE40D_LIVE_STREAM23_MENU_TEST.iso"
STAGE40D_RUNNER = ROOT / "bia_stage40d_tools" / "run_bia_stage40d.ps1"

OUT = ROOT / "analysis" / "stage40e_live_runtime_proof"
LOG_DIR = ROOT / "log"

SUCCESS_ZIP = LOG_DIR / "bia_stage40e_upload.zip"
FAIL_ZIP = LOG_DIR / "fail_bia_stage40e_upload.zip"
REPORT_PATH = OUT / "stage40e_report.json"
PPSSPP_LOG = OUT / "stage40e_ppsspp.log"

RENDER_CALL_RUNTIME = 0x08972360
EXPECTED_RENDER_JAL_RUNTIME = bytes.fromhex("e410330e")
UNICODE_LOOKUP = 0x08C7F2FC
WIDE_RENDER_LOOKUP_RA = 0x08972368

FONT_OBJECT = 0x0972385C
EXPECTED_GLYPH_COUNT = 847
EXPECTED_GLYPH_PTR = 0x098F5020

MENU_OPEN_MARKER = (
    "sceIoOpen(disc0:/PSP_GAME/USRDIR/SYSTEM/RAWFILES/MENUINT0.RAW"
)

# Stage40D stream23 allocations.
MENU_VALUES = [
    {
        "label": "Skirmish",
        "ko": "스커미시",
        "ptr": 0x098FF890,
        "num": 13,
        "probe_char": "커",
    },
    {
        "label": "Options",
        "ko": "옵션",
        "ptr": 0x098FF8A0,
        "num": 7,
        "probe_char": "옵",
    },
    {
        "label": "Profile",
        "ko": "프로필",
        "ptr": 0x098FF8A8,
        "num": 10,
        "probe_char": "프",
    },
]

# Story is the known Stage39U control.
STORY_PROBE_CHAR = "토"

# Broad PSP RAM scan.
RAM_START = 0x08800000
RAM_END = 0x0A800000
SCAN_CHUNK = 0x20000

# PPSSPP log proved the game double-buffers these two 480x272 RGB565 surfaces.
FRAMEBUFFERS = [
    0x04000000,
    0x04044000,
]
FB_STRIDE = 512
FB_W = 480
FB_H = 272
FB_BPP = 2


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
        raise RuntimeError("Could not resolve Stage39B helpers")

    return mod, b


def ensure_stage40d_iso():
    if SOURCE_ISO.exists():
        return {
            "already_present": True,
            "path": str(SOURCE_ISO),
        }

    if not STAGE40D_RUNNER.exists():
        raise RuntimeError(
            f"Stage40D ISO missing and runner unavailable: {STAGE40D_RUNNER}"
        )

    log("[Stage40E] Stage40D ISO missing; regenerating it.")
    p = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(STAGE40D_RUNNER),
        ],
        check=False,
    )

    # Stage40D is expected to return non-zero because its old runtime metadata
    # proof was sampled too early. The ISO is still structurally valid.
    if not SOURCE_ISO.exists():
        raise RuntimeError(
            f"Stage40D regeneration did not produce {SOURCE_ISO}; exit={p.returncode}"
        )

    return {
        "already_present": False,
        "regeneration_exit_code": p.returncode,
        "path": str(SOURCE_ISO),
    }


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


def wait_cpu_ready(ws, timeout=20):
    end = time.time() + timeout
    attempts = 0
    last_error = None

    while time.time() < end:
        attempts += 1
        try:
            status = ws.request(
                "cpu.status",
                timeout=2,
            )
            probe = read_ws(
                ws,
                RENDER_CALL_RUNTIME,
                4,
            )
            if len(probe) == 4:
                return {
                    "ready": True,
                    "attempts": attempts,
                    "status": status,
                    "probe": probe.hex(),
                }
        except Exception as e:
            last_error = str(e)

        time.sleep(0.05)

    return {
        "ready": False,
        "attempts": attempts,
        "last_error": last_error,
    }


def wait_menu_resource(ws, timeout=180):
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
                    "startup_start_presses": presses,
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
        "startup_start_presses": presses,
    }


def scan_for_story_utf16(ws, timeout=12):
    needle = (
        "스토리".encode("utf-16le")
        + b"\x00\x00"
    )

    deadline = time.time() + timeout

    while time.time() < deadline:
        try:
            block = read_ws(
                ws,
                0x08E40000,
                0x10000,
            )
            p = block.find(needle)
            if p >= 0:
                return {
                    "found": True,
                    "address":
                        f"0x{0x08E40000+p:08X}",
                }
        except Exception:
            pass

        time.sleep(0.12)

    return {"found": False}


def verify_direct_allocations(ws):
    result = []

    for item in MENU_VALUES:
        expected = (
            item["ko"].encode("utf-8")
            + b"\x00"
        )

        try:
            got = read_ws(
                ws,
                item["ptr"],
                len(expected),
            )
            result.append({
                "label": item["label"],
                "ptr": f"0x{item['ptr']:08X}",
                "expected_hex": expected.hex(),
                "actual_hex": got.hex(),
                "ok": got == expected,
            })
        except Exception as e:
            result.append({
                "label": item["label"],
                "ptr": f"0x{item['ptr']:08X}",
                "ok": False,
                "error": str(e),
            })

    return result


def scan_ram_patterns(ws, patterns):
    """
    Find exact byte patterns in 32 MiB main RAM without debugger memory.search.
    """
    hits = {
        name: []
        for name in patterns
    }

    max_needle = max(
        len(v)
        for v in patterns.values()
    )
    overlap = max_needle - 1

    addr = RAM_START
    prev = b""

    while addr < RAM_END:
        size = min(
            SCAN_CHUNK,
            RAM_END - addr,
        )

        try:
            block = read_ws(
                ws,
                addr,
                size,
            )
        except Exception:
            prev = b""
            addr += size
            continue

        data = prev + block
        base = addr - len(prev)

        for name, needle in patterns.items():
            start = 0

            while len(hits[name]) < 32:
                p = data.find(
                    needle,
                    start,
                )
                if p < 0:
                    break

                absolute = base + p

                if (
                    RAM_START
                    <= absolute
                    < RAM_END
                ):
                    s = f"0x{absolute:08X}"
                    if s not in hits[name]:
                        hits[name].append(s)

                start = p + 1

        prev = (
            data[-overlap:]
            if overlap > 0
            else b""
        )
        addr += size

    return hits


def remove_bp(ws, addr):
    try:
        ws.request(
            "cpu.breakpoint.remove",
            timeout=5,
            address=addr,
        )
    except Exception:
        pass


def resume(ws):
    try:
        ws.request(
            "cpu.resume",
            timeout=0.5,
        )
    except Exception:
        pass


def wait_pause(ws, timeout=10):
    end = time.time() + timeout

    while time.time() < end:
        try:
            s = ws.request(
                "cpu.status",
                timeout=2,
            )
            if s.get("stepping", False):
                return s
        except Exception:
            pass

        time.sleep(0.018)

    return None


def lookup_renderer_probe(ws, char, timeout=20):
    """
    Prove that the actual wide renderer calls Unicode lookup for this Hangul
    codepoint. We include RA in the condition to reject unrelated lookups.
    """
    code = ord(char)

    remove_bp(
        ws,
        UNICODE_LOOKUP,
    )

    ws.request(
        "cpu.breakpoint.add",
        timeout=10,
        address=UNICODE_LOOKUP,
        enabled=True,
        log=False,
        condition=(
            f"a1 == 0x{code:X} && "
            f"ra == 0x{WIDE_RENDER_LOOKUP_RA:08X}"
        ),
    )

    resume(ws)
    p = wait_pause(
        ws,
        timeout=timeout,
    )

    if p is None:
        remove_bp(
            ws,
            UNICODE_LOOKUP,
        )
        return {
            "char": char,
            "codepoint": f"U+{code:04X}",
            "hit": False,
        }

    uints, floats = parse_regs(
        ws.request(
            "cpu.getAllRegs",
            timeout=10,
        )
    )

    s0 = uints.get("s0", 0)
    sample = None

    if (
        RAM_START
        <= s0
        < RAM_END
    ):
        try:
            sample = read_ws(
                ws,
                s0,
                40,
            ).hex()
        except Exception:
            pass

    hit = {
        "char": char,
        "codepoint": f"U+{code:04X}",
        "hit": True,
        "pc":
            f"0x{uints.get('pc',0):08X}",
        "ra":
            f"0x{uints.get('ra',0):08X}",
        "a1":
            f"0x{uints.get('a1',0):08X}",
        "s0":
            f"0x{s0:08X}",
        "s4":
            uints.get("s4"),
        "s5":
            uints.get("s5"),
        "source_sample_hex": sample,
    }

    remove_bp(
        ws,
        UNICODE_LOOKUP,
    )
    resume(ws)

    return hit


def rgb565_to_image(raw):
    need = (
        FB_STRIDE
        * FB_H
        * FB_BPP
    )

    if len(raw) < need:
        raise RuntimeError(
            f"Framebuffer too short: {len(raw)} < {need}"
        )

    # PSP little-endian BGR/RGB565. Convert explicitly.
    pixels = []

    for y in range(FB_H):
        row = y * FB_STRIDE * 2

        for x in range(FB_W):
            v = struct.unpack_from(
                "<H",
                raw,
                row + x * 2,
            )[0]

            r5 = v & 0x1F
            g6 = (v >> 5) & 0x3F
            b5 = (v >> 11) & 0x1F

            r = (r5 << 3) | (r5 >> 2)
            g = (g6 << 2) | (g6 >> 4)
            b = (b5 << 3) | (b5 >> 2)

            pixels.append(
                (r,g,b)
            )

    im = Image.new(
        "RGB",
        (FB_W, FB_H),
    )
    im.putdata(pixels)
    return im


def dump_framebuffers(ws):
    result = []

    for addr in FRAMEBUFFERS:
        item = {
            "address":
                f"0x{addr:08X}",
        }

        try:
            raw = read_ws(
                ws,
                addr,
                FB_STRIDE
                * FB_H
                * FB_BPP,
            )

            path = (
                OUT
                / f"stage40e_vram_{addr:08X}.png"
            )

            im = rgb565_to_image(raw)
            im.save(path)

            item.update({
                "captured": True,
                "path": str(path),
                "size": list(im.size),
            })
        except Exception as e:
            item.update({
                "captured": False,
                "error": str(e),
            })

        result.append(item)

    return result


def runtime_test(local_mod, b):
    exe = b.find_ppsspp_exe()

    cfg = OUT / "stage40e_append.ini"
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
        str(SOURCE_ISO),
    ]

    log("[Stage40E] Launching PPSSPP")
    proc = subprocess.Popen(cmd)
    cleanup = b.register_ppsspp_auto_close(
        proc
    )

    result = {
        "pid": proc.pid,
    }

    try:
        hwnd = b.find_ppsspp_hwnd(30)

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

        try:
            result["debugger_host"] = host
            result["debugger_port"] = actual_port

            ready = wait_cpu_ready(ws)
            result["cpu_ready"] = ready

            if not ready.get("ready"):
                raise RuntimeError(
                    "CPU did not become ready"
                )

            result["renderer_jal"] = {
                "actual":
                    read_ws(
                        ws,
                        RENDER_CALL_RUNTIME,
                        4,
                    ).hex(),
                "expected":
                    EXPECTED_RENDER_JAL_RUNTIME.hex(),
            }

            menu = wait_menu_resource(ws)
            result["menu_resource"] = menu

            if not menu.get("opened"):
                raise RuntimeError(
                    "MENUINT0.RAW did not open"
                )

            # Title settle, then ONE Start only.
            time.sleep(2.5)
            ws.request(
                "input.buttons.press",
                timeout=5,
                button="start",
                duration=2,
            )

            story = scan_for_story_utf16(
                ws,
                timeout=12,
            )
            result["menu_confirmed"] = story

            if not story.get("found"):
                raise RuntimeError(
                    "Selectable menu Story object did not appear"
                )

            # Let the real menu render a few frames.
            time.sleep(1.0)

            # Now prove the stream23 data really exists in live RAM.
            direct = verify_direct_allocations(ws)
            result["stream23_allocations"] = direct

            # Search for the actual metadata triplets anywhere in main RAM.
            patterns = {}

            for item in MENU_VALUES:
                patterns[
                    f"metadata_{item['label']}"
                ] = struct.pack(
                    "<III",
                    item["ptr"],
                    item["num"],
                    item["num"],
                )

                patterns[
                    f"utf8_{item['label']}"
                ] = (
                    item["ko"].encode("utf-8")
                    + b"\x00"
                )

                patterns[
                    f"utf16_{item['label']}"
                ] = (
                    item["ko"].encode("utf-16le")
                    + b"\x00\x00"
                )

            patterns["utf16_Story"] = (
                "스토리".encode("utf-16le")
                + b"\x00\x00"
            )

            result["ram_pattern_hits"] = (
                scan_ram_patterns(
                    ws,
                    patterns,
                )
            )

            # Actual renderer proof. Use one character unique to each visible
            # menu label (Story second char, Skirmish second char, etc.).
            probes = [
                ("Story", STORY_PROBE_CHAR),
                ("Skirmish", "커"),
                ("Options", "옵"),
                ("Profile", "프"),
            ]

            result["renderer_unicode_probes"] = []

            for label, ch in probes:
                p = lookup_renderer_probe(
                    ws,
                    ch,
                    timeout=18,
                )
                p["label"] = label
                result[
                    "renderer_unicode_probes"
                ].append(p)

            # Font must be initialized at this point.
            glyph_count = struct.unpack(
                "<H",
                read_ws(
                    ws,
                    FONT_OBJECT + 0x50,
                    2,
                ),
            )[0]

            glyph_ptr = struct.unpack(
                "<I",
                read_ws(
                    ws,
                    FONT_OBJECT + 0x54,
                    4,
                ),
            )[0]

            result["font_after_menu"] = {
                "glyph_count": glyph_count,
                "glyph_count_ok":
                    glyph_count
                    == EXPECTED_GLYPH_COUNT,
                "glyph_ptr":
                    f"0x{glyph_ptr:08X}",
                "glyph_ptr_ok":
                    glyph_ptr
                    == EXPECTED_GLYPH_PTR,
            }

            # Raw VRAM capture bypasses the window screenshot helper, which in
            # Stage40D captured PPSSPP's Developer Menu overlay instead of the
            # PSP framebuffer.
            result["vram_framebuffers"] = (
                dump_framebuffers(ws)
            )

            direct_ok = all(
                x.get("ok",False)
                for x in direct
            )
            probes_ok = all(
                x.get("hit",False)
                for x in result[
                    "renderer_unicode_probes"
                ]
            )
            vram_ok = any(
                x.get("captured",False)
                for x in result[
                    "vram_framebuffers"
                ]
            )

            result["ok"] = (
                result["renderer_jal"]["actual"]
                == result["renderer_jal"]["expected"]
                and direct_ok
                and probes_ok
                and result["font_after_menu"][
                    "glyph_count_ok"
                ]
                and result["font_after_menu"][
                    "glyph_ptr_ok"
                ]
                and vram_ok
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
        "stage": "40E",
        "purpose":
            "Re-evaluate Stage40D using live-RAM pointer search, actual Unicode "
            "renderer breakpoints, and raw PSP VRAM captures instead of the "
            "misleading early metadata addresses/window screenshot.",
        "stage40d_key_findings": {
            "build":
                "The three translations rebuilt correctly and point into "
                "stream23.",
            "runtime":
                "All four Korean labels (Story, Skirmish, Options, Profile) "
                "were found as proper UTF-16 strings in RAM after entering menu.",
            "font":
                "Production font remained correct: 847 / 0x098F5020.",
            "old_runtime_metadata_check":
                "0x095EC790 etc. were sampled before the relevant live object "
                "was initialized and read as zero. Stage40E searches the real "
                "ptr/Num/Max triplets across main RAM after menu initialization.",
            "old_screenshot":
                "The Stage40D window capture shows PPSSPP's Developer Menu "
                "overlay, not a reliable PSP framebuffer. Stage40E dumps both "
                "raw 480x272 RGB565 VRAM buffers directly.",
        },
    }

    try:
        report["source"] = (
            ensure_stage40d_iso()
        )

        local_mod, b = load_helpers()

        report["runtime"] = runtime_test(
            local_mod,
            b,
        )

        report["completed"] = bool(
            report["runtime"].get(
                "ok", False
            )
        )

    except Exception as e:
        report["runtime_exception"] = str(e)
        report["runtime_traceback"] = (
            traceback.format_exc()
        )
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
            f"Stage40E failed. See {FAIL_ZIP}"
        )

    log("[Stage40E] COMPLETE")
    log(
        f"[Stage40E] Upload ZIP: "
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
            f"STAGE 40E FAILED: "
            f"{FAIL_ZIP}",
            flush=True,
        )
        raise SystemExit(1)
