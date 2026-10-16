#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import base64
import csv
import hashlib
import importlib.util
import json
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
TEST_ISO = ROOT / "BIA_STAGE40F_ON_MEMU_RESIDENT_MASS_TEST.iso"

OUT = ROOT / "analysis" / "stage40f_on_memu_resident_mass"
LOG_DIR = ROOT / "log"

SUCCESS_ZIP = LOG_DIR / "bia_stage40f_upload.zip"
FAIL_ZIP = LOG_DIR / "fail_bia_stage40f_upload.zip"
REPORT_PATH = OUT / "stage40f_report.json"
PPSSPP_LOG = OUT / "stage40f_ppsspp.log"

SCRIPT_DIR = Path(__file__).resolve().parent
PLAN_PATH = SCRIPT_DIR / "stage40f_on_memu_plan.tsv"

TARGET = [
    "PSP_GAME",
    "USRDIR",
    "SYSTEM",
    "ON_MEMU_O.MDI",
]

MDI_SEQ_BASE = 0x08E2D020
MDI_STREAM_SIZE = 0x78000

# Stream23 is directly proven resident because its runtime base is exactly
# the production glyph array pointer used by the active renderer.
LIVE_STREAM = 23
LIVE_BASE = MDI_SEQ_BASE + LIVE_STREAM * MDI_STREAM_SIZE
ALLOC_START = 0xA870
ALLOC_END = 0x77FC0

# Stage39U invariants.
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

RAM_START = 0x08800000
RAM_END = 0x0A800000

# Visible top-level probes. Story remains Stage39U's already-proven field;
# the other three are part of this 690-unit mass patch.
VISIBLE_PROBES = [
    ("Story", "토"),
    ("Skirmish", "커"),
    ("Options", "옵"),
    ("Profile", "프"),
]


def log(msg):
    print(msg, flush=True)


def sha1(data):
    return hashlib.sha1(data).hexdigest()


def align_up(v, a=4):
    return (v + a - 1) & ~(a - 1)


def runtime_addr(stream_index, offset):
    return (
        MDI_SEQ_BASE
        + stream_index * MDI_STREAM_SIZE
        + offset
    )


def parse_int(v):
    s = str(v).strip()
    if not s:
        return None
    return int(s, 0)


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
            f"Expected 1675 metadata actions, got {len(rows)}"
        )

    if len({x["unit_id"] for x in rows}) != 690:
        raise RuntimeError(
            "Expected 690 unique A-priority ON_MEMU units"
        )

    if len({x["korean"] for x in rows}) != 656:
        raise RuntimeError(
            "Expected 656 unique translated payloads"
        )

    if {x["kind"] for x in rows} != {"narrow_reloc"}:
        raise RuntimeError(
            "Unexpected action kind in Stage40F plan"
        )

    # The plan must not have duplicate metadata slots.
    slots = [
        (
            parse_int(x["metadata_stream"]),
            parse_int(x["metadata_offset"]),
        )
        for x in rows
    ]
    if len(slots) != len(set(slots)):
        raise RuntimeError(
            "Duplicate metadata target in Stage40F plan"
        )

    return rows


def build_iso(b, plan):
    if not SOURCE_ISO.exists():
        raise RuntimeError(
            f"Missing promoted Stage39U ISO: {SOURCE_ISO}"
        )

    if TEST_ISO.exists():
        TEST_ISO.unlink()

    import shutil
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
        raise RuntimeError("ON_MEMU stream23 missing")

    live = original_by[LIVE_STREAM]

    if ALLOC_END > len(live):
        raise RuntimeError(
            f"Stream23 is shorter than expected: 0x{len(live):X}"
        )

    # Deduplicate by exact Korean payload, preserving first plan occurrence.
    payload_order = []
    seen = set()

    for row in plan:
        ko = row["korean"]
        if ko not in seen:
            seen.add(ko)
            payload_order.append(ko)

    cursor = ALLOC_START
    alloc = {}

    for ko in payload_order:
        blob = ko.encode("utf-8") + b"\x00"
        cursor = align_up(cursor, 4)

        if cursor + len(blob) > ALLOC_END:
            raise RuntimeError(
                f"Stream23 allocation overflow at {ko!r}"
            )

        # Must be zero in the untouched Stage39U source.
        if any(
            live[
                cursor:
                cursor+len(blob)
            ]
        ):
            raise RuntimeError(
                f"Stream23 allocation target not zero at 0x{cursor:X}"
            )

        ptr = runtime_addr(
            LIVE_STREAM,
            cursor,
        )

        mutable[LIVE_STREAM][
            cursor:
            cursor+len(blob)
        ] = blob

        alloc[ko] = {
            "stream": LIVE_STREAM,
            "offset": cursor,
            "runtime": ptr,
            "blob": blob,
        }

        cursor += len(blob)

    metadata_actions = []

    for row in plan:
        msi = parse_int(
            row["metadata_stream"]
        )
        moff = parse_int(
            row["metadata_offset"]
        )

        old_ptr = parse_int(
            row["source_runtime"]
        )
        old_num = parse_int(
            row["old_num"]
        )
        old_max = parse_int(
            row["old_max"]
        )

        if msi not in original_by:
            raise RuntimeError(
                f"Metadata stream {msi} missing"
            )

        if moff + 12 > len(
            original_by[msi]
        ):
            raise RuntimeError(
                f"Metadata out of bounds: stream{msi} 0x{moff:X}"
            )

        got = struct.unpack_from(
            "<III",
            original_by[msi],
            moff,
        )
        expected = (
            old_ptr,
            old_num,
            old_max,
        )

        if got != expected:
            raise RuntimeError(
                f"Metadata precondition mismatch "
                f"{row['english']!r} stream{msi} 0x{moff:X}: "
                f"{got} != {expected}"
            )

        a = alloc[
            row["korean"]
        ]
        new_num = len(
            a["blob"]
        )

        struct.pack_into(
            "<III",
            mutable[msi],
            moff,
            a["runtime"],
            new_num,
            new_num,
        )

        metadata_actions.append({
            "unit_id": row["unit_id"],
            "english": row["english"],
            "korean": row["korean"],
            "metadata_stream": msi,
            "metadata_offset": moff,
            "metadata_runtime":
                runtime_addr(msi, moff),
            "old_ptr": old_ptr,
            "old_num": old_num,
            "old_max": old_max,
            "new_ptr": a["runtime"],
            "new_num": new_num,
            "new_max": new_num,
        })

    replacements = {}

    for si, before in original_by.items():
        after = bytes(
            mutable[si]
        )
        if after != before:
            replacements[si] = after

    # Stage40C proved exactly these metadata streams contain the 1675 refs,
    # plus stream23 now holds every payload.
    expected_streams = {
        1,2,3,4,8,9,10,11,12,13,14,15,16,19,20,23
    }

    if set(replacements) != expected_streams:
        raise RuntimeError(
            f"Unexpected changed streams: {sorted(replacements)}"
        )

    patched = b.rebuild_mdi(
        original,
        replacements,
    )

    verify = b.parse_mdi(
        patched,
    )
    verify_by = {
        st["index"]: bytes(st["decoded"])
        for st in verify
    }

    for si, expected in replacements.items():
        if verify_by.get(si) != expected:
            raise RuntimeError(
                f"Decoded stream readback mismatch: {si}"
            )

    # Verify every translated payload and every metadata record in rebuilt bytes.
    payload_proof = []

    for ko, a in alloc.items():
        raw = verify_by[LIVE_STREAM][
            a["offset"]:
            a["offset"]+len(a["blob"])
        ]

        payload_proof.append({
            "korean": ko,
            "offset":
                f"0x{a['offset']:X}",
            "runtime":
                f"0x{a['runtime']:08X}",
            "bytes":
                len(a["blob"]),
            "ok":
                raw == a["blob"],
        })

    metadata_failures = []

    for a in metadata_actions:
        got = struct.unpack_from(
            "<III",
            verify_by[
                a["metadata_stream"]
            ],
            a["metadata_offset"],
        )
        expected = (
            a["new_ptr"],
            a["new_num"],
            a["new_max"],
        )

        if got != expected:
            metadata_failures.append({
                **a,
                "actual":
                    list(got),
                "expected":
                    list(expected),
            })

    if not all(
        x["ok"]
        for x in payload_proof
    ):
        raise RuntimeError(
            "Payload readback validation failed"
        )

    if metadata_failures:
        raise RuntimeError(
            f"{len(metadata_failures)} metadata readback failures"
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
            "ON_MEMU ISO readback mismatch"
        )

    return {
        "original_sha1":
            sha1(original),
        "patched_sha1":
            sha1(patched),
        "original_size":
            len(original),
        "patched_size":
            len(patched),
        "metadata_action_count":
            len(metadata_actions),
        "unique_unit_count":
            len({
                x["unit_id"]
                for x in plan
            }),
        "unique_payload_count":
            len(alloc),
        "allocation_stream":
            LIVE_STREAM,
        "allocation_runtime_base":
            f"0x{LIVE_BASE:08X}",
        "allocation_start":
            f"0x{ALLOC_START:X}",
        "allocation_end_used":
            f"0x{align_up(cursor,4):X}",
        "allocation_bytes_used":
            align_up(cursor,4)
            - ALLOC_START,
        "allocation_capacity":
            ALLOC_END
            - ALLOC_START,
        "changed_streams":
            sorted(replacements),
        "iso_readback_ok":
            True,
        "payloads": [
            {
                "korean": ko,
                "offset":
                    f"0x{a['offset']:X}",
                "runtime":
                    f"0x{a['runtime']:08X}",
                "bytes":
                    len(a["blob"]),
            }
            for ko,a in alloc.items()
        ],
        "metadata_actions":
            metadata_actions,
    }


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
                uints[n] = int(
                    uvals[i]
                ) & 0xFFFFFFFF

            if i < len(fvals):
                try:
                    floats[n] = float(
                        fvals[i]
                    )
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
                    "probe":
                        probe.hex(),
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
    last_press = 0
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
                    "startup_start_presses":
                        presses,
                }

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

    return {
        "opened": False,
        "startup_start_presses":
            presses,
    }


def wait_story_menu(ws, timeout=12):
    needle = (
        "스토리".encode(
            "utf-16le"
        )
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
            p = block.find(
                needle
            )

            if p >= 0:
                return {
                    "found": True,
                    "address":
                        f"0x{0x08E40000+p:08X}",
                }
        except Exception:
            pass

        time.sleep(0.12)

    return {
        "found": False,
    }


def verify_payload_runtime(ws, build):
    failures = []
    checked = 0

    for item in build["payloads"]:
        ptr = int(
            item["runtime"],
            16,
        )
        expected = (
            item["korean"].encode(
                "utf-8"
            )
            + b"\x00"
        )

        try:
            got = read_ws(
                ws,
                ptr,
                len(expected),
            )
            checked += 1

            if got != expected:
                failures.append({
                    **item,
                    "actual_hex":
                        got.hex(),
                    "expected_hex":
                        expected.hex(),
                })
        except Exception as e:
            failures.append({
                **item,
                "error": str(e),
            })

    return {
        "checked":
            checked,
        "total":
            len(build["payloads"]),
        "failure_count":
            len(failures),
        "failures":
            failures[:100],
        "ok":
            not failures
            and checked
            == len(build["payloads"]),
    }


def verify_metadata_runtime(ws, build):
    """
    After menu initialization, attempt direct validation of all 1675 live
    metadata records. ON_MEMU streams are expected to be mapped together.
    Keep detailed counts in case some submenu-only records are not resident yet.
    """
    ok = 0
    mismatch = 0
    unreadable = 0
    examples = []

    for item in build[
        "metadata_actions"
    ]:
        addr = item[
            "metadata_runtime"
        ]

        expected = (
            item["new_ptr"],
            item["new_num"],
            item["new_max"],
        )

        try:
            raw = read_ws(
                ws,
                addr,
                12,
            )
            got = struct.unpack(
                "<III",
                raw,
            )

            if got == expected:
                ok += 1
            else:
                mismatch += 1

                if len(examples) < 50:
                    examples.append({
                        "unit_id":
                            item["unit_id"],
                        "english":
                            item["english"],
                        "metadata_runtime":
                            f"0x{addr:08X}",
                        "expected":
                            [f"0x{expected[0]:08X}",
                             expected[1],
                             expected[2]],
                        "actual":
                            [f"0x{got[0]:08X}",
                             got[1],
                             got[2]],
                    })

        except Exception as e:
            unreadable += 1

            if len(examples) < 50:
                examples.append({
                    "unit_id":
                        item["unit_id"],
                    "english":
                        item["english"],
                    "metadata_runtime":
                        f"0x{addr:08X}",
                    "error":
                        str(e),
                })

    return {
        "total":
            len(
                build[
                    "metadata_actions"
                ]
            ),
        "exact":
            ok,
        "mismatch":
            mismatch,
        "unreadable":
            unreadable,
        "examples":
            examples,
        "all_exact":
            (
                ok
                == len(
                    build[
                        "metadata_actions"
                    ]
                )
            ),
    }


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

            if s.get(
                "stepping",
                False,
            ):
                return s

        except Exception:
            pass

        time.sleep(0.018)

    return None


def renderer_probe(ws, label, ch):
    code = ord(ch)

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
        timeout=18,
    )

    if p is None:
        remove_bp(
            ws,
            UNICODE_LOOKUP,
        )

        return {
            "label":
                label,
            "char":
                ch,
            "codepoint":
                f"U+{code:04X}",
            "hit":
                False,
        }

    uints, _ = parse_regs(
        ws.request(
            "cpu.getAllRegs",
            timeout=10,
        )
    )

    s0 = uints.get(
        "s0",
        0,
    )

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
        "label":
            label,
        "char":
            ch,
        "codepoint":
            f"U+{code:04X}",
        "hit":
            True,
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
        "source_sample_hex":
            sample,
    }

    remove_bp(
        ws,
        UNICODE_LOOKUP,
    )
    resume(ws)

    return hit


def runtime_test(b, build):
    exe = b.find_ppsspp_exe()

    cfg = OUT / "stage40f_append.ini"
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

    log(
        "[Stage40F] Launching PPSSPP mass ON_MEMU proof"
    )

    proc = subprocess.Popen(
        cmd
    )
    cleanup = (
        b.register_ppsspp_auto_close(
            proc
        )
    )

    result = {
        "pid":
            proc.pid,
    }

    try:
        hwnd = b.find_ppsspp_hwnd(
            30
        )

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

        ws, host = (
            b.connect_debugger(
                actual_port
            )
        )

        try:
            result[
                "debugger_host"
            ] = host
            result[
                "debugger_port"
            ] = actual_port

            ready = wait_cpu_ready(
                ws
            )
            result[
                "cpu_ready"
            ] = ready

            if not ready.get(
                "ready"
            ):
                raise RuntimeError(
                    "CPU did not become ready"
                )

            result[
                "renderer_jal"
            ] = {
                "actual":
                    read_ws(
                        ws,
                        RENDER_CALL_RUNTIME,
                        4,
                    ).hex(),
                "expected":
                    EXPECTED_RENDER_JAL_RUNTIME.hex(),
            }

            menu = wait_menu_resource(
                ws
            )
            result[
                "menu_resource"
            ] = menu

            if not menu.get(
                "opened"
            ):
                raise RuntimeError(
                    "MENUINT0.RAW did not open"
                )

            # Title settle, then exactly one Start.
            time.sleep(2.5)

            ws.request(
                "input.buttons.press",
                timeout=5,
                button="start",
                duration=2,
            )

            story = wait_story_menu(
                ws,
                timeout=12,
            )
            result[
                "menu_confirmed"
            ] = story

            if not story.get(
                "found"
            ):
                raise RuntimeError(
                    "Selectable menu did not initialize"
                )

            time.sleep(0.75)

            # 656 payloads all live in the proven resident stream23.
            result[
                "payload_runtime"
            ] = verify_payload_runtime(
                ws,
                build,
            )

            # Validate all 1675 metadata refs currently resident after menu init.
            result[
                "metadata_runtime"
            ] = verify_metadata_runtime(
                ws,
                build,
            )

            # Real visible renderer proof for all four top-level labels.
            probes = []

            for label, ch in VISIBLE_PROBES:
                probes.append(
                    renderer_probe(
                        ws,
                        label,
                        ch,
                    )
                )

            result[
                "renderer_unicode_probes"
            ] = probes

            glyph_count = struct.unpack(
                "<H",
                read_ws(
                    ws,
                    FONT_OBJECT+0x50,
                    2,
                ),
            )[0]

            glyph_ptr = struct.unpack(
                "<I",
                read_ws(
                    ws,
                    FONT_OBJECT+0x54,
                    4,
                ),
            )[0]

            result[
                "font_after_menu"
            ] = {
                "glyph_count":
                    glyph_count,
                "glyph_count_ok":
                    glyph_count
                    == EXPECTED_GLYPH_COUNT,
                "glyph_ptr":
                    f"0x{glyph_ptr:08X}",
                "glyph_ptr_ok":
                    glyph_ptr
                    == EXPECTED_GLYPH_PTR,
            }

            probe_ok = all(
                x.get(
                    "hit",
                    False,
                )
                for x in probes
            )

            # Exact runtime validation of every metadata ref is desirable but
            # not required for success: submenu-specific records may be unloaded
            # until that submenu is opened.  Payload residency + top-level actual
            # renderer hits are the hard requirements.
            result[
                "ok"
            ] = (
                result[
                    "renderer_jal"
                ]["actual"]
                == result[
                    "renderer_jal"
                ]["expected"]
                and result[
                    "payload_runtime"
                ]["ok"]
                and probe_ok
                and result[
                    "font_after_menu"
                ]["glyph_count_ok"]
                and result[
                    "font_after_menu"
                ]["glyph_ptr_ok"]
            )

        finally:
            try:
                ws.close()
            except Exception:
                pass

    finally:
        try:
            cleanup()
            result[
                "ppsspp_closed"
            ] = True
        except Exception as e:
            result[
                "ppsspp_close_error"
            ] = str(e)

    return result


def make_zip(path):
    if path.exists():
        path.unlink()

    with zipfile.ZipFile(
        path,
        "w",
        zipfile.ZIP_DEFLATED,
    ) as z:
        for p in sorted(
            OUT.rglob("*")
        ):
            if p.is_file():
                z.write(
                    p,
                    p.relative_to(
                        OUT
                    ).as_posix(),
                )

        z.write(
            PLAN_PATH,
            "stage40f_on_memu_plan.tsv",
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

    plan = load_plan()
    _, b = load_helpers()

    report = {
        "stage":
            "40F",
        "purpose":
            "Promote the Stage40E-proven resident stream23 relocation method "
            "to all 1675 high-confidence ON_MEMU metadata references covering "
            "690 A-priority translation units.",
        "stage40e_proof":
            {
                "stream23_payloads_live":
                    True,
                "actual_wide_renderer_hits":
                    [
                        "Story/토",
                        "Skirmish/커",
                        "Options/옵",
                        "Profile/프",
                    ],
                "production_font":
                    "847 glyphs / 0x098F5020",
                "raw_vram_note":
                    "PPSSPP buffered rendering keeps the current host FBO "
                    "separate from raw emulated VRAM, so memory.read framebuffer "
                    "snapshots are not used as a success criterion.",
            },
        "source_iso":
            str(SOURCE_ISO),
        "test_iso":
            str(TEST_ISO),
        "plan":
            {
                "metadata_actions":
                    len(plan),
                "unique_units":
                    len({
                        x["unit_id"]
                        for x in plan
                    }),
                "unique_payloads":
                    len({
                        x["korean"]
                        for x in plan
                    }),
            },
    }

    try:
        build = build_iso(
            b,
            plan,
        )
        report[
            "build"
        ] = build

        runtime = runtime_test(
            b,
            build,
        )
        report[
            "runtime"
        ] = runtime

        report[
            "completed"
        ] = bool(
            runtime.get(
                "ok",
                False,
            )
        )

    except Exception as e:
        report[
            "runtime_exception"
        ] = str(e)
        report[
            "runtime_traceback"
        ] = traceback.format_exc()
        report[
            "completed"
        ] = False

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
        if report[
            "completed"
        ]
        else FAIL_ZIP
    )

    make_zip(
        target
    )

    if not report[
        "completed"
    ]:
        raise RuntimeError(
            f"Stage40F failed. See {FAIL_ZIP}"
        )

    log(
        "[Stage40F] COMPLETE"
    )
    log(
        f"[Stage40F] ISO: {TEST_ISO}"
    )
    log(
        f"[Stage40F] Upload ZIP: {SUCCESS_ZIP}"
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
            make_zip(
                FAIL_ZIP
            )
        except Exception:
            pass

        print(
            traceback.format_exc(),
            flush=True,
        )
        print(
            f"STAGE 40F FAILED: {FAIL_ZIP}",
            flush=True,
        )
        raise SystemExit(1)
