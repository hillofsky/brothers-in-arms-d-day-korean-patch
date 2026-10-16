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

OUT = ROOT / "analysis" / "stage40h_localize_encoding_retry"
LOG_DIR = ROOT / "log"

SUCCESS_ZIP = LOG_DIR / "bia_stage40h_upload.zip"
FAIL_ZIP = LOG_DIR / "fail_bia_stage40h_upload.zip"
REPORT_PATH = OUT / "stage40h_retry_report.json"

TARGET_LOCALIZE = [
    "PSP_GAME",
    "USRDIR",
    "SYSTEM",
    "LOCALIZE.INT",
]

# Canonical untouched USA v1.01 LOCALIZE.INT.
CANONICAL_SHA1 = "da7dedd4a2dfa6bbbff379e1cd28984c99f8deb5"

# Old Stage04B diagnostic file. It differs from the canonical file only by:
# Story->LSTRY, Options->L_OPTNS, Skirmish->L_SKIRM_.
OLD_STAGE04B_SHA1 = "800615456f22384e43465bed5b90f29942c190ef"

MENU_OPEN_MARKER = (
    "sceIoOpen(disc0:/PSP_GAME/USRDIR/SYSTEM/RAWFILES/MENUINT0.RAW"
)
LOCALIZE_OPEN_MARKER = "LOCALIZE.INT"

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

# Order is deliberate.
# mixed_utf8 is the most important candidate: only Korean values become UTF-8,
# while every other byte in the original cp1252-ish INT file remains untouched.
VARIANTS = [
    "mixed_utf8",
    "mixed_utf8_bom",
    "mixed_cp949",
    "whole_utf16le_bom",
]

RENDER_CALL_RUNTIME = 0x08972360
EXPECTED_RENDER_JAL_RUNTIME = bytes.fromhex("e410330e")
FONT_OBJECT = 0x0972385C
EXPECTED_GLYPH_COUNT = 847
EXPECTED_GLYPH_PTR = 0x098F5020

FAST_SCAN_START = 0x08E00000
FAST_SCAN_END = 0x09A00000
RAM_START = 0x08800000
RAM_END = 0x0A800000
CHUNK = 0x20000


def log(msg):
    print(msg, flush=True)


def sha1(data):
    return hashlib.sha1(data).hexdigest()


def load_helpers():
    p = BASE_TOOLS / "bia_stage39b_compiled_mdi_text.py"
    if not p.exists():
        raise RuntimeError(f"Missing Stage39B helper: {p}")

    sys.path.insert(0, str(BASE_TOOLS))
    spec = importlib.util.spec_from_file_location("bia_stage39b_local", p)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)

    b = getattr(mod, "b", None)
    if b is None and hasattr(mod, "s39"):
        b = getattr(mod.s39, "b", None)
    if b is None:
        raise RuntimeError("Could not resolve Stage39B helpers")
    return mod, b


def canonicalize_localize(raw):
    h = sha1(raw)

    if h == CANONICAL_SHA1:
        return raw, {
            "input_sha1": h,
            "normalized": False,
            "canonical_sha1": CANONICAL_SHA1,
        }

    if h != OLD_STAGE04B_SHA1:
        raise RuntimeError(
            "Unexpected LOCALIZE.INT source SHA1. "
            f"known={CANONICAL_SHA1}/{OLD_STAGE04B_SHA1} actual={h}"
        )

    # Restore only the three known equal-length Stage04B placeholders.
    replacements = [
        (b"MAINMENU_SINGLEPLAYER=LSTRY", b"MAINMENU_SINGLEPLAYER=Story"),
        (b"MAINMENU_OPTIONS=L_OPTNS", b"MAINMENU_OPTIONS=Options"),
        (b"MAINMENU_SKIRMISH=L_SKIRM_", b"MAINMENU_SKIRMISH=Skirmish"),
    ]

    out = raw
    counts = {}

    for old, new in replacements:
        c = out.count(old)
        if c != 1:
            raise RuntimeError(
                f"Stage04B normalization expected exactly one {old!r}, got {c}"
            )
        out = out.replace(old, new, 1)
        counts[old.decode("ascii")] = c

    nh = sha1(out)
    if nh != CANONICAL_SHA1:
        raise RuntimeError(
            f"Stage04B normalization hash mismatch: {nh}"
        )

    return out, {
        "input_sha1": h,
        "normalized": True,
        "normalization_counts": counts,
        "canonical_sha1": nh,
    }


def patch_ascii_values_bytes(raw, encoding):
    """
    Patch only the exact ASCII value bytes after the exact key prefix.
    This preserves every unrelated byte in LOCALIZE.INT.
    """
    out = raw
    changes = []

    for p in PROBES:
        prefix = (p["key"] + "=").encode("ascii")
        old = prefix + p["english"].encode("ascii")
        new_value = p["korean"].encode(encoding)
        new = prefix + new_value

        count = out.count(old)
        if count != 1:
            raise RuntimeError(
                f"{p['key']}: expected one exact source occurrence, got {count}"
            )

        pos = out.find(old)
        out = out[:pos] + new + out[pos + len(old):]

        changes.append({
            "id": p["id"],
            "key": p["key"],
            "english": p["english"],
            "korean": p["korean"],
            "offset_before": f"0x{pos:X}",
            "encoding": encoding,
            "old_bytes": len(p["english"].encode("ascii")),
            "new_bytes": len(new_value),
            "new_hex": new_value.hex(),
        })

    return out, changes


def build_variant_bytes(canonical, variant):
    if variant == "mixed_utf8":
        data, changes = patch_ascii_values_bytes(canonical, "utf-8")
        return data, changes

    if variant == "mixed_utf8_bom":
        data, changes = patch_ascii_values_bytes(canonical, "utf-8")
        return b"\xef\xbb\xbf" + data, changes

    if variant == "mixed_cp949":
        data, changes = patch_ascii_values_bytes(canonical, "cp949")
        return data, changes

    if variant == "whole_utf16le_bom":
        # cp1252 is the semantic encoding detected by the original Stage02
        # inventory and round-trips the canonical file byte-for-byte.
        text = canonical.decode("cp1252")
        patched = text

        changes = []
        for p in PROBES:
            old = p["key"] + "=" + p["english"]
            new = p["key"] + "=" + p["korean"]
            count = patched.count(old)
            if count != 1:
                raise RuntimeError(
                    f"{p['key']}: whole-file source count={count}"
                )
            patched = patched.replace(old, new, 1)
            changes.append({
                "id": p["id"],
                "key": p["key"],
                "english": p["english"],
                "korean": p["korean"],
                "encoding": "utf-16le",
            })

        return b"\xff\xfe" + patched.encode("utf-16le"), changes

    raise ValueError(variant)


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
                    "localize_seen_in_log": LOCALIZE_OPEN_MARKER in txt,
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


def best_effort_enter_options(ws):
    """
    Enter the selectable main menu, then try to open Options.
    This is not a pass/fail condition; it just encourages controller-option
    localization objects to be instantiated before the RAM scan.
    """
    events = []

    def press(button, duration=2, wait=0.35):
        try:
            ws.request(
                "input.buttons.press",
                timeout=4,
                button=button,
                duration=duration,
            )
            events.append({"button": button, "ok": True})
        except Exception as e:
            events.append({
                "button": button,
                "ok": False,
                "error": str(e),
            })
        time.sleep(wait)

    time.sleep(2.0)
    press("start", wait=1.0)
    press("down")
    press("down")
    press("cross", wait=1.0)

    return events


def pattern_forms(text):
    utf8 = text.encode("utf-8")
    cp949 = text.encode("cp949")
    utf16 = text.encode("utf-16le")
    widened_utf8 = b"".join(bytes((b, 0)) for b in utf8)
    widened_cp949 = b"".join(bytes((b, 0)) for b in cp949)

    return {
        "utf8": utf8,
        "cp949": cp949,
        "utf16le": utf16,
        "widened_utf8_u16": widened_utf8,
        "widened_cp949_u16": widened_cp949,
    }


def scan_region(ws, start_addr, end_addr, needles):
    hits = {
        name: {form: None for form in forms}
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

    def compatible(hits, pid):
        # Proper Unicode is ideal. Widened UTF-8 is also valid because the
        # Stage39U renderer helper is already proven to decode that exact form.
        return (
            hits[pid]["utf16le"] is not None
            or hits[pid]["widened_utf8_u16"] is not None
        )

    if all(compatible(fast, p["id"]) for p in PROBES):
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


def evaluate_hits(scan):
    hits = scan["hits"]
    details = {}
    all_compatible = True

    for p in PROBES:
        h = hits[p["id"]]
        proper = h["utf16le"] is not None
        widened_utf8 = h["widened_utf8_u16"] is not None

        details[p["id"]] = {
            "proper_utf16": proper,
            "widened_utf8": widened_utf8,
            "compatible_with_stage39u_renderer": proper or widened_utf8,
        }

        if not (proper or widened_utf8):
            all_compatible = False

    return {
        "all_compatible": all_compatible,
        "per_probe": details,
    }


def runtime_attempt(b, variant):
    exe = b.find_ppsspp_exe()
    log_path = OUT / f"stage40h_retry_{variant}_ppsspp.log"
    cfg = OUT / f"stage40h_retry_{variant}_append.ini"

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

    log(f"[Stage40H retry] Launching variant={variant}")
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

        actual_port = b.wait_for_actual_debugger_port(log_path, 30)
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

            menu = wait_menu_resource(ws, log_path)
            result["menu_resource"] = menu
            if not menu.get("opened"):
                raise RuntimeError("MENUINT0.RAW did not open")

            result["navigation"] = best_effort_enter_options(ws)

            time.sleep(0.75)
            result["probe_scan"] = scan_probes(ws)
            result["compatibility"] = evaluate_hits(result["probe_scan"])

            glyph_count = int.from_bytes(
                read_ws(ws, FONT_OBJECT + 0x50, 2),
                "little",
            )
            glyph_ptr = int.from_bytes(
                read_ws(ws, FONT_OBJECT + 0x54, 4),
                "little",
            )

            result["font"] = {
                "glyph_count": glyph_count,
                "glyph_count_ok": glyph_count == EXPECTED_GLYPH_COUNT,
                "glyph_ptr": f"0x{glyph_ptr:08X}",
                "glyph_ptr_ok": glyph_ptr == EXPECTED_GLYPH_PTR,
            }

            result["ok"] = (
                result["renderer_jal"]["actual"]
                == result["renderer_jal"]["expected"]
                and result["compatibility"]["all_compatible"]
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


def prepare_variant_iso(b, canonical_localize, variant):
    if TEST_ISO.exists():
        TEST_ISO.unlink()

    shutil.copy2(SOURCE_ISO, TEST_ISO)

    encoded, changes = build_variant_bytes(
        canonical_localize,
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
        "patched_sha1": sha1(encoded),
        "patched_bytes": len(encoded),
        "changes": changes,
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

    report = {
        "stage": "40H-retry",
        "purpose":
            "Fix the false source-hash gate and determine a loose LOCALIZE.INT "
            "Korean byte encoding compatible with the already-proven Stage39U "
            "renderer.",
        "previous_failure":
            "Stage40H stopped before any ISO variant/runtime test because it "
            "incorrectly expected the old Stage04B diagnostic SHA1 "
            "800615... The Stage40F ISO contains the canonical untouched "
            "LOCALIZE.INT SHA1 da7dedd4..., which is the correct baseline.",
        "source_iso": str(SOURCE_ISO),
        "test_iso": str(TEST_ISO),
        "attempts": [],
        "selected_variant": None,
    }

    try:
        if not SOURCE_ISO.exists():
            raise RuntimeError(
                f"Missing Stage40F ISO: {SOURCE_ISO}"
            )

        _, b = load_helpers()

        _, source_localize = b.iso_read_file(
            SOURCE_ISO,
            TARGET_LOCALIZE,
        )

        canonical, norm = canonicalize_localize(
            source_localize
        )
        report["source_localize"] = norm

        selected = None

        for variant in VARIANTS:
            attempt = {
                "variant": variant,
            }

            try:
                attempt["build"] = prepare_variant_iso(
                    b,
                    canonical,
                    variant,
                )
                attempt["runtime"] = runtime_attempt(
                    b,
                    variant,
                )
            except Exception as e:
                attempt["exception"] = str(e)
                attempt["traceback"] = traceback.format_exc()

            report["attempts"].append(attempt)

            if attempt.get("runtime", {}).get("ok", False):
                selected = variant
                report["selected_variant"] = variant
                break

        report["completed"] = selected is not None

    except Exception as e:
        report["top_level_exception"] = str(e)
        report["top_level_traceback"] = traceback.format_exc()
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
            f"Stage40H retry found no proven compatible encoding. See {FAIL_ZIP}"
        )

    log("[Stage40H retry] COMPLETE")
    log(
        f"[Stage40H retry] selected encoding: "
        f"{report['selected_variant']}"
    )
    log(f"[Stage40H retry] retained ISO: {TEST_ISO}")
    log(f"[Stage40H retry] upload ZIP: {SUCCESS_ZIP}")


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
                        "stage": "40H-retry",
                        "completed": False,
                        "fatal_traceback": traceback.format_exc(),
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
            f"STAGE 40H RETRY FAILED: {FAIL_ZIP}",
            flush=True,
        )
        raise SystemExit(1)
