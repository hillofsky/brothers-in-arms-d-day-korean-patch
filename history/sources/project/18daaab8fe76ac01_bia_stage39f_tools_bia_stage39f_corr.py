#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import base64
import importlib.util
import json
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

STAGE39B_ISO = ROOT / "BIA_STAGE39B_COMPILED_MDI_TEXT_TEST.iso"
STAGE39C_ISO = ROOT / "BIA_STAGE39C_COMPILED_LOCALIZATION_TEST.iso"
TEST_ISO = ROOT / "BIA_STAGE39F_CORRECT_NARROW_METADATA_TEST.iso"

OUT = ROOT / "analysis" / "stage39f_correct_narrow_metadata"
LOG_DIR = ROOT / "log"

SUCCESS_ZIP = LOG_DIR / "bia_stage39f_upload.zip"
FAIL_ZIP = LOG_DIR / "fail_bia_stage39f_upload.zip"

REPORT_PATH = OUT / "stage39f_report.json"
PPSSPP_LOG = OUT / "stage39f_ppsspp.log"
SCREENSHOT = OUT / "stage39f_menu.png"
GPU_DUMP = OUT / "stage39f_menu.ppdmp"

# MDI layout proven in the project.
MDI_SEQ_BASE = 0x08E2D020
MDI_STREAM_SIZE = 0x78000

S11 = 11
S16 = 16
S11_BASE = MDI_SEQ_BASE + S11 * MDI_STREAM_SIZE
S16_BASE = MDI_SEQ_BASE + S16 * MDI_STREAM_SIZE

# IMPORTANT Stage39F correction:
#
# stream11 + 0x5CB20 = display value "Story" after SINGLEPLAYER.
# stream11 + 0x5CB90 = INTERNAL KEY "MenuStory".
# stream11 + 0x5CB94 = "Story" SUBSTRING INSIDE "MenuStory".
#                        It is NOT a separate display value.
# stream11 + 0x5CBD0 = the second real display value "Story",
#                        after key "TITLE".
DISPLAY1_OFF = 0x5CB20
MENUSTORY_KEY_OFF = 0x5CB90
DISPLAY2_OFF = 0x5CBD0

FIELD_BYTES = 16

# FString-like pointer/num/max records in stream16.
#
# First display:
#   +0x3F754 ptr -> stream11+0x5CB20
#   +0x3F758 num = 6  ("Story" + NUL)
#   +0x3F75C max = 6
#
# Second display:
#   +0x44738 ptr -> stream11+0x5CBD0
#   +0x4473C num = 6
#   +0x44740 max = 6
DISPLAY1_META_PTR_OFF = 0x3F754
DISPLAY1_META_NUM_OFF = 0x3F758
DISPLAY1_META_MAX_OFF = 0x3F75C

DISPLAY2_META_PTR_OFF = 0x44738
DISPLAY2_META_NUM_OFF = 0x4473C
DISPLAY2_META_MAX_OFF = 0x44740

TEST_TEXT = "\uc2a4\ud1a0\ub9ac"
UTF8 = TEST_TEXT.encode("utf-8")
UTF8_NUL = UTF8 + b"\x00"
UTF16 = TEST_TEXT.encode("utf-16le")
BYTEWISE_WIDENED = b"".join(bytes((x, 0)) for x in UTF8)

DISPLAY1_ADDR = S11_BASE + DISPLAY1_OFF
MENUSTORY_KEY_ADDR = S11_BASE + MENUSTORY_KEY_OFF
DISPLAY2_ADDR = S11_BASE + DISPLAY2_OFF

META1_ADDR = S16_BASE + DISPLAY1_META_PTR_OFF
META2_ADDR = S16_BASE + DISPLAY2_META_PTR_OFF

EXPECTED_DISPLAY1_PTR = DISPLAY1_ADDR
EXPECTED_DISPLAY2_PTR = DISPLAY2_ADDR
EXPECTED_NUM = len(UTF8_NUL)  # 10 bytes/elements.

RAM_SEARCH_START = 0x08800000
RAM_SEARCH_SIZE = 0x02000000

SCRIPT_DIR = Path(__file__).resolve().parent


def log(msg: str):
    # ASCII-only console messages avoid the Stage39C CP949 exception.
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
        raise RuntimeError("Could not resolve Stage39B base helpers")
    return mod, b


def find_callable(objects, name):
    for obj in objects:
        if obj is not None and hasattr(obj, name):
            fn = getattr(obj, name)
            if callable(fn):
                return fn
    return None


def read_bytes_ws(ws, address, size):
    r = ws.request(
        "memory.read",
        timeout=10,
        address=address,
        size=size,
    )
    return base64.b64decode(r["base64"])


def search_bytes(ws, pattern: bytes, align=1, max_results=128):
    try:
        r = ws.request(
            "memory.search",
            timeout=30,
            address=RAM_SEARCH_START,
            size=RAM_SEARCH_SIZE,
            type="bytes",
            base64=base64.b64encode(pattern).decode("ascii"),
            align=align,
            maxResults=max_results,
        )
        return [int(x) for x in r.get("matches", [])]
    except Exception as e:
        return {"error": str(e), "matches": []}


def parse_mdi_with_base(b, data):
    return b.parse_mdi(data)


def rebuild_mdi_with_base(b, original, replacements):
    return b.rebuild_mdi(original, replacements)


def choose_source_iso():
    if STAGE39B_ISO.exists():
        return STAGE39B_ISO, "Stage39B production-font ISO"
    if STAGE39C_ISO.exists():
        return STAGE39C_ISO, "Stage39C fallback ISO (MenuStory key will be repaired)"
    raise RuntimeError(
        "Neither Stage39B nor Stage39C ISO was found."
    )


def patch_correct_sources(b, source_iso: Path):
    _, mdi = b.iso_read_file(source_iso, b.TARGET_MDI)
    streams = parse_mdi_with_base(b, mdi)

    if len(streams) <= S16:
        raise RuntimeError("MDI does not contain stream16")

    d11 = bytearray(streams[S11]["decoded"])
    d16 = bytearray(streams[S16]["decoded"])

    # Capture old bytes/metadata for the report.
    before = {
        "display1": bytes(
            d11[DISPLAY1_OFF:DISPLAY1_OFF+FIELD_BYTES]
        ).hex(),
        "menustory_key": bytes(
            d11[MENUSTORY_KEY_OFF:MENUSTORY_KEY_OFF+FIELD_BYTES]
        ).hex(),
        "display2": bytes(
            d11[DISPLAY2_OFF:DISPLAY2_OFF+FIELD_BYTES]
        ).hex(),
        "meta1": [
            struct.unpack_from("<I", d16, DISPLAY1_META_PTR_OFF)[0],
            struct.unpack_from("<I", d16, DISPLAY1_META_NUM_OFF)[0],
            struct.unpack_from("<I", d16, DISPLAY1_META_MAX_OFF)[0],
        ],
        "meta2": [
            struct.unpack_from("<I", d16, DISPLAY2_META_PTR_OFF)[0],
            struct.unpack_from("<I", d16, DISPLAY2_META_NUM_OFF)[0],
            struct.unpack_from("<I", d16, DISPLAY2_META_MAX_OFF)[0],
        ],
    }

    # Restore the internal key exactly.  This repairs the Stage39C fallback
    # source if it had "Story" inside MenuStory overwritten.
    key_field = b"MenuStory\x00"
    key_field += b"\x00" * (FIELD_BYTES - len(key_field))
    d11[
        MENUSTORY_KEY_OFF:MENUSTORY_KEY_OFF+FIELD_BYTES
    ] = key_field

    # Patch the TWO REAL display values.
    value_field = UTF8_NUL + b"\x00" * (FIELD_BYTES - len(UTF8_NUL))
    d11[
        DISPLAY1_OFF:DISPLAY1_OFF+FIELD_BYTES
    ] = value_field
    d11[
        DISPLAY2_OFF:DISPLAY2_OFF+FIELD_BYTES
    ] = value_field

    # Update FString-like ArrayNum/ArrayMax metadata.  Original English Story:
    # 5 bytes + NUL => 6.  UTF-8 Korean: 9 bytes + NUL => 10.
    ptr1 = struct.unpack_from("<I", d16, DISPLAY1_META_PTR_OFF)[0]
    ptr2 = struct.unpack_from("<I", d16, DISPLAY2_META_PTR_OFF)[0]

    if ptr1 != EXPECTED_DISPLAY1_PTR:
        raise RuntimeError(
            f"Display1 pointer mismatch: 0x{ptr1:08X} "
            f"!= 0x{EXPECTED_DISPLAY1_PTR:08X}"
        )
    if ptr2 != EXPECTED_DISPLAY2_PTR:
        raise RuntimeError(
            f"Display2 pointer mismatch: 0x{ptr2:08X} "
            f"!= 0x{EXPECTED_DISPLAY2_PTR:08X}"
        )

    struct.pack_into("<I", d16, DISPLAY1_META_NUM_OFF, EXPECTED_NUM)
    struct.pack_into("<I", d16, DISPLAY1_META_MAX_OFF, EXPECTED_NUM)
    struct.pack_into("<I", d16, DISPLAY2_META_NUM_OFF, EXPECTED_NUM)
    struct.pack_into("<I", d16, DISPLAY2_META_MAX_OFF, EXPECTED_NUM)

    patched = rebuild_mdi_with_base(
        b,
        mdi,
        {
            S11: bytes(d11),
            S16: bytes(d16),
        },
    )

    # Parse rebuilt MDI and verify every critical field.
    vs = parse_mdi_with_base(b, patched)
    v11 = vs[S11]["decoded"]
    v16 = vs[S16]["decoded"]

    expected_value_field = value_field

    if v11[
        DISPLAY1_OFF:DISPLAY1_OFF+FIELD_BYTES
    ] != expected_value_field:
        raise RuntimeError("Display1 rebuilt MDI mismatch")
    if v11[
        DISPLAY2_OFF:DISPLAY2_OFF+FIELD_BYTES
    ] != expected_value_field:
        raise RuntimeError("Display2 rebuilt MDI mismatch")
    if v11[
        MENUSTORY_KEY_OFF:MENUSTORY_KEY_OFF+FIELD_BYTES
    ] != key_field:
        raise RuntimeError("MenuStory key rebuild mismatch")

    meta1 = [
        struct.unpack_from("<I", v16, DISPLAY1_META_PTR_OFF)[0],
        struct.unpack_from("<I", v16, DISPLAY1_META_NUM_OFF)[0],
        struct.unpack_from("<I", v16, DISPLAY1_META_MAX_OFF)[0],
    ]
    meta2 = [
        struct.unpack_from("<I", v16, DISPLAY2_META_PTR_OFF)[0],
        struct.unpack_from("<I", v16, DISPLAY2_META_NUM_OFF)[0],
        struct.unpack_from("<I", v16, DISPLAY2_META_MAX_OFF)[0],
    ]

    if meta1 != [EXPECTED_DISPLAY1_PTR, EXPECTED_NUM, EXPECTED_NUM]:
        raise RuntimeError(f"Display1 metadata mismatch: {meta1}")
    if meta2 != [EXPECTED_DISPLAY2_PTR, EXPECTED_NUM, EXPECTED_NUM]:
        raise RuntimeError(f"Display2 metadata mismatch: {meta2}")

    return patched, {
        "before": before,
        "after": {
            "display1_runtime": f"0x{DISPLAY1_ADDR:08X}",
            "display1_utf8_hex": UTF8_NUL.hex(),
            "display2_runtime": f"0x{DISPLAY2_ADDR:08X}",
            "display2_utf8_hex": UTF8_NUL.hex(),
            "menustory_key_runtime": f"0x{MENUSTORY_KEY_ADDR:08X}",
            "menustory_key": "MenuStory",
            "meta1_runtime": f"0x{META1_ADDR:08X}",
            "meta1": [
                f"0x{EXPECTED_DISPLAY1_PTR:08X}",
                EXPECTED_NUM,
                EXPECTED_NUM,
            ],
            "meta2_runtime": f"0x{META2_ADDR:08X}",
            "meta2": [
                f"0x{EXPECTED_DISPLAY2_PTR:08X}",
                EXPECTED_NUM,
                EXPECTED_NUM,
            ],
        },
        "critical_correction":
            "0x093B1BB4 is inside internal key MenuStory; "
            "the second real Story display is 0x093B1BF0.",
    }


def build_iso(b):
    source_iso, source_desc = choose_source_iso()

    if TEST_ISO.exists():
        TEST_ISO.unlink()
    shutil.copy2(source_iso, TEST_ISO)

    patched_mdi, info = patch_correct_sources(b, source_iso)

    b.append_iso_file_and_repoint(
        TEST_ISO,
        b.TARGET_MDI,
        patched_mdi,
    )

    _, rb = b.iso_read_file(TEST_ISO, b.TARGET_MDI)
    if rb != patched_mdi:
        raise RuntimeError("Stage39F MDI ISO read-back mismatch")

    return source_iso, source_desc, info


def verify_runtime_sources(ws):
    d1 = read_bytes_ws(ws, DISPLAY1_ADDR, FIELD_BYTES)
    key = read_bytes_ws(ws, MENUSTORY_KEY_ADDR, FIELD_BYTES)
    d2 = read_bytes_ws(ws, DISPLAY2_ADDR, FIELD_BYTES)

    m1 = read_bytes_ws(ws, META1_ADDR, 12)
    m2 = read_bytes_ws(ws, META2_ADDR, 12)

    meta1 = list(struct.unpack("<III", m1))
    meta2 = list(struct.unpack("<III", m2))

    return {
        "display1_hex": d1.hex(),
        "display1_ok": d1.startswith(UTF8_NUL),
        "menustory_key_hex": key.hex(),
        "menustory_key_ok": key.startswith(b"MenuStory\x00"),
        "display2_hex": d2.hex(),
        "display2_ok": d2.startswith(UTF8_NUL),
        "meta1": [
            f"0x{meta1[0]:08X}", meta1[1], meta1[2]
        ],
        "meta1_ok": (
            meta1[0] == EXPECTED_DISPLAY1_PTR
            and meta1[1] == EXPECTED_NUM
            and meta1[2] == EXPECTED_NUM
        ),
        "meta2": [
            f"0x{meta2[0]:08X}", meta2[1], meta2[2]
        ],
        "meta2_ok": (
            meta2[0] == EXPECTED_DISPLAY2_PTR
            and meta2[1] == EXPECTED_NUM
            and meta2[2] == EXPECTED_NUM
        ),
    }


def normalize_search(result):
    if isinstance(result, dict):
        return result.get("matches", []), result.get("error")
    return result, None


def runtime_test(local_mod, b):
    exe = b.find_ppsspp_exe()

    cfg = OUT / "stage39f_append.ini"
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

    port_requested = b.choose_free_port()

    cmd = [
        str(exe),
        "-d",
        f"--log={PPSSPP_LOG}",
        "--windowed",
        f"--appendconfig={cfg}",
        f"--debugger={port_requested}",
        str(TEST_ISO),
    ]

    log("[Stage39F] Launching PPSSPP normal JIT")
    proc = subprocess.Popen(cmd)
    cleanup = b.register_ppsspp_auto_close(proc)

    result = {
        "pid": proc.pid,
        "ppsspp_exe": str(exe),
        "previous_ppsspp_cleanup": previous,
        "normal_jit": True,
        "runtime_patch": False,
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

            try:
                result["version"] = ws.request(
                    "version",
                    timeout=5,
                    name="bia-stage39f",
                    version="1",
                )
            except Exception as e:
                result["version_error"] = str(e)

            # Wait for the MDI streams to be resident before sending input.
            source_ready = False
            for _ in range(120):
                try:
                    src = verify_runtime_sources(ws)
                    if (
                        src["display1_ok"]
                        and src["display2_ok"]
                        and src["menustory_key_ok"]
                        and src["meta1_ok"]
                        and src["meta2_ok"]
                    ):
                        source_ready = True
                        result["runtime_sources"] = src
                        break
                except Exception:
                    pass
                time.sleep(0.25)

            if not source_ready:
                raise RuntimeError(
                    "Corrected stream11/stream16 data did not become resident"
                )

            # At most three Start presses.  Search after EVERY press and stop
            # immediately if real UTF-16 appears, preventing the old behavior
            # of repeatedly leaving the main menu.
            attempts = []

            for press_no in range(0, 4):
                if press_no:
                    try:
                        ws.request(
                            "input.buttons.press",
                            timeout=5,
                            button="start",
                            duration=2,
                        )
                    except Exception:
                        pass
                    time.sleep(1.25)
                else:
                    time.sleep(1.0)

                true_res = search_bytes(ws, UTF16, align=2)
                bad_res = search_bytes(
                    ws, BYTEWISE_WIDENED, align=2
                )

                true_matches, true_error = normalize_search(true_res)
                bad_matches, bad_error = normalize_search(bad_res)

                attempts.append({
                    "start_presses": press_no,
                    "true_utf16_matches": [
                        f"0x{x:08X}" for x in true_matches
                    ],
                    "true_utf16_error": true_error,
                    "bytewise_widened_matches": [
                        f"0x{x:08X}" for x in bad_matches
                    ],
                    "bytewise_widened_error": bad_error,
                })

                if true_matches:
                    break

            result["search_attempts"] = attempts

            last = attempts[-1]
            result["unicode_conversion_proof"] = bool(
                last["true_utf16_matches"]
            )
            result["bytewise_widening_observed"] = bool(
                last["bytewise_widened_matches"]
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
                        plan_path.read_text(encoding="utf-8")
                    )
                    pid, base = b.get_pid_base(hwnd)
                    result["production_font_runtime"] = inspect(
                        pid,
                        base,
                        plan,
                        plan["atlas_sha1"],
                    )
                except Exception as e:
                    result["production_font_runtime_error"] = str(e)

            # Diagnostic screenshot/GPU dump.  Capture failure alone is not a
            # source or font failure.
            capture_fn = find_callable(
                [b, getattr(local_mod, "s39", None), local_mod],
                "capture",
            )
            helper = BASE_TOOLS / "capture_ppsspp.ps1"
            if capture_fn and helper.exists():
                try:
                    capture_fn(hwnd, SCREENSHOT, helper)
                    result["screenshot"] = str(SCREENSHOT)
                except Exception as e:
                    result["screenshot_error"] = str(e)

            record_fn = find_callable(
                [b, getattr(local_mod, "s39", None), local_mod],
                "record_gpu_frame",
            )
            if record_fn:
                try:
                    result["gpu_frame"] = record_fn(
                        ws, GPU_DUMP
                    )
                except Exception as e:
                    result["gpu_frame_error"] = str(e)

            font = result.get("production_font_runtime", {})
            font_ok = (
                font.get("ok", True)
                if isinstance(font, dict)
                else True
            )

            result["completed"] = (
                result["unicode_conversion_proof"]
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

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(OUT.rglob("*")):
            if p.is_file():
                z.write(p, p.relative_to(OUT).as_posix())


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    for p in OUT.iterdir():
        if p.is_file():
            p.unlink()

    local_mod, b = load_helpers()

    report = {
        "stage": "39F",
        "purpose":
            "Correct the Stage39C narrow-string source locations and FString "
            "length metadata, then test whether the existing game path produces "
            "real UTF-16 Korean without any decoder patch.",
        "stage39e_new_finding":
            "The writer at PC 0x08C74EAC / caller RA 0x08C71A74 is inside "
            "the MDI decompressor, not a Unicode converter. The old widened "
            "scratch-copy observation is therefore not proof of byte-wise "
            "character conversion.",
        "critical_stage39c_corrections": [
            "stream11+0x5CB94 is inside internal key MenuStory, not a display value",
            "second real Story display is stream11+0x5CBD0",
            "stream16 FString-like Num/Max metadata must change from 6 to 10 "
            "when Story (5+NUL bytes) becomes UTF-8 Korean (9+NUL bytes)",
        ],
        "decoder_patch": False,
        "runtime_patch": False,
        "uses_old_fixed_story_slot": False,
    }

    source_iso, source_desc, build = build_iso(b)
    report["source_iso"] = str(source_iso)
    report["source_description"] = source_desc
    report["test_iso"] = str(TEST_ISO)
    report["build"] = build

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
        log("[Stage39F] COMPLETE")
        log(f"[Stage39F] ISO: {TEST_ISO}")
        log(f"[Stage39F] Upload ZIP: {SUCCESS_ZIP}")
        return

    make_zip(FAIL_ZIP)
    raise RuntimeError(
        f"Stage39F did not prove real UTF-16 conversion. See {FAIL_ZIP}"
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
        print(f"STAGE 39F FAILED: {FAIL_ZIP}", flush=True)
        raise SystemExit(1)
