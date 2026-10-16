#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import time
import traceback
import zipfile
from pathlib import Path

ROOT = Path(r"PROJECT_ROOT")
BASE_TOOLS = ROOT / "bia_stage39b_tools"

SOURCE_ISO = ROOT / "BIA_STAGE40F_ON_MEMU_RESIDENT_MASS_TEST.iso"
TEST_ISO = ROOT / "BIA_STAGE40H_LOCALIZE_ENCODING_TEST.iso"

OUT = ROOT / "analysis" / "stage40h_localize_encoding"
LOG_DIR = ROOT / "log"

SUCCESS_ZIP = LOG_DIR / "bia_stage40h_upload.zip"
FAIL_ZIP = LOG_DIR / "fail_bia_stage40h_upload.zip"
REPORT_PATH = OUT / "stage40h_report.json"

TARGET_LOCALIZE = [
    "PSP_GAME",
    "USRDIR",
    "SYSTEM",
    "LOCALIZE.INT",
]

EXPECTED_LOCALIZE_SHA1 = "800615456f22384e43465bed5b90f29942c190ef"

MENU_OPEN_MARKER = (
    "sceIoOpen(disc0:/PSP_GAME/USRDIR/SYSTEM/RAWFILES/MENUINT0.RAW"
)

# All four are A-priority rows that Stage40B did NOT find in any compiled MDI.
# Therefore seeing these Korean strings in runtime memory after patching
# LOCALIZE.INT is a clean proof that the loose INT source is actually loaded.
PROBES = [
    {
        "id": "BIA-00514",
        "section": "MENU",
        "key": "MENU0PTION_CONTROLLER_CONFIG",
        "english": "Controls Config",
        "korean": "조작 설정",
    },
    {
        "id": "BIA-00625",
        "section": "MENU",
        "key": "MENU0PTION_CONTROLLER_HORZ_SEN",
        "english": "Horizontal Sensitivity",
        "korean": "수평 감도",
    },
    {
        "id": "BIA-01052",
        "section": "MENU",
        "key": "MENU0PTION_CONTROLLER_VERT_SEN",
        "english": "Vertical Sensitivity",
        "korean": "수직 감도",
    },
    {
        "id": "BIA-01054",
        "section": "MENU",
        "key": "MENU0PTION_CONTROLLER_VIBRATION",
        "english": "Vibration",
        "korean": "진동",
    },
]

VARIANTS = [
    "utf8",
    "utf8_bom",
    "utf16le_bom",
]

# Localization/runtime object region. If needed, the fallback scans all 32 MiB.
FAST_SCAN_START = 0x08E00000
FAST_SCAN_END = 0x09A00000
RAM_START = 0x08800000
RAM_END = 0x0A800000
CHUNK = 0x20000

RENDER_CALL_RUNTIME = 0x08972360
EXPECTED_RENDER_JAL_RUNTIME = bytes.fromhex("e410330e")
FONT_OBJECT = 0x0972385C
EXPECTED_GLYPH_COUNT = 847
EXPECTED_GLYPH_PTR = 0x098F5020


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
        "bia_stage39b_local",
        p,
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


def decode_localize(raw):
    if raw.startswith(b"\xff\xfe"):
        return raw[2:].decode("utf-16le"), "utf16le_bom"
    if raw.startswith(b"\xfe\xff"):
        return raw[2:].decode("utf-16be"), "utf16be_bom"

    try:
        return raw.decode("utf-8-sig"), "utf8"
    except UnicodeDecodeError:
        return raw.decode("cp1252"), "cp1252"


def encode_variant(text, variant):
    if variant == "utf8":
        return text.encode("utf-8")
    if variant == "utf8_bom":
        return b"\xef\xbb\xbf" + text.encode("utf-8")
    if variant == "utf16le_bom":
        return b"\xff\xfe" + text.encode("utf-16le")
    raise ValueError(variant)


def patch_probe_values(text):
    # Exact section/key/value patching only.
    wanted = {
        (p["section"], p["key"]): p
        for p in PROBES
    }

    found = set()
    current_section = ""
    out = []

    for line_no, line in enumerate(
        text.splitlines(keepends=True),
        1,
    ):
        body = line.rstrip("\r\n")
        newline = line[len(body):]
        stripped = body.strip()

        if stripped.startswith("[") and stripped.endswith("]"):
            current_section = stripped[1:-1].strip()
            out.append(line)
            continue

        if "=" not in body:
            out.append(line)
            continue

        left, right = body.split("=", 1)
        key = left.strip()
        target = wanted.get((current_section, key))

        if target is None:
            out.append(line)
            continue

        raw_value = right.strip()
        prefix = right[:len(right) - len(right.lstrip())]
        suffix = right[len(right.rstrip()):]

        quote = ""
        core = raw_value

        if len(raw_value) >= 2 and raw_value.startswith('"') and raw_value.endswith('"'):
            quote = '"'
            core = raw_value[1:-1]

        if core != target["english"]:
            raise RuntimeError(
                f"{current_section}:{key} line {line_no}: "
                f"expected {target['english']!r}, got {core!r}"
            )

        replacement = quote + target["korean"] + quote
        out.append(
            left + "=" + prefix + replacement + suffix + newline
        )
        found.add((current_section, key))

    missing = set(wanted) - found
    if missing:
        raise RuntimeError(
            f"Probe LOCALIZE entries not found: {sorted(missing)}"
        )

    return "".join(out)


def read_ws(ws, address, size):
    r = ws.request(
        "memory.read",
        timeout=10,
        address=address,
        size=size,
    )
    return base64.b64decode(r["base64"])


def wait_cpu_ready(ws, timeout=20):
    end = time.time() + timeout
    attempts = 0
    last_error = None

    while time.time() < end:
        attempts += 1
        try:
            status = ws.request("cpu.status", timeout=2)
            probe = read_ws(ws, RENDER_CALL_RUNTIME, 4)

            if len(probe) == 4:
                return {
                    "ready": True,
                    "attempts": attempts,
                    "status": status,
                    "renderer_probe": probe.hex(),
                }
        except Exception as e:
            last_error = str(e)

        time.sleep(0.05)

    return {
        "ready": False,
        "attempts": attempts,
        "last_error": last_error,
    }


def wait_menu_resource(ws, log_path, timeout=180):
    end = time.time() + timeout
    last_press = 0.0
    presses = 0

    while time.time() < end:
        if log_path.exists():
            txt = log_path.read_text(
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


def pattern_forms(text):
    utf8 = text.encode("utf-8")
    utf16 = text.encode("utf-16le")
    widened = b"".join(
        bytes((x, 0))
        for x in utf8
    )

    return {
        "utf8": utf8,
        "utf16le": utf16,
        "widened_utf8_u16": widened,
    }


def scan_region(ws, start_addr, end_addr, needles):
    hits = {
        name: {
            form: None
            for form in forms
        }
        for name, forms in needles.items()
    }

    max_len = max(
        len(blob)
        for forms in needles.values()
        for blob in forms.values()
    )
    overlap = max(0, max_len - 1)

    prev = b""
    addr = start_addr

    while addr < end_addr:
        size = min(CHUNK, end_addr - addr)

        try:
            block = read_ws(ws, addr, size)
        except Exception:
            prev = b""
            addr += size
            continue

        data = prev + block
        base = addr - len(prev)

        for name, forms in needles.items():
            for form, needle in forms.items():
                if hits[name][form] is not None:
                    continue

                pos = data.find(needle)
                if pos >= 0:
                    hits[name][form] = f"0x{base+pos:08X}"

        prev = data[-overlap:] if overlap else b""
        addr += size

    return hits


def scan_probes(ws):
    needles = {
        p["id"]: pattern_forms(p["korean"])
        for p in PROBES
    }

    fast = scan_region(
        ws,
        FAST_SCAN_START,
        FAST_SCAN_END,
        needles,
    )

    # If every probe has proper UTF-16, no need to scan all 32 MiB.
    if all(
        fast[p["id"]]["utf16le"] is not None
        for p in PROBES
    ):
        return {
            "scope": "fast",
            "start": f"0x{FAST_SCAN_START:08X}",
            "end": f"0x{FAST_SCAN_END:08X}",
            "hits": fast,
        }

    full = scan_region(
        ws,
        RAM_START,
        RAM_END,
        needles,
    )

    return {
        "scope": "full",
        "start": f"0x{RAM_START:08X}",
        "end": f"0x{RAM_END:08X}",
        "hits": full,
    }


def runtime_attempt(b, variant):
    exe = b.find_ppsspp_exe()
    log_path = OUT / f"stage40h_{variant}_ppsspp.log"
    cfg = OUT / f"stage40h_{variant}_append.ini"

    cfg.write_text(
        "[Debugger]\n"
        "ShowDeveloperMenu = True\n"
        "\n"
        "[Graphics]\n"
        "ReplaceTextures = False\n"
        "SaveNewTextures = False\n",
        encoding="utf-8",
    )

    if log_path.exists():
        log_path.unlink()

    try:
        b.close_existing_ppsspp(timeout=3.0)
    except Exception:
        pass

    port = b.choose_free_port()

    cmd = [
        str(exe),
        "-d",
        f"--log={log_path}",
        "--windowed",
        f"--appendconfig={cfg}",
        f"--debugger={port}",
        str(TEST_ISO),
    ]

    log(f"[Stage40H] Launching PPSSPP variant={variant}")
    proc = subprocess.Popen(cmd)
    cleanup = b.register_ppsspp_auto_close(proc)

    result = {
        "variant": variant,
        "pid": proc.pid,
    }

    try:
        hwnd = b.find_ppsspp_hwnd(30)
        if not hwnd:
            raise RuntimeError("PPSSPP window did not appear")

        actual_port = b.wait_for_actual_debugger_port(
            log_path,
            30,
        )
        ws, host = b.connect_debugger(actual_port)

        try:
            result["debugger_host"] = host
            result["debugger_port"] = actual_port

            ready = wait_cpu_ready(ws)
            result["cpu_ready"] = ready
            if not ready.get("ready"):
                raise RuntimeError("CPU did not become ready")

            result["renderer_jal"] = {
                "actual": read_ws(
                    ws,
                    RENDER_CALL_RUNTIME,
                    4,
                ).hex(),
                "expected": EXPECTED_RENDER_JAL_RUNTIME.hex(),
            }

            menu = wait_menu_resource(
                ws,
                log_path,
            )
            result["menu_resource"] = menu
            if not menu.get("opened"):
                raise RuntimeError("MENUINT0.RAW did not open")

            # Allow localization tables to settle.
            time.sleep(1.0)

            result["probe_scan"] = scan_probes(ws)

            glyph_count = int.from_bytes(
                read_ws(
                    ws,
                    FONT_OBJECT + 0x50,
                    2,
                ),
                "little",
            )
            glyph_ptr = int.from_bytes(
                read_ws(
                    ws,
                    FONT_OBJECT + 0x54,
                    4,
                ),
                "little",
            )

            result["font"] = {
                "glyph_count": glyph_count,
                "glyph_count_ok": glyph_count == EXPECTED_GLYPH_COUNT,
                "glyph_ptr": f"0x{glyph_ptr:08X}",
                "glyph_ptr_ok": glyph_ptr == EXPECTED_GLYPH_PTR,
            }

            hits = result["probe_scan"]["hits"]

            proper = all(
                hits[p["id"]]["utf16le"] is not None
                for p in PROBES
            )
            widened = all(
                hits[p["id"]]["widened_utf8_u16"] is not None
                for p in PROBES
            )
            raw_utf8 = all(
                hits[p["id"]]["utf8"] is not None
                for p in PROBES
            )

            result["all_proper_utf16"] = proper
            result["all_widened_utf8_u16"] = widened
            result["all_raw_utf8"] = raw_utf8

            result["ok"] = (
                result["renderer_jal"]["actual"]
                == result["renderer_jal"]["expected"]
                and proper
                and result["font"]["glyph_count_ok"]
                and result["font"]["glyph_ptr_ok"]
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


def prepare_variant_iso(b, original_localize, variant):
    if TEST_ISO.exists():
        TEST_ISO.unlink()

    shutil.copy2(
        SOURCE_ISO,
        TEST_ISO,
    )

    text, original_encoding = decode_localize(
        original_localize
    )
    patched_text = patch_probe_values(text)
    encoded = encode_variant(
        patched_text,
        variant,
    )

    b.append_iso_file_and_repoint(
        TEST_ISO,
        TARGET_LOCALIZE,
        encoded,
    )

    _, rb = b.iso_read_file(
        TEST_ISO,
        TARGET_LOCALIZE,
    )

    if rb != encoded:
        raise RuntimeError(
            f"{variant}: LOCALIZE.INT ISO readback mismatch"
        )

    return {
        "variant": variant,
        "original_encoding": original_encoding,
        "original_sha1": sha1(original_localize),
        "patched_sha1": sha1(encoded),
        "patched_bytes": len(encoded),
        "iso_readback_ok": True,
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

    if not SOURCE_ISO.exists():
        raise RuntimeError(
            f"Missing Stage40F ISO: {SOURCE_ISO}"
        )

    _, b = load_helpers()

    _, original_localize = b.iso_read_file(
        SOURCE_ISO,
        TARGET_LOCALIZE,
    )

    original_sha = sha1(original_localize)

    report = {
        "stage": "40H",
        "purpose":
            "Determine the actual on-disc encoding accepted by loose "
            "LOCALIZE.INT for A-priority strings absent from all scanned MDIs.",
        "source_iso": str(SOURCE_ISO),
        "test_iso": str(TEST_ISO),
        "original_localize_sha1": original_sha,
        "expected_original_localize_sha1": EXPECTED_LOCALIZE_SHA1,
        "original_sha1_ok": original_sha == EXPECTED_LOCALIZE_SHA1,
        "probes": PROBES,
        "attempts": [],
        "selected_variant": None,
    }

    if original_sha != EXPECTED_LOCALIZE_SHA1:
        raise RuntimeError(
            "LOCALIZE.INT source SHA1 changed unexpectedly. "
            f"expected={EXPECTED_LOCALIZE_SHA1} actual={original_sha}"
        )

    selected = None

    for variant in VARIANTS:
        build = prepare_variant_iso(
            b,
            original_localize,
            variant,
        )

        attempt = {
            "build": build,
        }

        try:
            attempt["runtime"] = runtime_attempt(
                b,
                variant,
            )
        except Exception as e:
            attempt["runtime_exception"] = str(e)
            attempt["runtime_traceback"] = traceback.format_exc()

        report["attempts"].append(attempt)

        if attempt.get("runtime", {}).get("ok", False):
            selected = variant
            report["selected_variant"] = variant
            break

    report["completed"] = selected is not None

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
            f"Stage40H found no proven loose-INT encoding. See {FAIL_ZIP}"
        )

    log("[Stage40H] COMPLETE")
    log(f"[Stage40H] selected encoding: {selected}")
    log(f"[Stage40H] retained ISO: {TEST_ISO}")
    log(f"[Stage40H] upload ZIP: {SUCCESS_ZIP}")


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
            f"STAGE 40H FAILED: {FAIL_ZIP}",
            flush=True,
        )
        raise SystemExit(1)
