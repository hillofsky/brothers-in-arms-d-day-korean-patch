#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import base64
import importlib.util
import json
import os
import subprocess
import sys
import time
import traceback
import zipfile
from pathlib import Path

ROOT = Path(r"PROJECT_ROOT")
BASE_TOOLS = ROOT / "bia_stage39b_tools"

TEST_ISO = ROOT / "BIA_STAGE39F_CORRECT_NARROW_METADATA_TEST.iso"

OUT = ROOT / "analysis" / "stage39h_main_menu_visual_proof"
LOG_DIR = ROOT / "log"

SUCCESS_ZIP = LOG_DIR / "bia_stage39h_upload.zip"
FAIL_ZIP = LOG_DIR / "fail_bia_stage39h_upload.zip"

REPORT_PATH = OUT / "stage39h_report.json"
PPSSPP_LOG = OUT / "stage39h_ppsspp.log"

# Correct Stage39F source structures.
DISPLAY1_ADDR = 0x093B1B40
MENUSTORY_KEY_ADDR = 0x093B1BB0
DISPLAY2_ADDR = 0x093B1BF0

META1_ADDR = 0x095EC774
META2_ADDR = 0x095F1758

TEST_TEXT = "\uc2a4\ud1a0\ub9ac"
UTF8 = TEST_TEXT.encode("utf-8")
UTF8_NUL = UTF8 + b"\x00"
UTF16 = TEST_TEXT.encode("utf-16le")

EXPECTED_META1 = (DISPLAY1_ADDR, 10, 10)
EXPECTED_META2 = (DISPLAY2_ADDR, 10, 10)

# Stage39G already found real UTF-16 Korean at these addresses before any
# input.  These are diagnostic observations, not fixed-slot success criteria.
STAGE39G_UTF16_MATCHES = [
    0x08E416C0,
    0x08E431A0,
    0x08FF4B89,
]

# Focused dynamic region.  This is much faster than Stage39G's full 32 MiB
# ReadProcessMemory scan and contains the two aligned Stage39G matches.
FOCUS_START = 0x08E00000
FOCUS_SIZE = 0x00200000

MENU_PATTERNS = {
    "korean_story": UTF16,
    "OPTIONS": "OPTIONS".encode("utf-16le"),
    "Options": "Options".encode("utf-16le"),
    "EXTRAS": "EXTRAS".encode("utf-16le"),
    "Extras": "Extras".encode("utf-16le"),
    "PROFILE": "PROFILE".encode("utf-16le"),
    "Profile": "Profile".encode("utf-16le"),
    "CONTINUE": "CONTINUE".encode("utf-16le"),
    "Continue": "Continue".encode("utf-16le"),
}

MENU_OPEN_LOG_MARKER = (
    "sceIoOpen(disc0:/PSP_GAME/USRDIR/SYSTEM/RAWFILES/MENUINT0.RAW"
)

SCRIPT_DIR = Path(__file__).resolve().parent


def log(msg: str):
    # ASCII-only console messages avoid the Stage39C CP949 console problem.
    print(msg, flush=True)


def load_helpers():
    module_path = BASE_TOOLS / "bia_stage39b_compiled_mdi_text.py"
    if not module_path.exists():
        raise RuntimeError(f"Missing Stage39B helper: {module_path}")

    sys.path.insert(0, str(BASE_TOOLS))
    spec = importlib.util.spec_from_file_location(
        "bia_stage39b_local",
        module_path,
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


def read_ws(ws, address, size):
    r = ws.request(
        "memory.read",
        timeout=10,
        address=address,
        size=size,
    )
    return base64.b64decode(r["base64"])


def verify_sources(ws):
    import struct

    d1 = read_ws(ws, DISPLAY1_ADDR, 16)
    key = read_ws(ws, MENUSTORY_KEY_ADDR, 16)
    d2 = read_ws(ws, DISPLAY2_ADDR, 16)

    m1 = struct.unpack("<III", read_ws(ws, META1_ADDR, 12))
    m2 = struct.unpack("<III", read_ws(ws, META2_ADDR, 12))

    return {
        "display1_hex": d1.hex(),
        "display1_ok": d1.startswith(UTF8_NUL),
        "menustory_key_hex": key.hex(),
        "menustory_key_ok": key.startswith(b"MenuStory\x00"),
        "display2_hex": d2.hex(),
        "display2_ok": d2.startswith(UTF8_NUL),
        "meta1": [f"0x{m1[0]:08X}", m1[1], m1[2]],
        "meta1_ok": m1 == EXPECTED_META1,
        "meta2": [f"0x{m2[0]:08X}", m2[1], m2[2]],
        "meta2_ok": m2 == EXPECTED_META2,
    }


def _find_all(data: bytes, pat: bytes):
    out = []
    pos = 0
    while True:
        p = data.find(pat, pos)
        if p < 0:
            break
        out.append(p)
        pos = p + 1
    return out


def focused_scan(b, pid, base):
    """
    Scan only the 0x08E00000..0x08FFFFFF dynamic area.  Stage39G already
    proved that real UTF-16 Korean exists there, so a full 32 MiB scan only
    delays menu progression.
    """
    h = b.open_process(pid)
    try:
        data = b.guest_read(
            h, base, FOCUS_START, FOCUS_SIZE
        )
    finally:
        b.kernel32.CloseHandle(h)

    result = {}
    for name, pat in MENU_PATTERNS.items():
        result[name] = [
            f"0x{FOCUS_START + p:08X}"
            for p in _find_all(data, pat)
        ]

    # Directly sample the two aligned Stage39G matches as additional evidence.
    samples = {}
    h = b.open_process(pid)
    try:
        for addr in STAGE39G_UTF16_MATCHES[:2]:
            try:
                raw = b.guest_read(h, base, addr, 24)
                samples[f"0x{addr:08X}"] = raw.hex()
            except Exception as e:
                samples[f"0x{addr:08X}"] = f"ERROR: {e}"
    finally:
        b.kernel32.CloseHandle(h)

    result["stage39g_match_samples"] = samples
    result["korean_found"] = bool(result["korean_story"])

    sibling_count = 0
    for name in (
        "OPTIONS", "Options",
        "EXTRAS", "Extras",
        "PROFILE", "Profile",
        "CONTINUE", "Continue",
    ):
        sibling_count += len(result[name])

    result["menu_sibling_match_count"] = sibling_count
    return result


def capture(local_mod, b, hwnd, label):
    fn = find_callable(
        [b, getattr(local_mod, "s39", None), local_mod],
        "capture",
    )
    helper = BASE_TOOLS / "capture_ppsspp.ps1"
    path = OUT / f"stage39h_{label}.png"

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


def log_has_menu_open():
    if not PPSSPP_LOG.exists():
        return False
    try:
        text = PPSSPP_LOG.read_text(
            encoding="utf-8",
            errors="replace",
        )
    except Exception:
        return False
    return MENU_OPEN_LOG_MARKER in text


def wait_for_menu_resource(ws, timeout=90.0):
    """
    Skip startup/legal/movie screens with Start, but STOP permanently the
    moment PPSSPP actually opens MENUINT0.RAW.

    This is a concrete state transition, unlike the old fixed Story-slot test.
    """
    end = time.time() + timeout
    last_press = 0.0
    presses = 0

    while time.time() < end:
        if log_has_menu_open():
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

        time.sleep(0.12)

    return {
        "opened": False,
        "start_presses": presses,
    }


def runtime_test(local_mod, b):
    if not TEST_ISO.exists():
        raise RuntimeError(
            f"Missing Stage39F ISO: {TEST_ISO}"
        )

    exe = b.find_ppsspp_exe()

    cfg = OUT / "stage39h_append.ini"
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
        previous = b.close_existing_ppsspp(timeout=3.0)
    except Exception:
        previous = None

    requested_port = b.choose_free_port()

    cmd = [
        str(exe),
        "-d",
        f"--log={PPSSPP_LOG}",
        "--windowed",
        f"--appendconfig={cfg}",
        f"--debugger={requested_port}",
        str(TEST_ISO),
    ]

    log("[Stage39H] Launching PPSSPP normal JIT")
    proc = subprocess.Popen(cmd)
    cleanup = b.register_ppsspp_auto_close(proc)

    result = {
        "pid": proc.pid,
        "normal_jit": True,
        "runtime_patch": False,
        "previous_ppsspp_cleanup": previous,
    }

    try:
        hwnd = b.find_ppsspp_hwnd(30)
        if not hwnd:
            raise RuntimeError("PPSSPP window did not appear")

        end = time.time() + 30
        pid = base = None
        while time.time() < end:
            try:
                pid, base = b.get_pid_base(hwnd)
                if pid and base:
                    break
            except Exception:
                pass
            time.sleep(0.2)
        if not pid or not base:
            raise RuntimeError("PPSSPP process memory base unavailable")

        actual_port = b.wait_for_actual_debugger_port(
            PPSSPP_LOG, 30
        )
        ws, host = b.connect_debugger(actual_port)

        try:
            result["debugger_host"] = host
            result["debugger_port"] = actual_port

            # Wait for corrected Stage39F source structures.
            source = None
            for _ in range(160):
                try:
                    s = verify_sources(ws)
                    if (
                        s["display1_ok"]
                        and s["display2_ok"]
                        and s["menustory_key_ok"]
                        and s["meta1_ok"]
                        and s["meta2_ok"]
                    ):
                        source = s
                        break
                except Exception:
                    pass
                time.sleep(0.25)

            if source is None:
                raise RuntimeError(
                    "Corrected Stage39F sources did not become resident"
                )

            result["runtime_sources"] = source

            # Stage39G proved real UTF-16 Korean already exists before input.
            # Record the quick focused scan, but DO NOT stop boot progression.
            result["pre_menu_scan"] = focused_scan(
                b, pid, base
            )

            # Skip startup content only until the game REALLY opens MENUINT0.
            menu_open = wait_for_menu_resource(
                ws, timeout=90.0
            )
            result["menu_resource_open"] = menu_open

            if not menu_open["opened"]:
                raise RuntimeError(
                    "MENUINT0.RAW was not opened within timeout"
                )

            # Absolutely no more automatic Start presses during this wait.
            time.sleep(2.0)

            result["title_or_menu_capture"] = capture(
                local_mod, b, hwnd, "menu_resource_open"
            )
            result["scan_after_menu_resource"] = focused_scan(
                b, pid, base
            )

            # MENUINT0 normally opens as the title/menu environment loads.
            # One deliberate Start advances the title screen to the actual
            # selectable main menu.  We then STOP input unconditionally.
            try:
                ws.request(
                    "input.buttons.press",
                    timeout=5,
                    button="start",
                    duration=2,
                )
                result["main_menu_start_press_sent"] = True
            except Exception as e:
                result["main_menu_start_press_error"] = str(e)

            # Capture several moments because menu animation/profile loading
            # can delay the labels by a few seconds.
            checkpoints = []
            last_wait = 0.0
            for wait_s in (1.0, 2.5, 5.0, 8.0):
                delta = wait_s - last_wait
                if delta > 0:
                    time.sleep(delta)
                last_wait = wait_s

                scan = focused_scan(b, pid, base)
                cap = capture(
                    local_mod, b, hwnd,
                    f"main_menu_{str(wait_s).replace('.', 'p')}s"
                )

                checkpoints.append({
                    "elapsed_after_start": wait_s,
                    "scan": scan,
                    "capture": cap,
                })

            result["main_menu_checkpoints"] = checkpoints

            final_scan = checkpoints[-1]["scan"]
            result["final_scan"] = final_scan

            # At a real main menu state we expect Korean plus at least one
            # sibling menu string in the dynamic area.  The screenshot is still
            # the authority for normal glyph appearance and is intentionally
            # included for ChatGPT/user visual verification.
            result["main_menu_candidate"] = (
                final_scan["korean_found"]
                and final_scan["menu_sibling_match_count"] > 0
            )

            # Font metadata / atlas verification.  Descriptor is recorded, but
            # Stage39G showed that checking it at an unrelated splash frame can
            # give a dynamic texture state.  Do not make descriptor equality the
            # only reason this visual-proof stage fails.
            inspect = find_callable(
                [local_mod, getattr(local_mod, "s39", None), b],
                "inspect_production_runtime",
            )
            plan_path = BASE_TOOLS / "stage39a_font_plan.json"

            if inspect and plan_path.exists():
                try:
                    plan = json.loads(
                        plan_path.read_text(encoding="utf-8")
                    )
                    fr = inspect(
                        pid, base, plan, plan["atlas_sha1"]
                    )
                    result["production_font_runtime"] = fr
                    result["font_core_ok"] = (
                        fr.get("glyph_count")
                            == fr.get("expected_glyph_count")
                        and fr.get("glyph_ptr")
                            == fr.get("expected_glyph_ptr")
                        and fr.get("atlas_sha1")
                            == fr.get("expected_atlas_sha1")
                        and fr.get("all_production_mappings_ok", False)
                    )
                except Exception as e:
                    result["production_font_runtime_error"] = str(e)
                    result["font_core_ok"] = False
            else:
                result["font_core_ok"] = False

            record_fn = find_callable(
                [b, getattr(local_mod, "s39", None), local_mod],
                "record_gpu_frame",
            )
            if record_fn:
                try:
                    gpu = OUT / "stage39h_main_menu.ppdmp"
                    result["gpu_frame"] = record_fn(ws, gpu)
                except Exception as e:
                    result["gpu_frame_error"] = str(e)

            result["completed"] = (
                result["main_menu_candidate"]
                and result["font_core_ok"]
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


def make_zip(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
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

    local_mod, b = load_helpers()

    report = {
        "stage": "39H",
        "purpose":
            "Reach the real selectable main menu, preserve the corrected "
            "Stage39F Unicode path, and capture the menu for visual Korean "
            "glyph verification.",
        "stage39g_reclassification": {
            "unicode_conversion": "PASS",
            "evidence": [
                "UTF-16LE Korean found at 0x08E416C0",
                "UTF-16LE Korean found at 0x08E431A0",
                "no byte-wise-widened UTF-8 pattern found",
            ],
            "why_stage39g_zip_was_named_fail":
                "The old production-font helper required a transient GE "
                "descriptor value while the screen was still in startup/title "
                "state. Core font/glyph/atlas checks themselves passed.",
            "stage39g_actual_font_core": {
                "glyph_count": 847,
                "glyph_ptr": "0x098F5020",
                "atlas_sha1":
                    "b58e6ef06af9555a23d8be1f70a0e8d65b2ce4c6",
                "all_696_mappings": "PASS",
            },
        },
        "iso_changed_in_this_stage": False,
        "runtime_patch": False,
        "automatic_success_is_not_final_visual_claim":
            "Final screenshot must still be inspected for normal Korean glyph appearance.",
        "test_iso": str(TEST_ISO),
    }

    try:
        rt = runtime_test(local_mod, b)
        report["runtime"] = rt
        report["completed"] = bool(rt.get("completed", False))
    except Exception as e:
        report["runtime_exception"] = str(e)
        report["runtime_traceback"] = traceback.format_exc()
        report["completed"] = False

    REPORT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    if report["completed"]:
        make_zip(SUCCESS_ZIP)
        log("[Stage39H] COMPLETE - upload ZIP for visual verification")
        log(f"[Stage39H] Upload ZIP: {SUCCESS_ZIP}")
        return

    make_zip(FAIL_ZIP)
    raise RuntimeError(
        f"Stage39H did not reach a verifiable main-menu candidate. "
        f"See {FAIL_ZIP}"
    )


if __name__ == "__main__":
    try:
        main()
    except Exception:
        OUT.mkdir(parents=True, exist_ok=True)
        LOG_DIR.mkdir(parents=True, exist_ok=True)

        failure = OUT / "FAILURE.txt"
        failure.write_text(
            traceback.format_exc(),
            encoding="utf-8",
        )

        try:
            make_zip(FAIL_ZIP)
        except Exception:
            pass

        print(traceback.format_exc(), flush=True)
        print(f"STAGE 39H FAILED: {FAIL_ZIP}", flush=True)
        raise SystemExit(1)
