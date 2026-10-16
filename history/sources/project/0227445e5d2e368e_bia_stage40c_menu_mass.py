#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import base64
import csv
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
from collections import defaultdict
from pathlib import Path

ROOT = Path(r"PROJECT_ROOT")
BASE_TOOLS = ROOT / "bia_stage39b_tools"

SOURCE_ISO = ROOT / "BIA_STAGE39U_BOOT_RENDER_UTF8_TEST.iso"
TEST_ISO = ROOT / "BIA_STAGE40C_MENU_MASS_TEST.iso"

OUT = ROOT / "analysis" / "stage40c_menu_mass"
LOG_DIR = ROOT / "log"

SUCCESS_ZIP = LOG_DIR / "bia_stage40c_upload.zip"
FAIL_ZIP = LOG_DIR / "fail_bia_stage40c_upload.zip"

REPORT_PATH = OUT / "stage40c_report.json"
PPSSPP_LOG = OUT / "stage40c_ppsspp.log"
SCREENSHOT = OUT / "stage40c_main_menu.png"

SCRIPT_DIR = Path(__file__).resolve().parent
PLAN_PATH = SCRIPT_DIR / "stage40c_on_memu_plan.tsv"
CORPUS_PATH = SCRIPT_DIR / "stage39a_A_translations.tsv"

TARGET = [
    "PSP_GAME",
    "USRDIR",
    "SYSTEM",
    "ON_MEMU_O.MDI",
]

MDI_SEQ_BASE = 0x08E2D020
MDI_STREAM_SIZE = 0x78000

# Stage39U runtime invariants.
RENDER_CALL_RUNTIME = 0x08972360
EXPECTED_RENDER_JAL_RUNTIME = bytes.fromhex("e410330e")
FONT_OBJECT = 0x0972385C
EXPECTED_GLYPH_COUNT = 847
EXPECTED_GLYPH_PTR = 0x098F5020

MENU_OPEN_MARKER = (
    "sceIoOpen(disc0:/PSP_GAME/USRDIR/SYSTEM/RAWFILES/MENUINT0.RAW"
)

# Search the known dynamic localization work area rather than hard-coding the
# old English string addresses. Stage40B translated Options/Profile, so the
# old Stage39R anchors are intentionally no longer valid success criteria.
DYNAMIC_SCAN_START = 0x08E40000
DYNAMIC_SCAN_END = 0x08E46000

EXPECTED_DYNAMIC = {
    "스토리": "스토리".encode("utf-16le") + b"\x00\x00",
    "스커미시": "스커미시".encode("utf-16le") + b"\x00\x00",
    "옵션": "옵션".encode("utf-16le") + b"\x00\x00",
    "프로필": "프로필".encode("utf-16le") + b"\x00\x00",
}

# Direct source/metadata proof points from Stage39F/40B.
PROOF_FIELDS = [
    {
        "label": "Skirmish",
        "source_addr": 0x093B1B60,
        "metadata_addr": 0x095EC790,
        "expected_ko": "스커미시",
    },
    {
        "label": "Options",
        "source_addr": 0x093B1B80,
        "metadata_addr": 0x095EC7AC,
        "expected_ko": "옵션",
    },
    {
        "label": "Profile",
        "source_addr": 0x093B1BA0,
        "metadata_addr": 0x095EC7C8,
        "expected_ko": "프로필",
    },
]

RAM_START = 0x08800000
RAM_END = 0x0A800000


def log(msg):
    print(msg, flush=True)


def sha1(data):
    return hashlib.sha1(data).hexdigest()


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


def load_plan():
    rows = list(csv.DictReader(
        PLAN_PATH.open(
            encoding="utf-8-sig",
            newline="",
        ),
        delimiter="\t",
    ))

    if len(rows) != 1675:
        raise RuntimeError(
            f"Expected 1675 ON_MEMU actions, got {len(rows)}"
        )

    units = {x["unit_id"] for x in rows}

    if len(units) != 690:
        raise RuntimeError(
            f"Expected 690 unique menu units, got {len(units)}"
        )

    if {x["kind"] for x in rows} != {"narrow_reloc"}:
        raise RuntimeError("Unexpected action kind in plan")

    return rows, units


def parse_int(v):
    s = str(v).strip()
    if not s:
        return None
    return int(s, 0)


def patch_menu_mdi(b, original, plan):
    streams = b.parse_mdi(original)
    original_by = {
        st["index"]: bytes(st["decoded"])
        for st in streams
    }
    mutable = {
        si: bytearray(data)
        for si, data in original_by.items()
    }

    # Group allocation targets. The same Korean value is intentionally
    # deduplicated and referenced by many metadata records.
    alloc_groups = defaultdict(list)

    for row in plan:
        asi = parse_int(row["alloc_stream"])
        aoff = parse_int(row["alloc_offset"])

        if asi is None or aoff is None:
            raise RuntimeError(
                f"Missing allocation address: {row}"
            )

        alloc_groups[(asi, aoff)].append(row)

    allocation_report = []

    for (si, off), rows in sorted(alloc_groups.items()):
        sample = rows[0]
        ko = sample["korean"]
        blob = ko.encode("utf-8") + b"\x00"

        expected_runtime = parse_int(sample["alloc_runtime"])
        expected_len = parse_int(sample["encoded_bytes"])

        if len(blob) != expected_len:
            raise RuntimeError(
                f"{ko!r}: encoded length mismatch "
                f"{len(blob)} != {expected_len}"
            )

        if runtime_addr(si, off) != expected_runtime:
            raise RuntimeError(
                f"{ko!r}: runtime allocation mismatch"
            )

        for other in rows[1:]:
            if (
                other["korean"] != ko
                or parse_int(other["encoded_bytes"]) != expected_len
                or parse_int(other["alloc_runtime"]) != expected_runtime
            ):
                raise RuntimeError(
                    f"Inconsistent deduplicated allocation at stream {si} off 0x{off:X}"
                )

        src = original_by[si]

        if off + len(blob) > len(src):
            raise RuntimeError(
                f"Allocation out of stream bounds: {si}:0x{off:X}"
            )

        if any(src[off:off+len(blob)]):
            raise RuntimeError(
                f"Allocation target was not zero padding: {si}:0x{off:X}"
            )

        mutable[si][off:off+len(blob)] = blob

        allocation_report.append({
            "stream": si,
            "offset": f"0x{off:X}",
            "runtime": f"0x{expected_runtime:08X}",
            "korean": ko,
            "bytes": len(blob),
            "reference_count": len(rows),
        })

    metadata_report = []

    for row in plan:
        msi = parse_int(row["metadata_stream"])
        moff = parse_int(row["metadata_offset"])

        source_runtime = parse_int(row["source_runtime"])
        old_num = parse_int(row["old_num"])
        old_max = parse_int(row["old_max"])

        new_ptr = parse_int(row["alloc_runtime"])
        new_num = parse_int(row["new_num"])
        new_max = parse_int(row["new_max"])

        dec = original_by[msi]

        if moff + 12 > len(dec):
            raise RuntimeError(
                f"Metadata out of bounds: {msi}:0x{moff:X}"
            )

        got = struct.unpack_from(
            "<III",
            dec,
            moff,
        )
        expected = (
            source_runtime,
            old_num,
            old_max,
        )

        if got != expected:
            raise RuntimeError(
                f"Metadata precondition mismatch "
                f"{row['english']!r} stream {msi} off 0x{moff:X}: "
                f"{got} != {expected}"
            )

        struct.pack_into(
            "<III",
            mutable[msi],
            moff,
            new_ptr,
            new_num,
            new_max,
        )

        metadata_report.append({
            "unit_id": row["unit_id"],
            "english": row["english"],
            "korean": row["korean"],
            "stream": msi,
            "offset": f"0x{moff:X}",
            "old_ptr": f"0x{source_runtime:08X}",
            "new_ptr": f"0x{new_ptr:08X}",
            "old_num": old_num,
            "new_num": new_num,
        })

    replacements = {}

    for si, before in original_by.items():
        after = bytes(mutable[si])

        if after != before:
            replacements[si] = after

    # Stage40B found exactly these changed streams for ON_MEMU_O.
    expected_changed = {
        1,2,3,4,8,9,10,11,12,13,14,15,16,19,20
    }

    if set(replacements) != expected_changed:
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
                f"Rebuilt stream {si} read-back mismatch"
            )

    # Explicitly prove the first main-menu values now point to translated UTF-8.
    proof = []

    for label, source_off, metadata_off in [
        ("Skirmish", 0x5CB40, 0x3F770),
        ("Options", 0x5CB60, 0x3F78C),
        ("Profile", 0x5CB80, 0x3F7A8),
    ]:
        md = verify_by[16]
        ptr, num, maxv = struct.unpack_from(
            "<III",
            md,
            metadata_off,
        )

        target_stream = (
            (ptr - MDI_SEQ_BASE) // MDI_STREAM_SIZE
        )
        target_off = (
            ptr - MDI_SEQ_BASE
            - target_stream * MDI_STREAM_SIZE
        )

        data = verify_by[target_stream]

        end = data.find(
            b"\x00",
            target_off,
            target_off + max(1, num),
        )

        if end < 0:
            raise RuntimeError(
                f"{label}: translated NUL not found"
            )

        text = data[
            target_off:end
        ].decode("utf-8")

        proof.append({
            "label": label,
            "pointer": f"0x{ptr:08X}",
            "num": num,
            "max": maxv,
            "target_stream": target_stream,
            "target_offset": f"0x{target_off:X}",
            "utf8": text,
        })

    return patched, {
        "unique_allocations": len(alloc_groups),
        "metadata_actions": len(metadata_report),
        "unique_units": len({
            x["unit_id"] for x in plan
        }),
        "changed_streams": sorted(replacements),
        "allocations": allocation_report,
        "main_menu_proof": proof,
    }


def build_iso(b, plan):
    if not SOURCE_ISO.exists():
        raise RuntimeError(
            f"Missing Stage39U ISO: {SOURCE_ISO}"
        )

    if TEST_ISO.exists():
        TEST_ISO.unlink()

    shutil.copy2(
        SOURCE_ISO,
        TEST_ISO,
    )

    _, original = b.iso_read_file(
        TEST_ISO,
        TARGET,
    )

    patched, info = patch_menu_mdi(
        b,
        original,
        plan,
    )

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
            "Patched ON_MEMU_O.MDI ISO read-back mismatch"
        )

    info.update({
        "original_size": len(original),
        "patched_size": len(patched),
        "original_sha1": sha1(original),
        "patched_sha1": sha1(patched),
        "iso_readback_ok": True,
    })

    return info


def read_ws(ws, address, size):
    r = ws.request(
        "memory.read",
        timeout=10,
        address=address,
        size=size,
    )
    return base64.b64decode(
        r["base64"]
    )


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


def scan_dynamic_labels(ws):
    try:
        blob = read_ws(
            ws,
            DYNAMIC_SCAN_START,
            DYNAMIC_SCAN_END - DYNAMIC_SCAN_START,
        )
    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
            "hits": {},
        }

    hits = {}

    for label, needle in EXPECTED_DYNAMIC.items():
        pos = blob.find(needle)

        hits[label] = (
            None
            if pos < 0
            else f"0x{DYNAMIC_SCAN_START + pos:08X}"
        )

    return {
        "ok": all(v is not None for v in hits.values()),
        "hits": hits,
    }


def read_runtime_proof_fields(ws):
    result = []

    for p in PROOF_FIELDS:
        try:
            ptr, num, maxv = struct.unpack(
                "<III",
                read_ws(
                    ws,
                    p["metadata_addr"],
                    12,
                ),
            )

            # The translated values all live in stream20 in the Stage40C plan.
            raw = read_ws(
                ws,
                ptr,
                max(1, num),
            )
            text = raw.split(b"\x00", 1)[0].decode(
                "utf-8",
                errors="replace",
            )

            result.append({
                "label": p["label"],
                "metadata_addr":
                    f"0x{p['metadata_addr']:08X}",
                "ptr": f"0x{ptr:08X}",
                "num": num,
                "max": maxv,
                "value": text,
                "expected": p["expected_ko"],
                "ok":
                    text == p["expected_ko"],
            })
        except Exception as e:
            result.append({
                "label": p["label"],
                "ok": False,
                "error": str(e),
            })

    return result


def find_callable(objects, name):
    for obj in objects:
        if obj is not None and hasattr(obj, name):
            fn = getattr(obj, name)
            if callable(fn):
                return fn
    return None


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
        fn(
            hwnd,
            SCREENSHOT,
            helper,
        )
        return {
            "captured": SCREENSHOT.exists(),
            "path": str(SCREENSHOT),
        }
    except Exception as e:
        return {
            "captured": False,
            "error": str(e),
        }


def runtime_test(local_mod, b):
    exe = b.find_ppsspp_exe()

    cfg = OUT / "stage40c_append.ini"
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

    log("[Stage40C] Launching PPSSPP menu-only proof")
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

            # Do NOT read font object yet. Stage40B did that before font
            # initialization and got a false 0/NULL result.

            # Skip startup only until MENUINT0 is really opened.
            end = time.time() + 180
            last_press = 0
            presses = 0
            opened = False

            while time.time() < end:
                if PPSSPP_LOG.exists():
                    text = PPSSPP_LOG.read_text(
                        encoding="utf-8",
                        errors="replace",
                    )

                    if MENU_OPEN_MARKER in text:
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

            # Prove the compiled metadata itself is translated in live RAM.
            time.sleep(0.5)
            result["runtime_menu_metadata"] = (
                read_runtime_proof_fields(ws)
            )

            # Proven title input timing.
            time.sleep(2.0)

            # Up to two safe title Start presses. We no longer use old
            # Options/Profile English anchors because those strings are now
            # intentionally translated.
            scans = []

            for attempt in (1, 2):
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
                found = False

                while time.time()-start < 10:
                    s = scan_dynamic_labels(ws)
                    scans.append({
                        "attempt": attempt,
                        "elapsed":
                            time.time()-start,
                        **s,
                    })

                    if s.get("ok"):
                        found = True
                        break

                    time.sleep(0.20)

                if found:
                    break

            result["dynamic_label_scans"] = scans
            result["dynamic_labels"] = (
                scan_dynamic_labels(ws)
            )

            # Now the font object must be initialized.
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
                    glyph_count == EXPECTED_GLYPH_COUNT,
                "glyph_ptr":
                    f"0x{glyph_ptr:08X}",
                "glyph_ptr_ok":
                    glyph_ptr == EXPECTED_GLYPH_PTR,
            }

            # Capture regardless of automatic label-detection outcome.
            time.sleep(0.8)
            result["screenshot"] = capture(
                local_mod,
                b,
                hwnd,
            )

            metadata_ok = all(
                x.get("ok", False)
                for x in result[
                    "runtime_menu_metadata"
                ]
            )

            result["ok"] = (
                result["renderer_jal"]["actual"]
                == result["renderer_jal"]["expected"]
                and metadata_ok
                and result["dynamic_labels"].get(
                    "ok", False
                )
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

        z.write(
            PLAN_PATH,
            "stage40c_on_memu_plan.tsv",
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

    plan, units = load_plan()
    local_mod, b = load_helpers()

    report = {
        "stage": "40C",
        "purpose":
            "Validate the mass-relocation method on ON_MEMU_O.MDI only before "
            "touching mission MDIs.",
        "stage40b_diagnosis": {
            "mass_patch_actions": 44923,
            "patched_units": 720,
            "matched_units": 730,
            "changed_mdis": 57,
            "problem_1":
                "Stage40B patched every MDI before the ON_MEMU relocation "
                "method had been visually proven.",
            "problem_2":
                "Its smoke test read the production font object before font "
                "initialization, so glyph_count=0/glyph_ptr=0 was a false "
                "failure signal.",
            "problem_3":
                "Its main-menu success test still required English Options/"
                "Profile at the old Stage39R addresses even though Stage40B "
                "intentionally translated those values.",
            "result":
                "The Stage40B ISO is not promoted. Stage40C restarts from the "
                "known-good Stage39U ISO and patches only ON_MEMU_O.",
        },
        "plan": {
            "metadata_actions": len(plan),
            "unique_units": len(units),
            "kind": "narrow_reloc only",
        },
        "source_iso": str(SOURCE_ISO),
        "test_iso": str(TEST_ISO),
    }

    try:
        report["build"] = build_iso(
            b,
            plan,
        )
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
            f"Stage40C failed. See {FAIL_ZIP}"
        )

    log("[Stage40C] COMPLETE")
    log(
        f"[Stage40C] ISO: {TEST_ISO}"
    )
    log(
        f"[Stage40C] Upload ZIP: {SUCCESS_ZIP}"
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
            f"STAGE 40C FAILED: {FAIL_ZIP}",
            flush=True,
        )
        raise SystemExit(1)
