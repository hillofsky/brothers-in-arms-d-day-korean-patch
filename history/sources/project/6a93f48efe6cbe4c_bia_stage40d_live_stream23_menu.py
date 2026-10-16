#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import base64
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

SOURCE_ISO = ROOT / "BIA_STAGE39U_BOOT_RENDER_UTF8_TEST.iso"
TEST_ISO = ROOT / "BIA_STAGE40D_LIVE_STREAM23_MENU_TEST.iso"

OUT = ROOT / "analysis" / "stage40d_live_stream23_menu"
LOG_DIR = ROOT / "log"

SUCCESS_ZIP = LOG_DIR / "bia_stage40d_upload.zip"
FAIL_ZIP = LOG_DIR / "fail_bia_stage40d_upload.zip"
REPORT_PATH = OUT / "stage40d_report.json"
PPSSPP_LOG = OUT / "stage40d_ppsspp.log"
SCREENSHOT = OUT / "stage40d_main_menu.png"

TARGET = [
    "PSP_GAME",
    "USRDIR",
    "SYSTEM",
    "ON_MEMU_O.MDI",
]

MDI_SEQ_BASE = 0x08E2D020
MDI_STREAM_SIZE = 0x78000

# Stream23 is definitively resident for the lifetime of the menu because the
# production font glyph array itself starts at its runtime base:
#   stream23 runtime base = 0x098F5020
#   production glyph_ptr  = 0x098F5020
LIVE_STREAM = 23
LIVE_STREAM_BASE = MDI_SEQ_BASE + LIVE_STREAM * MDI_STREAM_SIZE
ALLOC_START = 0xA870
ALLOC_END = 0x77FC0

RENDER_CALL_RUNTIME = 0x08972360
EXPECTED_RENDER_JAL_RUNTIME = bytes.fromhex("e410330e")
FONT_OBJECT = 0x0972385C
EXPECTED_GLYPH_COUNT = 847
EXPECTED_GLYPH_PTR = 0x098F5020

MENU_OPEN_MARKER = (
    "sceIoOpen(disc0:/PSP_GAME/USRDIR/SYSTEM/RAWFILES/MENUINT0.RAW"
)

# Only the three TOP-LEVEL menu display metadata records.
# Story remains the already-proven Stage39U/Stage39F value.
TOP_MENU = [
    {
        "label": "Skirmish",
        "ko": "스커미시",
        "metadata_stream": 16,
        "metadata_offset": 0x3F770,
        "source_ptr": 0x093B1B60,
        "old_num": 9,
        "old_max": 9,
    },
    {
        "label": "Options",
        "ko": "옵션",
        "metadata_stream": 16,
        "metadata_offset": 0x3F78C,
        "source_ptr": 0x093B1B80,
        "old_num": 8,
        "old_max": 8,
    },
    {
        "label": "Profile",
        "ko": "프로필",
        "metadata_stream": 16,
        "metadata_offset": 0x3F7A8,
        "source_ptr": 0x093B1BA0,
        "old_num": 8,
        "old_max": 8,
    },
]

EXPECTED_LABELS = {
    "스토리": "스토리",
    "스커미시": "스커미시",
    "옵션": "옵션",
    "프로필": "프로필",
}

# Search a broad, known menu/runtime region without using unsupported
# memory.search.
SCAN_START = 0x08E00000
SCAN_END = 0x09A00000
SCAN_CHUNK = 0x10000


def log(msg):
    print(msg, flush=True)


def sha1(data):
    import hashlib
    return hashlib.sha1(data).hexdigest()


def align_up(v, a=4):
    return (v + a - 1) & ~(a - 1)


def runtime_addr(stream_index, offset):
    return (
        MDI_SEQ_BASE
        + stream_index * MDI_STREAM_SIZE
        + offset
    )


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


def build_iso(b):
    if not SOURCE_ISO.exists():
        raise RuntimeError(
            f"Missing proven Stage39U ISO: {SOURCE_ISO}"
        )

    if TEST_ISO.exists():
        TEST_ISO.unlink()

    shutil.copy2(SOURCE_ISO, TEST_ISO)

    _, original = b.iso_read_file(
        TEST_ISO,
        TARGET,
    )
    streams = b.parse_mdi(original)

    original_by = {
        st["index"]: bytes(st["decoded"])
        for st in streams
    }
    mutable = {
        si: bytearray(data)
        for si, data in original_by.items()
    }

    if LIVE_STREAM not in original_by:
        raise RuntimeError("Stream23 missing from ON_MEMU_O.MDI")

    # Strong proof that the selected live-stream tail is zero in the original.
    tail = original_by[LIVE_STREAM]
    if ALLOC_START >= len(tail):
        raise RuntimeError("Stream23 allocation start out of bounds")

    cursor = ALLOC_START
    allocations = []

    for item in TOP_MENU:
        blob = item["ko"].encode("utf-8") + b"\x00"
        cursor = align_up(cursor, 4)

        if cursor + len(blob) > min(ALLOC_END, len(tail)):
            raise RuntimeError("Stream23 live allocation space exhausted")

        if any(tail[cursor:cursor+len(blob)]):
            raise RuntimeError(
                f"Stream23 target is not zero at 0x{cursor:X}"
            )

        ptr = runtime_addr(LIVE_STREAM, cursor)

        mutable[LIVE_STREAM][
            cursor:cursor+len(blob)
        ] = blob

        msi = item["metadata_stream"]
        moff = item["metadata_offset"]
        got = struct.unpack_from(
            "<III",
            original_by[msi],
            moff,
        )
        expected = (
            item["source_ptr"],
            item["old_num"],
            item["old_max"],
        )

        if got != expected:
            raise RuntimeError(
                f"{item['label']} metadata precondition mismatch: "
                f"{got} != {expected}"
            )

        new_num = len(blob)
        struct.pack_into(
            "<III",
            mutable[msi],
            moff,
            ptr,
            new_num,
            new_num,
        )

        allocations.append({
            **item,
            "alloc_stream": LIVE_STREAM,
            "alloc_offset": f"0x{cursor:X}",
            "alloc_runtime": f"0x{ptr:08X}",
            "encoded_hex": blob.hex(),
            "new_num": new_num,
            "new_max": new_num,
        })

        cursor += len(blob)

    replacements = {}

    for si, before in original_by.items():
        after = bytes(mutable[si])
        if after != before:
            replacements[si] = after

    if set(replacements) != {16, 23}:
        raise RuntimeError(
            f"Unexpected changed streams: {sorted(replacements)}"
        )

    patched = b.rebuild_mdi(
        original,
        replacements,
    )

    verify = b.parse_mdi(patched)
    verify_by = {
        st["index"]: bytes(st["decoded"])
        for st in verify
    }

    for si, expected in replacements.items():
        if verify_by.get(si) != expected:
            raise RuntimeError(
                f"Decoded readback mismatch for stream {si}"
            )

    # Verify metadata and pointed UTF-8 from rebuilt bytes.
    proof = []

    for a in allocations:
        ptr, num, maxv = struct.unpack_from(
            "<III",
            verify_by[a["metadata_stream"]],
            a["metadata_offset"],
        )

        si = (
            ptr - MDI_SEQ_BASE
        ) // MDI_STREAM_SIZE
        off = (
            ptr - MDI_SEQ_BASE
            - si * MDI_STREAM_SIZE
        )

        raw = verify_by[si][off:off+num]
        text = raw.split(b"\x00",1)[0].decode("utf-8")

        proof.append({
            "label": a["label"],
            "pointer": f"0x{ptr:08X}",
            "num": num,
            "max": maxv,
            "target_stream": si,
            "target_offset": f"0x{off:X}",
            "value": text,
            "ok": (
                si == LIVE_STREAM
                and text == a["ko"]
                and num == a["new_num"]
                and maxv == a["new_max"]
            ),
        })

    if not all(x["ok"] for x in proof):
        raise RuntimeError("Rebuilt menu metadata proof failed")

    b.append_iso_file_and_repoint(
        TEST_ISO,
        TARGET,
        patched,
    )

    _, rb = b.iso_read_file(
        TEST_ISO,
        TARGET,
    )

    if rb != patched:
        raise RuntimeError(
            "ON_MEMU_O ISO readback mismatch"
        )

    return {
        "original_sha1": sha1(original),
        "patched_sha1": sha1(patched),
        "original_size": len(original),
        "patched_size": len(patched),
        "changed_streams": sorted(replacements),
        "live_stream": LIVE_STREAM,
        "live_stream_runtime_base":
            f"0x{LIVE_STREAM_BASE:08X}",
        "allocations": allocations,
        "rebuild_proof": proof,
        "iso_readback_ok": True,
    }


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


def capture(local_mod, b, hwnd):
    fn = find_callable(
        [
            b,
            getattr(local_mod, "s39", None),
            local_mod,
        ],
        "capture",
    )
    helper = BASE_TOOLS / "capture_ppsspp.ps1"

    if not fn or not helper.exists():
        return {
            "captured": False,
            "error": "capture helper unavailable",
        }

    try:
        fn(hwnd, SCREENSHOT, helper)
        return {
            "captured": SCREENSHOT.exists(),
            "path": str(SCREENSHOT),
        }
    except Exception as e:
        return {
            "captured": False,
            "error": str(e),
        }


def scan_memory_for(ws, patterns):
    """
    Search a broad runtime range using memory.read only.
    Supports raw UTF-8, proper UTF-16LE, and widened-byte UTF-8.
    """
    wanted = {}

    for label in patterns:
        utf8 = label.encode("utf-8")
        utf16 = label.encode("utf-16le")
        widened = b"".join(
            bytes((b,0))
            for b in utf8
        )

        wanted[label] = {
            "utf8": utf8,
            "utf16le": utf16,
            "widened_utf8_u16": widened,
        }

    hits = {
        label: {
            kind: None
            for kind in kinds
        }
        for label, kinds in wanted.items()
    }

    overlap = 64
    prev = b""
    addr = SCAN_START

    while addr < SCAN_END:
        size = min(
            SCAN_CHUNK,
            SCAN_END - addr,
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
        data_base = addr - len(prev)

        for label, kinds in wanted.items():
            for kind, needle in kinds.items():
                if hits[label][kind] is not None:
                    continue

                p = data.find(needle)
                if p >= 0:
                    hits[label][kind] = (
                        f"0x{data_base+p:08X}"
                    )

        if all(
            any(v is not None for v in d.values())
            for d in hits.values()
        ):
            break

        prev = data[-overlap:]
        addr += size

    return {
        "hits": hits,
        "all_labels_have_some_representation":
            all(
                any(v is not None for v in d.values())
                for d in hits.values()
            ),
    }


def runtime_metadata_proof(ws, build_info):
    out = []

    for a in build_info["allocations"]:
        maddr = runtime_addr(
            a["metadata_stream"],
            a["metadata_offset"],
        )

        try:
            raw = read_ws(
                ws,
                maddr,
                12,
            )
            ptr, num, maxv = struct.unpack(
                "<III",
                raw,
            )

            item = {
                "label": a["label"],
                "metadata_runtime":
                    f"0x{maddr:08X}",
                "raw_hex": raw.hex(),
                "ptr": f"0x{ptr:08X}",
                "num": num,
                "max": maxv,
                "expected_ptr":
                    a["alloc_runtime"],
                "expected_num":
                    a["new_num"],
                "expected_max":
                    a["new_max"],
            }

            item["metadata_ok"] = (
                ptr == int(a["alloc_runtime"],16)
                and num == a["new_num"]
                and maxv == a["new_max"]
            )

            try:
                value_raw = read_ws(
                    ws,
                    ptr,
                    max(1,num),
                )
                value = value_raw.split(
                    b"\x00",1
                )[0].decode(
                    "utf-8",
                    errors="replace",
                )
                item["value"] = value
                item["pointer_read_ok"] = (
                    value == a["ko"]
                )
            except Exception as e:
                item["pointer_read_ok"] = False
                item["pointer_read_error"] = str(e)

            item["ok"] = (
                item["metadata_ok"]
                and item["pointer_read_ok"]
            )
            out.append(item)

        except Exception as e:
            out.append({
                "label": a["label"],
                "metadata_runtime":
                    f"0x{maddr:08X}",
                "ok": False,
                "error": str(e),
            })

    return out


def runtime_test(local_mod, b, build_info):
    exe = b.find_ppsspp_exe()

    cfg = OUT / "stage40d_append.ini"
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
        str(TEST_ISO),
    ]

    log("[Stage40D] Launching PPSSPP")
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

            # Skip startup only until MENUINT0 opens.
            end = time.time() + 180
            last_press = 0
            presses = 0
            opened = False

            while time.time() < end:
                if PPSSPP_LOG.exists():
                    txt = PPSSPP_LOG.read_text(
                        encoding="utf-8",
                        errors="replace",
                    )
                    if MENU_OPEN_MARKER in txt:
                        opened = True
                        break

                now = time.time()
                if now-last_press >= 1.25:
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

            result["menu_resource"] = {
                "opened": opened,
                "startup_start_presses": presses,
            }
            if not opened:
                raise RuntimeError(
                    "MENUINT0.RAW did not open"
                )

            # Verify stream23 pointers BEFORE entering main menu.
            time.sleep(0.5)
            result["runtime_metadata"] = (
                runtime_metadata_proof(
                    ws,
                    build_info,
                )
            )

            # Proven title settle, then EXACTLY ONE Start.
            # No retry Start is allowed; the previous Stage40C second Start could
            # enter a submenu and destroy the diagnostic screenshot state.
            time.sleep(2.0)

            ws.request(
                "input.buttons.press",
                timeout=5,
                button="start",
                duration=2,
            )

            # Wait for Story's already-proven dynamic string to appear, which
            # confirms the selectable menu state without requiring English
            # Options/Profile anchors.
            story_utf16 = (
                "스토리".encode("utf-16le")
                + b"\x00\x00"
            )

            menu_confirmed = False
            story_addr = None
            deadline = time.time() + 12

            while time.time() < deadline:
                try:
                    block = read_ws(
                        ws,
                        0x08E40000,
                        0x8000,
                    )
                    p = block.find(story_utf16)
                    if p >= 0:
                        story_addr = (
                            0x08E40000 + p
                        )
                        menu_confirmed = True
                        break
                except Exception:
                    pass
                time.sleep(0.12)

            result["menu_confirmed"] = {
                "ok": menu_confirmed,
                "story_utf16_addr":
                    None
                    if story_addr is None
                    else f"0x{story_addr:08X}",
            }

            # Scan broad RAM while still on the main menu.
            result["label_representations"] = (
                scan_memory_for(
                    ws,
                    list(EXPECTED_LABELS),
                )
            )

            # Font proof only after menu initialization.
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

            time.sleep(0.75)
            result["screenshot"] = capture(
                local_mod,
                b,
                hwnd,
            )

            metadata_ok = all(
                x.get("ok",False)
                for x in result["runtime_metadata"]
            )

            result["ok"] = (
                result["renderer_jal"]["actual"]
                == result["renderer_jal"]["expected"]
                and metadata_ok
                and menu_confirmed
                and result["font_after_menu"][
                    "glyph_count_ok"
                ]
                and result["font_after_menu"][
                    "glyph_ptr_ok"
                ]
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
        "stage": "40D",
        "purpose":
            "Test whether Stage40C corruption came from relocating menu "
            "strings into non-resident stream20. Patch only the three top-level "
            "menu values and relocate them into definitively-live stream23.",
        "stage40c_diagnosis": {
            "build_was_valid":
                "ON_MEMU rebuilt and ISO readback succeeded; 1675 metadata "
                "actions / 690 units were structurally applied.",
            "renderer_font_ok":
                "Stage39U renderer JAL and production font remained correct "
                "(glyph_count 847, glyph_ptr 0x098F5020).",
            "runtime_symptom":
                "Stage40C runtime metadata dereference for translated menu "
                "values returned Invalid address and the screenshot showed "
                "Story correct but the other visible menu lines corrupted.",
            "allocation_problem":
                "Stage40C put all translated payloads in stream20 because it "
                "had the largest zero tail. Stream20 was never proven resident. "
                "Stage40D instead uses stream23, whose runtime base is exactly "
                "the live production glyph_ptr 0x098F5020.",
            "input_bug_fixed":
                "Stage40C sent a second Start because the Skirmish scan failed. "
                "Stage40D sends exactly one title Start and captures that state.",
        },
        "source_iso": str(SOURCE_ISO),
        "test_iso": str(TEST_ISO),
        "live_stream": LIVE_STREAM,
        "live_stream_base":
            f"0x{LIVE_STREAM_BASE:08X}",
    }

    try:
        build = build_iso(b)
        report["build"] = build

        runtime = runtime_test(
            local_mod,
            b,
            build,
        )
        report["runtime"] = runtime
        report["completed"] = bool(
            runtime.get("ok",False)
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
            f"Stage40D failed. See {FAIL_ZIP}"
        )

    log("[Stage40D] COMPLETE")
    log(f"[Stage40D] ISO: {TEST_ISO}")
    log(f"[Stage40D] Upload ZIP: {SUCCESS_ZIP}")


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
            f"STAGE 40D FAILED: {FAIL_ZIP}",
            flush=True,
        )
        raise SystemExit(1)
