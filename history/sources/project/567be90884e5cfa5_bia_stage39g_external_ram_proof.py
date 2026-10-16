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

OUT = ROOT / "analysis" / "stage39g_external_ram_proof"
LOG_DIR = ROOT / "log"

SUCCESS_ZIP = LOG_DIR / "bia_stage39g_upload.zip"
FAIL_ZIP = LOG_DIR / "fail_bia_stage39g_upload.zip"

REPORT_PATH = OUT / "stage39g_report.json"
PPSSPP_LOG = OUT / "stage39g_ppsspp.log"

# Correct Stage39F source/metadata addresses.
DISPLAY1_ADDR = 0x093B1B40
MENUSTORY_KEY_ADDR = 0x093B1BB0
DISPLAY2_ADDR = 0x093B1BF0

META1_ADDR = 0x095EC774
META2_ADDR = 0x095F1758

TEST_TEXT = "\uc2a4\ud1a0\ub9ac"
UTF8 = TEST_TEXT.encode("utf-8")
UTF8_NUL = UTF8 + b"\x00"
UTF16 = TEST_TEXT.encode("utf-16le")

BYTEWISE_WIDENED = b"".join(
    bytes((x, 0)) for x in UTF8
)

EXPECTED_META1 = (DISPLAY1_ADDR, 10, 10)
EXPECTED_META2 = (DISPLAY2_ADDR, 10, 10)

# PSP game RAM range used by all previous stages.
RAM_START = 0x08800000
RAM_SIZE = 0x02000000
RAM_END = RAM_START + RAM_SIZE
SCAN_CHUNK = 0x00040000  # 256 KiB

# English wide strings used only as optional "menu-like state" diagnostics.
# Baseline matches are recorded before any input; only NEW addresses are
# considered interesting later.
MENU_DIAGNOSTIC_PATTERNS = {
    "Story": "Story".encode("utf-16le"),
    "STORY": "STORY".encode("utf-16le"),
    "Options": "Options".encode("utf-16le"),
    "OPTIONS": "OPTIONS".encode("utf-16le"),
    "Profile": "Profile".encode("utf-16le"),
    "PROFILE": "PROFILE".encode("utf-16le"),
}

MAX_START_PRESSES = 4
PHASE_WAIT_SECONDS = [0.8, 2.5, 6.0, 12.0]

SCRIPT_DIR = Path(__file__).resolve().parent


def log(msg: str):
    # Keep console output ASCII-only due the Stage39C CP949 console failure.
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
        raise RuntimeError("Could not resolve Stage39B base helper module")

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


def verify_correct_sources(ws):
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


def scan_guest_ram(b, pid, base, patterns):
    """
    Search guest RAM through PPSSPP's host process using the already-proven
    ReadProcessMemory helper.  This replaces Stage39F's unsupported
    debugger event "memory.search".

    `patterns` is dict[name -> bytes].
    """
    longest = max(len(x) for x in patterns.values())
    overlap = max(0, longest - 1)

    matches = {name: [] for name in patterns}

    h = b.open_process(pid)
    try:
        addr = RAM_START
        tail = b""
        tail_addr = RAM_START

        while addr < RAM_END:
            size = min(SCAN_CHUNK, RAM_END - addr)

            try:
                chunk = b.guest_read(h, base, addr, size)
            except Exception:
                # Retry smaller pages so one sparse/unreadable region does not
                # invalidate the whole scan.
                chunk_parts = []
                sub = addr
                end = addr + size
                while sub < end:
                    sub_size = min(0x4000, end - sub)
                    try:
                        part = b.guest_read(
                            h, base, sub, sub_size
                        )
                    except Exception:
                        part = b"\x00" * sub_size
                    chunk_parts.append(part)
                    sub += sub_size
                chunk = b"".join(chunk_parts)

            if tail:
                combined = tail + chunk
                combined_base = tail_addr
            else:
                combined = chunk
                combined_base = addr

            for name, pat in patterns.items():
                for p in _find_all(combined, pat):
                    guest = combined_base + p
                    if RAM_START <= guest < RAM_END:
                        matches[name].append(guest)

            if overlap:
                tail = combined[-overlap:]
                tail_addr = addr + size - len(tail)
            else:
                tail = b""
                tail_addr = addr + size

            addr += size

    finally:
        b.kernel32.CloseHandle(h)

    # Stable unique addresses.
    for name in matches:
        matches[name] = sorted(set(matches[name]))

    return matches


def capture_phase(local_mod, b, hwnd, label):
    capture_fn = find_callable(
        [
            b,
            getattr(local_mod, "s39", None),
            local_mod,
        ],
        "capture",
    )

    helper = BASE_TOOLS / "capture_ppsspp.ps1"
    path = OUT / f"stage39g_{label}.png"

    if not capture_fn or not helper.exists():
        return {
            "path": str(path),
            "captured": False,
            "error": "capture helper unavailable",
        }

    try:
        capture_fn(hwnd, path, helper)
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


def scan_snapshot(b, pid, base, baseline_menu=None):
    patterns = {
        "utf16_korean": UTF16,
        "bytewise_widened_utf8": BYTEWISE_WIDENED,
        "utf8_source": UTF8,
    }
    patterns.update({
        f"menu_{name}": pat
        for name, pat in MENU_DIAGNOSTIC_PATTERNS.items()
    })

    found = scan_guest_ram(
        b, pid, base, patterns
    )

    result = {
        name: [f"0x{x:08X}" for x in addrs]
        for name, addrs in found.items()
    }

    result["utf16_korean_found"] = bool(
        found["utf16_korean"]
    )

    if baseline_menu is not None:
        new_menu = {}
        for name in MENU_DIAGNOSTIC_PATTERNS:
            key = f"menu_{name}"
            before = set(baseline_menu.get(key, []))
            after = set(found.get(key, []))
            diff = sorted(after - before)
            new_menu[name] = [
                f"0x{x:08X}" for x in diff
            ]
        result["new_menu_like_matches"] = new_menu
        result["new_menu_like_match_count"] = sum(
            len(v) for v in new_menu.values()
        )

    # Keep raw address sets internally for baseline comparisons.
    result["_raw"] = found
    return result


def strip_raw(snapshot):
    out = dict(snapshot)
    out.pop("_raw", None)
    return out


def runtime_test(local_mod, b):
    if not TEST_ISO.exists():
        raise RuntimeError(
            f"Missing Stage39F ISO: {TEST_ISO}"
        )

    exe = b.find_ppsspp_exe()

    cfg = OUT / "stage39g_append.ini"
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

    log("[Stage39G] Launching PPSSPP normal JIT")
    proc = subprocess.Popen(cmd)
    cleanup = b.register_ppsspp_auto_close(proc)

    result = {
        "pid": proc.pid,
        "ppsspp_exe": str(exe),
        "normal_jit": True,
        "runtime_patch": False,
        "previous_ppsspp_cleanup": previous,
        "search_method":
            "host ReadProcessMemory via proven guest_read helper",
    }

    try:
        hwnd = b.find_ppsspp_hwnd(30)
        if not hwnd:
            raise RuntimeError("PPSSPP window did not appear")

        # Resolve pid/base for direct process-memory scans.
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
            raise RuntimeError(
                "PPSSPP process memory base unavailable"
            )

        result["guest_process"] = {
            "pid": pid,
            "base": f"0x{int(base):X}",
        }

        actual_port = b.wait_for_actual_debugger_port(
            PPSSPP_LOG, 30
        )
        ws, host = b.connect_debugger(actual_port)

        try:
            result["debugger_host"] = host
            result["debugger_port"] = actual_port

            try:
                result["version"] = ws.request(
                    "version",
                    timeout=5,
                    name="bia-stage39g",
                    version="1",
                )
            except Exception as e:
                result["version_error"] = str(e)

            # First wait until Stage39F's corrected MDI data is resident.
            resident = None
            for _ in range(160):
                try:
                    x = verify_correct_sources(ws)
                    if (
                        x["display1_ok"]
                        and x["display2_ok"]
                        and x["menustory_key_ok"]
                        and x["meta1_ok"]
                        and x["meta2_ok"]
                    ):
                        resident = x
                        break
                except Exception:
                    pass
                time.sleep(0.25)

            if resident is None:
                raise RuntimeError(
                    "Stage39F corrected source/metadata "
                    "did not become resident"
                )

            result["runtime_sources"] = resident

            # Baseline before any input.
            baseline = scan_snapshot(
                b, pid, base, baseline_menu=None
            )
            baseline_menu = baseline["_raw"]

            phases = [{
                "phase": "baseline_no_input",
                "elapsed_after_press": 0,
                "scan": strip_raw(baseline),
                "capture": capture_phase(
                    local_mod, b, hwnd, "baseline"
                ),
            }]

            if baseline["utf16_korean_found"]:
                result["phases"] = phases
                result["utf16_proof"] = True
            else:
                result["utf16_proof"] = False

            # Progress carefully.  One Start at a time, with long waits.
            # Search/capture multiple times before deciding another press is
            # needed.  If true UTF-16 appears, stop input immediately.
            stop_for_menu_state = False

            for press_no in range(1, MAX_START_PRESSES + 1):
                if result["utf16_proof"] or stop_for_menu_state:
                    break

                try:
                    ws.request(
                        "input.buttons.press",
                        timeout=5,
                        button="start",
                        duration=2,
                    )
                except Exception:
                    pass

                phase_start = time.time()
                previous_wait = 0.0

                for wait_s in PHASE_WAIT_SECONDS:
                    delta = wait_s - previous_wait
                    if delta > 0:
                        time.sleep(delta)
                    previous_wait = wait_s

                    snap = scan_snapshot(
                        b, pid, base,
                        baseline_menu=baseline_menu
                    )

                    label = (
                        f"press{press_no}_"
                        f"{str(wait_s).replace('.', 'p')}s"
                    )

                    cap = None
                    # Capture useful checkpoints, but not every scan.
                    if wait_s in (2.5, 12.0):
                        cap = capture_phase(
                            local_mod, b, hwnd, label
                        )

                    phases.append({
                        "phase": label,
                        "start_press_number": press_no,
                        "elapsed_after_press": wait_s,
                        "scan": strip_raw(snap),
                        "capture": cap,
                    })

                    if snap["utf16_korean_found"]:
                        result["utf16_proof"] = True
                        result["proof_phase"] = label
                        break

                    # If multiple new English wide menu strings have appeared,
                    # we are likely at a menu-like UI state.  Stop sending more
                    # Start presses and preserve this state for diagnosis.
                    if (
                        snap.get(
                            "new_menu_like_match_count", 0
                        ) >= 2
                        and wait_s >= 2.5
                    ):
                        stop_for_menu_state = True
                        result[
                            "stopped_for_new_menu_like_state"
                        ] = {
                            "phase": label,
                            "new_matches":
                                snap["new_menu_like_matches"],
                        }
                        break

                if result["utf16_proof"] or stop_for_menu_state:
                    break

            result["phases"] = phases

            # Re-scan once more at the preserved final state.
            final_scan = scan_snapshot(
                b, pid, base,
                baseline_menu=baseline_menu
            )
            result["final_scan"] = strip_raw(final_scan)

            if final_scan["utf16_korean_found"]:
                result["utf16_proof"] = True

            result["final_capture"] = capture_phase(
                local_mod, b, hwnd, "final"
            )

            # Production font verification.
            inspect = find_callable(
                [
                    local_mod,
                    getattr(local_mod, "s39", None),
                    b,
                ],
                "inspect_production_runtime",
            )
            plan_path = BASE_TOOLS / "stage39a_font_plan.json"

            if inspect and plan_path.exists():
                try:
                    plan = json.loads(
                        plan_path.read_text(
                            encoding="utf-8"
                        )
                    )
                    result["production_font_runtime"] = inspect(
                        pid,
                        base,
                        plan,
                        plan["atlas_sha1"],
                    )
                except Exception as e:
                    result[
                        "production_font_runtime_error"
                    ] = str(e)

            # Final GPU dump for visual diagnosis if available.
            record_fn = find_callable(
                [
                    b,
                    getattr(local_mod, "s39", None),
                    local_mod,
                ],
                "record_gpu_frame",
            )
            if record_fn:
                try:
                    gpu_path = OUT / "stage39g_final.ppdmp"
                    result["gpu_frame"] = record_fn(
                        ws, gpu_path
                    )
                except Exception as e:
                    result["gpu_frame_error"] = str(e)

            font = result.get(
                "production_font_runtime", {}
            )
            font_ok = (
                font.get("ok", True)
                if isinstance(font, dict)
                else True
            )

            result["completed"] = (
                bool(result["utf16_proof"])
                and font_ok
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

    with zipfile.ZipFile(
        path, "w", zipfile.ZIP_DEFLATED
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
        "stage": "39G",
        "purpose":
            "Re-run the already-correct Stage39F ISO and prove Unicode "
            "conversion using direct process-memory scanning instead of "
            "PPSSPP's unsupported memory.search debugger event.",
        "stage39f_conclusion": {
            "disc_patch": "verified",
            "runtime_utf8_sources": "verified",
            "runtime_pointer_num_max_metadata": "verified",
            "production_font": "verified",
            "reason_stage39f_reported_failure":
                "PPSSPP v1.20.4 returned 'Bad message: unknown event' "
                "for memory.search, so no actual RAM pattern search occurred.",
            "stage39f_screenshot_state":
                "Loading your latest saved profile; not yet the main menu.",
        },
        "iso_changed_in_this_stage": False,
        "runtime_patch": False,
        "uses_old_fixed_story_slot": False,
        "uses_debugger_memory_search": False,
        "test_iso": str(TEST_ISO),
    }

    try:
        rt = runtime_test(local_mod, b)
        report["runtime"] = rt
        report["completed"] = bool(
            rt.get("completed", False)
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

    if report["completed"]:
        make_zip(SUCCESS_ZIP)
        log("[Stage39G] COMPLETE")
        log(f"[Stage39G] Upload ZIP: {SUCCESS_ZIP}")
        return

    make_zip(FAIL_ZIP)
    raise RuntimeError(
        "Stage39G did not find real UTF-16 Korean in guest RAM. "
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
        print(
            f"STAGE 39G FAILED: {FAIL_ZIP}",
            flush=True,
        )
        raise SystemExit(1)
