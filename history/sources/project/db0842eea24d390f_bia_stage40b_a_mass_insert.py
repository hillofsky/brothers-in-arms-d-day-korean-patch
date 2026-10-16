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
import re
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
TEST_ISO = ROOT / "BIA_STAGE40B_A_MASS_TEST.iso"

OUT = ROOT / "analysis" / "stage40b_a_mass_insert"
LOG_DIR = ROOT / "log"

SUCCESS_ZIP = LOG_DIR / "bia_stage40b_upload.zip"
FAIL_ZIP = LOG_DIR / "fail_bia_stage40b_upload.zip"

REPORT_PATH = OUT / "stage40b_report.json"
PATCH_TSV = OUT / "stage40b_patch_actions.tsv"
UNIT_TSV = OUT / "stage40b_unit_coverage.tsv"
SKIP_TSV = OUT / "stage40b_skipped.tsv"
PPSSPP_LOG = OUT / "stage40b_ppsspp.log"
SCREENSHOT = OUT / "stage40b_main_menu.png"

SCRIPT_DIR = Path(__file__).resolve().parent
CORPUS_PATH = SCRIPT_DIR / "stage39a_A_translations.tsv"
ENTRY_MAP_PATH = SCRIPT_DIR / "stage38b_entry_map.tsv"

SYSTEM_DIR = ROOT / "extracted" / "PSP_GAME" / "USRDIR" / "SYSTEM"

# Runtime stream layout proven by Stages 36-39.
MDI_SEQ_BASE = 0x08E2D020
MDI_STREAM_SIZE = 0x78000

# Strings.
NARROW_RE = re.compile(
    rb'[\x09\x0A\x0D\x20-\x7E]{2,}\x00'
)
UTF16_ASCII_RE = re.compile(
    rb'(?:(?:[\x20-\x7E]\x00)){2,}\x00\x00'
)

# Conservative relocation allocator.
ALLOC_GUARD_BEFORE = 0x40
ALLOC_GUARD_AFTER = 0x40
MIN_TAIL_HOLE = 0x400

# Main-menu smoke-test anchors proven in Stage39R/U.
MAINMENU_OPTIONS_ADDR = 0x08E41660
MAINMENU_PROFILE_ADDR = 0x08E41680
MAINMENU_STORY_ADDR = 0x08E416C0

UTF16_OPTIONS = "Options".encode("utf-16le")
UTF16_PROFILE = "Profile".encode("utf-16le")
UTF16_STORY = "스토리".encode("utf-16le")

MENU_OPEN_MARKER = (
    "sceIoOpen(disc0:/PSP_GAME/USRDIR/SYSTEM/RAWFILES/MENUINT0.RAW"
)

# Stage39U executable/font invariants.
RENDER_CALL_RUNTIME = 0x08972360
EXPECTED_RENDER_JAL_RUNTIME = bytes.fromhex("e410330e")
FONT_OBJECT = 0x0972385C
EXPECTED_GLYPH_COUNT = 847
EXPECTED_GLYPH_PTR = 0x098F5020

RAM_START = 0x08800000
RAM_END = 0x0A800000


def log(msg):
    print(msg, flush=True)


def sha1(data):
    return hashlib.sha1(data).hexdigest()


def align_up(v, a):
    return (v + (a - 1)) & ~(a - 1)


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
        raise RuntimeError("Could not resolve Stage39B base helpers")

    return mod, b


def find_callable(objects, name):
    for obj in objects:
        if obj is not None and hasattr(obj, name):
            fn = getattr(obj, name)
            if callable(fn):
                return fn
    return None


def load_corpus():
    rows = list(csv.DictReader(
        CORPUS_PATH.open(
            encoding="utf-8-sig",
            newline="",
        ),
        delimiter="\t",
    ))

    if len(rows) != 1082:
        raise RuntimeError(
            f"Expected 1082 translations, got {len(rows)}"
        )

    exact = {}
    upper = defaultdict(list)

    hangul = set()

    for row in rows:
        eng = row["English"]
        ko = row["한국어"]

        if not eng or not ko:
            raise RuntimeError(
                f"Empty translation row: {row.get('id')}"
            )

        if eng in exact:
            raise RuntimeError(
                f"Duplicate English unit: {eng!r}"
            )

        exact[eng] = row
        upper[eng.upper()].append(row)

        for ch in ko:
            if "\uAC00" <= ch <= "\uD7A3":
                hangul.add(ch)

    upper_unique = {
        k: vals[0]
        for k, vals in upper.items()
        if len({x["한국어"] for x in vals}) == 1
    }
    upper_conflicts = {
        k: vals
        for k, vals in upper.items()
        if len({x["한국어"] for x in vals}) != 1
    }

    if len(hangul) != 696:
        raise RuntimeError(
            f"Expected 696 unique Hangul syllables, got {len(hangul)}"
        )

    return rows, exact, upper_unique, upper_conflicts, hangul


def mdi_runtime_addr(stream_index, offset):
    return (
        MDI_SEQ_BASE
        + stream_index * MDI_STREAM_SIZE
        + offset
    )


def trailing_zero_region(data):
    """
    Return a conservative allocator region inside the trailing all-zero padding.
    Nothing is inserted beyond the original decoded stream length.
    """
    i = len(data)

    while i > 0 and data[i-1] == 0:
        i -= 1

    start = align_up(
        i + ALLOC_GUARD_BEFORE,
        4,
    )
    end = max(start, len(data) - ALLOC_GUARD_AFTER)

    if end - start < MIN_TAIL_HOLE:
        return None

    return {
        "start": start,
        "end": end,
        "cursor": start,
        "capacity": end - start,
    }


def make_allocator(streams):
    regions = []

    for st in streams:
        region = trailing_zero_region(
            st["decoded"]
        )
        if not region:
            continue

        region = dict(region)
        region["stream"] = st["index"]
        regions.append(region)

    # Largest safe tail first.
    regions.sort(
        key=lambda x: x["capacity"],
        reverse=True,
    )

    return regions


def alloc_blob(
    mutable_streams,
    regions,
    cache,
    key,
    blob,
):
    """
    Deduplicate identical translated strings within one MDI.
    """
    if key in cache:
        return cache[key]

    need = len(blob)

    for r in regions:
        pos = align_up(r["cursor"], 4)

        if pos + need > r["end"]:
            continue

        si = r["stream"]
        dst = mutable_streams[si]

        # The allocator is allowed to use only untouched zero padding.
        if any(dst[pos:pos+need]):
            continue

        dst[pos:pos+need] = blob
        r["cursor"] = pos + need

        result = {
            "stream": si,
            "offset": pos,
            "runtime_address":
                mdi_runtime_addr(si, pos),
            "bytes": need,
        }
        cache[key] = result
        return result

    return None


def metadata_refs(
    original_streams,
    runtime_addr,
    expected_num,
):
    """
    Find high-confidence FString/TArray-like records:
        u32 pointer
        u32 Num
        u32 Max

    The pointer must be 4-byte aligned and Num must exactly match the source
    string's element count. Max may be equal or larger.
    """
    target = struct.pack("<I", runtime_addr)
    refs = []

    for st in original_streams:
        dec = st["decoded"]
        pos = 0

        while True:
            p = dec.find(target, pos)

            if p < 0:
                break

            pos = p + 1

            if p & 3:
                continue
            if p + 12 > len(dec):
                continue

            ptr, num, maxv = struct.unpack_from(
                "<III",
                dec,
                p,
            )

            if ptr != runtime_addr:
                continue
            if num != expected_num:
                continue
            if maxv < num or maxv > 0x100000:
                continue

            refs.append({
                "stream": st["index"],
                "offset": p,
                "num": num,
                "max": maxv,
            })

    return refs


def extra_utf16_capacity(data, end, limit=256):
    extra = 0
    p = end

    while (
        p + 2 <= len(data)
        and extra < limit
        and data[p:p+2] == b"\x00\x00"
    ):
        extra += 1
        p += 2

    return extra


def inspect_mdi(
    b,
    mdi_name,
    data,
    exact,
    upper_unique,
):
    streams = b.parse_mdi(data)
    original = [
        {
            **st,
            "decoded": bytes(st["decoded"]),
        }
        for st in streams
    ]
    mutable = {
        st["index"]: bytearray(st["decoded"])
        for st in streams
    }

    regions = make_allocator(original)
    alloc_cache = {}

    actions = []
    skips = []
    matched_units = set()
    patched_units = set()

    # ------------------------------------------------------------------
    # Narrow ANSI/UTF-8 source strings.
    # Exact case only. This avoids translating internal uppercase keys merely
    # because a display value exists with the same spelling.
    # ------------------------------------------------------------------
    narrow_candidates = []

    for st in original:
        dec = st["decoded"]

        for m in NARROW_RE.finditer(dec):
            raw = m.group()[:-1]

            if len(raw) > 4096:
                continue

            try:
                text = raw.decode("ascii")
            except Exception:
                continue

            row = exact.get(text)
            if row is None:
                continue

            off = m.start()
            addr = mdi_runtime_addr(
                st["index"], off
            )
            expected_num = len(raw) + 1
            refs = metadata_refs(
                original,
                addr,
                expected_num,
            )

            matched_units.add(row["id"])

            narrow_candidates.append({
                "row": row,
                "stream": st["index"],
                "offset": off,
                "runtime": addr,
                "english": text,
                "refs": refs,
                "source_num": expected_num,
            })

    for c in narrow_candidates:
        row = c["row"]
        ko = row["한국어"]

        if not c["refs"]:
            skips.append({
                "mdi": mdi_name,
                "unit_id": row["id"],
                "kind": "narrow",
                "english": c["english"],
                "korean": ko,
                "stream": c["stream"],
                "offset": f"0x{c['offset']:X}",
                "reason":
                    "Exact narrow source found but no matching ptr/Num/Max metadata",
            })
            continue

        blob = ko.encode("utf-8") + b"\x00"

        alloc = alloc_blob(
            mutable,
            regions,
            alloc_cache,
            ("utf8", ko),
            blob,
        )

        if alloc is None:
            skips.append({
                "mdi": mdi_name,
                "unit_id": row["id"],
                "kind": "narrow",
                "english": c["english"],
                "korean": ko,
                "stream": c["stream"],
                "offset": f"0x{c['offset']:X}",
                "reason":
                    "No safe trailing-zero relocation space",
            })
            continue

        for ref in c["refs"]:
            md = mutable[ref["stream"]]
            struct.pack_into(
                "<III",
                md,
                ref["offset"],
                alloc["runtime_address"],
                len(blob),
                len(blob),
            )

            actions.append({
                "mdi": mdi_name,
                "unit_id": row["id"],
                "kind": "narrow_reloc",
                "english": c["english"],
                "korean": ko,
                "source_stream": c["stream"],
                "source_offset": f"0x{c['offset']:X}",
                "source_runtime":
                    f"0x{c['runtime']:08X}",
                "metadata_stream": ref["stream"],
                "metadata_offset":
                    f"0x{ref['offset']:X}",
                "old_num": ref["num"],
                "old_max": ref["max"],
                "new_num": len(blob),
                "new_max": len(blob),
                "alloc_stream": alloc["stream"],
                "alloc_offset":
                    f"0x{alloc['offset']:X}",
                "alloc_runtime":
                    f"0x{alloc['runtime_address']:08X}",
                "encoded_bytes": len(blob),
            })

        patched_units.add(row["id"])

    # ------------------------------------------------------------------
    # Compiled UTF-16 ASCII literals.
    #
    # These were already proven safe in Stage39B. Use case-insensitive unique
    # corpus matching because compiled UI often uppercases the display literal.
    #
    # If metadata exists, relocate with a new pointer. If not, use only the
    # original field plus immediately-following UTF-16 NUL padding.
    # ------------------------------------------------------------------
    utf16_candidates = []

    for st in original:
        dec = st["decoded"]

        for m in UTF16_ASCII_RE.finditer(dec):
            raw = m.group()[:-2]

            try:
                text = raw.decode("utf-16le")
            except Exception:
                continue

            row = upper_unique.get(text.upper())
            if row is None:
                continue

            off = m.start()
            addr = mdi_runtime_addr(
                st["index"], off
            )
            expected_num = len(text) + 1
            refs = metadata_refs(
                original,
                addr,
                expected_num,
            )

            matched_units.add(row["id"])

            utf16_candidates.append({
                "row": row,
                "stream": st["index"],
                "offset": off,
                "runtime": addr,
                "english": text,
                "match_end": m.end(),
                "refs": refs,
                "source_num": expected_num,
            })

    for c in utf16_candidates:
        row = c["row"]
        ko = row["한국어"]

        if c["refs"]:
            blob = (
                ko.encode("utf-16le")
                + b"\x00\x00"
            )

            alloc = alloc_blob(
                mutable,
                regions,
                alloc_cache,
                ("utf16", ko),
                blob,
            )

            if alloc is None:
                skips.append({
                    "mdi": mdi_name,
                    "unit_id": row["id"],
                    "kind": "utf16",
                    "english": c["english"],
                    "korean": ko,
                    "stream": c["stream"],
                    "offset": f"0x{c['offset']:X}",
                    "reason":
                        "No safe trailing-zero relocation space",
                })
                continue

            for ref in c["refs"]:
                md = mutable[ref["stream"]]
                new_num = len(ko) + 1

                struct.pack_into(
                    "<III",
                    md,
                    ref["offset"],
                    alloc["runtime_address"],
                    new_num,
                    new_num,
                )

                actions.append({
                    "mdi": mdi_name,
                    "unit_id": row["id"],
                    "kind": "utf16_reloc",
                    "english": c["english"],
                    "korean": ko,
                    "source_stream": c["stream"],
                    "source_offset":
                        f"0x{c['offset']:X}",
                    "source_runtime":
                        f"0x{c['runtime']:08X}",
                    "metadata_stream":
                        ref["stream"],
                    "metadata_offset":
                        f"0x{ref['offset']:X}",
                    "old_num": ref["num"],
                    "old_max": ref["max"],
                    "new_num": new_num,
                    "new_max": new_num,
                    "alloc_stream": alloc["stream"],
                    "alloc_offset":
                        f"0x{alloc['offset']:X}",
                    "alloc_runtime":
                        f"0x{alloc['runtime_address']:08X}",
                    "encoded_bytes": len(blob),
                })

            patched_units.add(row["id"])
            continue

        # No pointer metadata: conservative fixed-field replacement only.
        source_dec = original[c["stream"]]["decoded"]
        extra = extra_utf16_capacity(
            source_dec,
            c["match_end"],
        )
        capacity_chars = (
            len(c["english"]) + extra
        )

        if len(ko) > capacity_chars:
            skips.append({
                "mdi": mdi_name,
                "unit_id": row["id"],
                "kind": "utf16_fixed",
                "english": c["english"],
                "korean": ko,
                "stream": c["stream"],
                "offset": f"0x{c['offset']:X}",
                "reason":
                    f"Fixed UTF-16 capacity {capacity_chars} < Korean chars {len(ko)}",
            })
            continue

        total_bytes = (
            capacity_chars + 1
        ) * 2

        blob = (
            ko.encode("utf-16le")
            + b"\x00\x00"
        )
        blob += b"\x00" * (
            total_bytes - len(blob)
        )

        dst = mutable[c["stream"]]
        start = c["offset"]
        end = start + total_bytes

        before = bytes(dst[start:end])
        dst[start:end] = blob

        if bytes(dst[start:end]) == before:
            continue

        actions.append({
            "mdi": mdi_name,
            "unit_id": row["id"],
            "kind": "utf16_fixed",
            "english": c["english"],
            "korean": ko,
            "source_stream": c["stream"],
            "source_offset": f"0x{start:X}",
            "source_runtime":
                f"0x{c['runtime']:08X}",
            "metadata_stream": "",
            "metadata_offset": "",
            "old_num": len(c["english"]) + 1,
            "old_max": capacity_chars + 1,
            "new_num": len(ko) + 1,
            "new_max": capacity_chars + 1,
            "alloc_stream": "",
            "alloc_offset": "",
            "alloc_runtime": "",
            "encoded_bytes": len(blob),
        })

        patched_units.add(row["id"])

    # Build replacement map only for streams that actually changed.
    replacements = {}

    for st in original:
        si = st["index"]
        now = bytes(mutable[si])

        if now != st["decoded"]:
            replacements[si] = now

    if replacements:
        patched = b.rebuild_mdi(
            data,
            replacements,
        )

        # Strong decoded read-back verification.
        verify = b.parse_mdi(patched)
        verify_by = {
            st["index"]: st["decoded"]
            for st in verify
        }

        for si, expected in replacements.items():
            if verify_by.get(si) != expected:
                raise RuntimeError(
                    f"{mdi_name}: rebuilt stream {si} mismatch"
                )
    else:
        patched = data

    allocator_report = [
        {
            "stream": r["stream"],
            "start": f"0x{r['start']:X}",
            "end": f"0x{r['end']:X}",
            "used": r["cursor"] - r["start"],
            "capacity": r["capacity"],
        }
        for r in regions
    ]

    return patched, {
        "mdi": mdi_name,
        "stream_count": len(streams),
        "changed": bool(replacements),
        "changed_streams":
            sorted(replacements.keys()),
        "matched_units":
            sorted(matched_units),
        "patched_units":
            sorted(patched_units),
        "actions": actions,
        "skips": skips,
        "allocator": allocator_report,
    }


def list_mdi_names():
    if not SYSTEM_DIR.exists():
        raise RuntimeError(
            f"Missing extracted SYSTEM mirror: {SYSTEM_DIR}"
        )

    names = sorted({
        p.name
        for p in SYSTEM_DIR.glob("*.MDI")
        if p.is_file()
    })

    if not names:
        raise RuntimeError(
            "No *.MDI files found in extracted SYSTEM mirror"
        )

    return names


def build_iso(b, rows, exact, upper_unique):
    if not SOURCE_ISO.exists():
        raise RuntimeError(
            f"Missing successful Stage39U ISO: {SOURCE_ISO}"
        )

    if TEST_ISO.exists():
        TEST_ISO.unlink()

    log("[Stage40B] Copying Stage39U baseline")
    shutil.copy2(SOURCE_ISO, TEST_ISO)

    mdi_names = list_mdi_names()

    all_actions = []
    all_skips = []
    per_mdi = []

    matched_units = set()
    patched_units = set()

    for idx, name in enumerate(mdi_names, 1):
        target = [
            "PSP_GAME",
            "USRDIR",
            "SYSTEM",
            name,
        ]

        try:
            _, original = b.iso_read_file(
                TEST_ISO,
                target,
            )
        except Exception as e:
            per_mdi.append({
                "mdi": name,
                "skipped": True,
                "reason":
                    f"Not readable from ISO: {e}",
            })
            continue

        try:
            patched, info = inspect_mdi(
                b,
                name,
                original,
                exact,
                upper_unique,
            )
        except Exception as e:
            per_mdi.append({
                "mdi": name,
                "skipped": True,
                "reason":
                    f"MDI parse/patch error: {e}",
            })
            continue

        if info["changed"]:
            b.append_iso_file_and_repoint(
                TEST_ISO,
                target,
                patched,
            )

            _, rb = b.iso_read_file(
                TEST_ISO,
                target,
            )

            if rb != patched:
                raise RuntimeError(
                    f"{name}: ISO read-back mismatch"
                )

        all_actions.extend(
            info["actions"]
        )
        all_skips.extend(
            info["skips"]
        )
        matched_units.update(
            info["matched_units"]
        )
        patched_units.update(
            info["patched_units"]
        )

        per_mdi.append({
            "mdi": name,
            "skipped": False,
            "changed": info["changed"],
            "stream_count":
                info["stream_count"],
            "changed_streams":
                info["changed_streams"],
            "matched_unit_count":
                len(info["matched_units"]),
            "patched_unit_count":
                len(info["patched_units"]),
            "action_count":
                len(info["actions"]),
            "skip_count":
                len(info["skips"]),
            "allocator":
                info["allocator"],
        })

        if idx % 5 == 0 or idx == len(mdi_names):
            log(
                f"[Stage40B] MDI {idx}/{len(mdi_names)} "
                f"actions={len(all_actions)} "
                f"units={len(patched_units)}"
            )

    return {
        "mdi_names": mdi_names,
        "per_mdi": per_mdi,
        "actions": all_actions,
        "skips": all_skips,
        "matched_units": matched_units,
        "patched_units": patched_units,
    }


# ---------------------------------------------------------------------------
# Minimal PPSSPP smoke test.
# ---------------------------------------------------------------------------

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


def wait_cpu_ready(ws, timeout=20.0):
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
                UTF16_OPTIONS + b"\x00\x00"
            )
            and pro.startswith(
                UTF16_PROFILE + b"\x00\x00"
            )
            and sto.startswith(
                UTF16_STORY + b"\x00\x00"
            )
        ),
        "options": opt.hex(),
        "profile": pro.hex(),
        "story": sto.hex(),
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


def smoke_test(local_mod, b):
    exe = b.find_ppsspp_exe()

    cfg = OUT / "stage40b_append.ini"
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

    log("[Stage40B] PPSSPP smoke test")
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
                "bytes":
                    read_ws(
                        ws,
                        RENDER_CALL_RUNTIME,
                        4,
                    ).hex(),
                "expected":
                    EXPECTED_RENDER_JAL_RUNTIME.hex(),
            }

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

            result["font"] = {
                "glyph_count": glyph_count,
                "glyph_count_ok":
                    glyph_count == EXPECTED_GLYPH_COUNT,
                "glyph_ptr":
                    f"0x{glyph_ptr:08X}",
                "glyph_ptr_ok":
                    glyph_ptr == EXPECTED_GLYPH_PTR,
            }

            # Startup skipping only until MENUINT0 is opened.
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

            result["menu_resource"] = {
                "opened": opened,
                "startup_start_presses":
                    presses,
            }

            if not opened:
                raise RuntimeError(
                    "MENUINT0.RAW did not open"
                )

            # Stage39R/U reliable title timing.
            time.sleep(2.5)

            confirmed = False
            attempts = []

            for attempt in (1, 2):
                a = menu_anchors(ws)

                if a.get("ok"):
                    confirmed = True
                    break

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
                        confirmed = True
                        break

                    if (
                        attempt == 1
                        and time.time()-start >= 8
                    ):
                        break

                    time.sleep(0.12)

                attempts.append({
                    "attempt": attempt,
                    "sent": sent,
                    "error":
                        None if sent else err,
                    "anchors": a,
                })

                if confirmed:
                    break

            result["main_menu"] = {
                "confirmed": confirmed,
                "attempts": attempts,
                "anchors": menu_anchors(ws),
            }

            if confirmed:
                time.sleep(0.75)
                result["screenshot"] = capture(
                    local_mod,
                    b,
                    hwnd,
                )

            result["ok"] = (
                result["renderer_jal"]["bytes"]
                == result["renderer_jal"]["expected"]
                and result["font"]["glyph_count_ok"]
                and result["font"]["glyph_ptr_ok"]
                and confirmed
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


def write_tables(actions, skips, rows, coverage):
    action_fields = [
        "mdi",
        "unit_id",
        "kind",
        "english",
        "korean",
        "source_stream",
        "source_offset",
        "source_runtime",
        "metadata_stream",
        "metadata_offset",
        "old_num",
        "old_max",
        "new_num",
        "new_max",
        "alloc_stream",
        "alloc_offset",
        "alloc_runtime",
        "encoded_bytes",
    ]

    with PATCH_TSV.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as f:
        w = csv.DictWriter(
            f,
            fieldnames=action_fields,
            delimiter="\t",
            extrasaction="ignore",
        )
        w.writeheader()

        for x in actions:
            w.writerow(x)

    skip_fields = [
        "mdi",
        "unit_id",
        "kind",
        "english",
        "korean",
        "stream",
        "offset",
        "reason",
    ]

    with SKIP_TSV.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as f:
        w = csv.DictWriter(
            f,
            fieldnames=skip_fields,
            delimiter="\t",
            extrasaction="ignore",
        )
        w.writeheader()

        for x in skips:
            w.writerow(x)

    with UNIT_TSV.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as f:
        fields = [
            "id",
            "priority",
            "category",
            "English",
            "한국어",
            "status",
            "action_count",
            "mdi_files",
        ]
        w = csv.DictWriter(
            f,
            fieldnames=fields,
            delimiter="\t",
        )
        w.writeheader()

        for row in rows:
            c = coverage[row["id"]]
            w.writerow({
                "id": row["id"],
                "priority": row["priority"],
                "category": row["category"],
                "English": row["English"],
                "한국어": row["한국어"],
                "status": c["status"],
                "action_count": c["action_count"],
                "mdi_files":
                    " | ".join(c["mdi_files"]),
            })


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

        # Keep the exact translation corpus with the result.
        z.write(
            CORPUS_PATH,
            "stage39a_A_translations.tsv",
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

    rows, exact, upper_unique, upper_conflicts, hangul = load_corpus()
    local_mod, b = load_helpers()

    report = {
        "stage": "40B",
        "purpose":
            "High-confidence A-priority mass insertion across compiled MDI "
            "assets, preserving the Stage39U renderer/font baseline.",
        "source_iso": str(SOURCE_ISO),
        "test_iso": str(TEST_ISO),
        "translation_units": len(rows),
        "unique_hangul": len(hangul),
        "uppercase_conflict_count":
            len(upper_conflicts),
        "strategy": {
            "narrow":
                "Exact-case English source + matching ptr/Num/Max metadata -> "
                "relocate Korean UTF-8 into trailing-zero stream padding and "
                "repoint metadata. Original source/key bytes remain untouched.",
            "utf16":
                "Unique case-insensitive English match. If ptr/Num/Max metadata "
                "exists, relocate proper Korean UTF-16. Otherwise patch only "
                "when the original field plus adjacent UTF-16 NUL padding fits.",
            "allocator":
                "Only trailing all-zero padding inside existing decoded MDI "
                "stream lengths; no stream growth and no overwrite of nonzero data.",
        },
    }

    try:
        build = build_iso(
            b,
            rows,
            exact,
            upper_unique,
        )

        report["mdi_files_scanned"] = len(
            build["mdi_names"]
        )
        report["per_mdi"] = build["per_mdi"]

        actions = build["actions"]
        skips = build["skips"]

        action_by_unit = defaultdict(list)

        for a in actions:
            action_by_unit[a["unit_id"]].append(a)

        matched_units = set(
            build["matched_units"]
        )
        patched_units = set(
            build["patched_units"]
        )

        coverage = {}

        for row in rows:
            uid = row["id"]
            aa = action_by_unit.get(uid, [])

            if uid in patched_units:
                status = "patched"
            elif uid in matched_units:
                status = "matched_but_skipped"
            else:
                status = "not_found_in_scanned_mdi"

            coverage[uid] = {
                "status": status,
                "action_count": len(aa),
                "mdi_files": sorted({
                    x["mdi"] for x in aa
                }),
            }

        write_tables(
            actions,
            skips,
            rows,
            coverage,
        )

        report["mass_patch"] = {
            "action_count": len(actions),
            "patched_unit_count":
                len(patched_units),
            "matched_unit_count":
                len(matched_units),
            "matched_but_skipped_unit_count":
                len(
                    matched_units
                    - patched_units
                ),
            "not_found_unit_count":
                len(rows)
                - len(matched_units),
            "changed_mdi_count":
                sum(
                    1
                    for x in build["per_mdi"]
                    if x.get("changed")
                ),
            "action_kinds": {
                kind: sum(
                    1
                    for x in actions
                    if x["kind"] == kind
                )
                for kind in sorted({
                    x["kind"]
                    for x in actions
                })
            },
            "skip_count": len(skips),
        }

        # Smoke-test only after all ISO read-back validations passed.
        smoke = smoke_test(
            local_mod,
            b,
        )
        report["smoke_test"] = smoke

        report["completed"] = bool(
            smoke.get("ok", False)
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
            f"Stage40B failed. See {FAIL_ZIP}"
        )

    log("[Stage40B] COMPLETE")
    log(
        f"[Stage40B] Patched ISO: {TEST_ISO}"
    )
    log(
        f"[Stage40B] Upload ZIP: {SUCCESS_ZIP}"
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
            f"STAGE 40B FAILED: {FAIL_ZIP}",
            flush=True,
        )
        raise SystemExit(1)
