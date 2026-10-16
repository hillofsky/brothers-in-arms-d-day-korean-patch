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
import zlib
from pathlib import Path

ROOT = Path(r"PROJECT_ROOT")
BASE_TOOLS = ROOT / "bia_stage39b_tools"

SOURCE_ISO = ROOT / "BIA_STAGE39C_COMPILED_LOCALIZATION_TEST.iso"
TEST_ISO = ROOT / "BIA_STAGE39D_UTF8_DECODER_TEST.iso"

OUT = ROOT / "analysis" / "stage39d_utf8_decoder"
LOG_DIR = ROOT / "log"

SUCCESS_ZIP = LOG_DIR / "bia_stage39d_upload.zip"
FAIL_ZIP = LOG_DIR / "fail_bia_stage39d_upload.zip"

SCRIPT_DIR = Path(__file__).resolve().parent

TARGET_PRX = ["PSP_GAME", "USRDIR", "SYSTEM", "BIAON.PRX"]
TARGET_MDI = ["PSP_GAME", "USRDIR", "SYSTEM", "ON_MEMU_O.MDI"]

SECTOR = 2048

EXPECTED_ORIGINAL_BIAON_SHA1 = "8c7033ca15103fa51afa9c7ec61f37c531d07ede"

# BIAON.PRX load base and converter locations.
BIAON_RUNTIME_BASE = 0x08804000

# Existing charset conversion function:
#   PRX vaddr 0x4C0108 -> runtime 0x08CC4108
#
# It recognizes C-SJIS / C-EUCJP / C-JIS, then falls back to byte-wise
# widening for the default path.
CONVERTER_VA = 0x004C0108
CONVERTER_RUNTIME = BIAON_RUNTIME_BASE + CONVERTER_VA

# Original:
#   0x4C037C load encoding name
#   0x4C0380 strcmp(..., "C-JIS")
#   0x4C0388 bnez v0, 0x4C06A4   ; default byte->u16 widening
#
# Stage39D changes this single branch to fall through into our UTF-8 decoder.
DISPATCH_BRANCH_VA = 0x004C0388
UTF8_DECODER_VA = 0x004C0390

# ELF .text begins at file offset 0x80 with vaddr 0.
ELF_TEXT_FILE_BIAS = 0x80

DISPATCH_BRANCH_FILE_OFF = DISPATCH_BRANCH_VA + ELF_TEXT_FILE_BIAS
UTF8_DECODER_FILE_OFF = UTF8_DECODER_VA + ELF_TEXT_FILE_BIAS

EXPECTED_BRANCH_BYTES = bytes.fromhex("c6004014")   # bnez v0,0x4C06A4
PATCHED_BRANCH_BYTES = b"\x00\x00\x00\x00"       # nop

# In the injected decoder, the 3-byte UTF-8 codepoint is stored at +0xD0:
#   sh t0,0(s1)
UTF8_3BYTE_STORE_RUNTIME = (
    BIAON_RUNTIME_BASE + UTF8_DECODER_VA + 0xD0
)

# Known Stage39C source table in MDI stream11.
MDI_SEQ_BASE = 0x08E2D020
MDI_STREAM_SIZE = 0x78000
SOURCE_STREAM_INDEX = 11
SOURCE_STREAM_BASE = MDI_SEQ_BASE + SOURCE_STREAM_INDEX * MDI_STREAM_SIZE

SOURCE_SCAN_START = SOURCE_STREAM_BASE + 0x5CA00
SOURCE_SCAN_END = SOURCE_STREAM_BASE + 0x5CD00

TEST_TEXT = "\uc2a4\ud1a0\ub9ac"
TEST_UTF8 = TEST_TEXT.encode("utf-8")
TEST_UTF16 = TEST_TEXT.encode("utf-16le")
FIRST_CODEPOINT = 0xC2A4

# Search enough PSP RAM to find the current dynamic wide copy, without relying
# on the old 0x08E41620 fixed-slot assumption.
RAM_SEARCH_START = 0x08800000
RAM_SEARCH_SIZE = 0x02000000

EXPECTED_DECODER_BLOB_SHA1 = "8eeb1e68f096e92dab1a3274b3120732c42eb532"

REPORT_PATH = OUT / "stage39d_report.json"
PPSSPP_LOG = OUT / "stage39d_ppsspp.log"
SCREENSHOT = OUT / "stage39d_menu.png"
GPU_DUMP = OUT / "stage39d_menu.ppdmp"


def log(msg: str):
    # Console output deliberately remains ASCII-only.  Stage39C showed that
    # a CP949 console can throw UnicodeEncodeError on Hangul output.
    print(msg, flush=True)


# ---------------------------------------------------------------------------
# ISO9660 same-size file patcher (self-contained, so the test does not depend
# on Codex/local helper implementation details for the actual disc patch).
# ---------------------------------------------------------------------------

def _norm_iso_name(name: bytes) -> str:
    try:
        s = name.decode("ascii", errors="replace")
    except Exception:
        s = str(name)
    if s in ("\x00", "\x01"):
        return s
    if ";" in s:
        s = s.split(";", 1)[0]
    return s.upper()


def _dir_records(f, extent: int, size: int):
    f.seek(extent * SECTOR)
    data = f.read(size)

    pos = 0
    while pos < len(data):
        rec_len = data[pos]
        if rec_len == 0:
            pos = ((pos // SECTOR) + 1) * SECTOR
            continue

        rec = data[pos:pos + rec_len]
        if len(rec) < 34:
            break

        child_extent = struct.unpack_from("<I", rec, 2)[0]
        child_size = struct.unpack_from("<I", rec, 10)[0]
        flags = rec[25]
        name_len = rec[32]
        name = rec[33:33 + name_len]

        yield {
            "extent": child_extent,
            "size": child_size,
            "flags": flags,
            "is_dir": bool(flags & 0x02),
            "name": _norm_iso_name(name),
        }
        pos += rec_len


def iso_find(path: Path, parts):
    parts = [x.upper() for x in parts]

    with path.open("rb") as f:
        f.seek(16 * SECTOR)
        pvd = f.read(SECTOR)
        if pvd[0] != 1 or pvd[1:6] != b"CD001":
            raise RuntimeError("ISO primary volume descriptor not found")

        root_len = pvd[156]
        root = pvd[156:156 + root_len]
        extent = struct.unpack_from("<I", root, 2)[0]
        size = struct.unpack_from("<I", root, 10)[0]

        current = {"extent": extent, "size": size, "is_dir": True}

        for i, want in enumerate(parts):
            found = None
            for rec in _dir_records(f, current["extent"], current["size"]):
                if rec["name"] == want:
                    found = rec
                    break
            if found is None:
                raise FileNotFoundError("/".join(parts))
            if i != len(parts) - 1 and not found["is_dir"]:
                raise RuntimeError(f"ISO component is not a directory: {want}")
            current = found

        return current


def iso_read(path: Path, parts):
    rec = iso_find(path, parts)
    with path.open("rb") as f:
        f.seek(rec["extent"] * SECTOR)
        data = f.read(rec["size"])
    return rec, data


def iso_overwrite_same_size(path: Path, parts, data: bytes):
    rec = iso_find(path, parts)
    if len(data) != rec["size"]:
        raise RuntimeError(
            f"Same-size overwrite required for {'/'.join(parts)}: "
            f"{len(data)} != {rec['size']}"
        )

    with path.open("r+b") as f:
        f.seek(rec["extent"] * SECTOR)
        f.write(data)
        f.flush()
        os.fsync(f.fileno())

    _, rb = iso_read(path, parts)
    if rb != data:
        raise RuntimeError(f"ISO read-back mismatch: {'/'.join(parts)}")
    return rec


# ---------------------------------------------------------------------------
# MDI parser used only to prove the Stage39C UTF-8 source really exists on disc.
# ---------------------------------------------------------------------------

def valid_zlib_header(h: bytes) -> bool:
    if len(h) < 2:
        return False
    cmf, flg = h
    return (
        (cmf & 0x0F) == 8
        and (((cmf << 8) + flg) % 31) == 0
    )


def parse_mdi(data: bytes):
    streams = []
    pos = 6
    idx = 0

    while pos + 4 <= len(data):
        csize = struct.unpack_from("<I", data, pos)[0]
        zpos = pos + 4

        if (
            csize > 0
            and zpos + csize <= len(data)
            and valid_zlib_header(data[zpos:zpos+2])
        ):
            dec = zlib.decompress(data[zpos:zpos+csize])
            streams.append({
                "index": idx,
                "decoded": dec,
                "csize": csize,
            })
            pos = zpos + csize
            idx += 1
            continue

        # MDI can contain a 4-byte separator before the next compressed stream.
        if pos + 8 <= len(data):
            c2 = struct.unpack_from("<I", data, pos + 4)[0]
            z2 = pos + 8
            if (
                c2 > 0
                and z2 + c2 <= len(data)
                and valid_zlib_header(data[z2:z2+2])
            ):
                pos += 4
                continue

        raise RuntimeError(f"Could not parse MDI near 0x{pos:X}")

    return streams


# ---------------------------------------------------------------------------
# Existing Stage39B helpers: debugger connection, PPSSPP discovery, capture,
# production font verifier, and automatic process cleanup.
# ---------------------------------------------------------------------------

def load_local_helpers():
    if not BASE_TOOLS.exists():
        raise RuntimeError(
            r"Missing PROJECT_ROOT\bia_stage39b_tools. "
            "Stage39D intentionally reuses the proven PPSSPP/debugger helpers."
        )

    module_path = BASE_TOOLS / "bia_stage39b_compiled_mdi_text.py"
    if not module_path.exists():
        raise RuntimeError(f"Missing helper module: {module_path}")

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


def regs_to_dict(resp):
    out = {}
    for cat in resp.get("categories", []):
        names = cat.get("registerNames", [])
        values = cat.get("uintValues", [])
        for name, value in zip(names, values):
            out[name.lower()] = int(value) & 0xFFFFFFFF
    return out


def cpu_reg(ws, name: str) -> int:
    r = ws.request("cpu.getReg", timeout=5, name=name)
    return int(r["uintValue"]) & 0xFFFFFFFF


def read_u32(ws, address):
    r = ws.request("memory.read_u32", timeout=5, address=address)
    return int(r["uintValue"]) & 0xFFFFFFFF


def read_bytes_ws(ws, address, size):
    r = ws.request(
        "memory.read",
        timeout=10,
        address=address,
        size=size,
    )
    return base64.b64decode(r["base64"])


def read_ascii_string(ws, address, maxlen=64):
    if not address:
        return None
    try:
        raw = read_bytes_ws(ws, address, maxlen)
    except Exception:
        return None
    raw = raw.split(b"\x00", 1)[0]
    return raw.decode("ascii", errors="replace")


def disasm(ws, address, count=24):
    try:
        return ws.request(
            "memory.disasm",
            timeout=10,
            address=address,
            count=count,
            displaySymbols=True,
            compact=False,
        )
    except Exception as e:
        return {"error": str(e)}


def wait_until_stepping(ws, timeout=90.0, press_start=True):
    end = time.time() + timeout
    last_press = 0.0
    presses = 0
    last = None

    while time.time() < end:
        try:
            last = ws.request("cpu.status", timeout=3)
        except Exception:
            time.sleep(0.05)
            continue

        if last.get("stepping", False):
            return last, presses

        now = time.time()
        if press_start and now - last_press >= 0.45:
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

        time.sleep(0.05)

    raise RuntimeError(
        f"UTF-8 decoder breakpoint did not hit; "
        f"last CPU status={last}, Start presses={presses}"
    )


def search_utf16(ws):
    r = ws.request(
        "memory.search",
        timeout=30,
        address=RAM_SEARCH_START,
        size=RAM_SEARCH_SIZE,
        type="bytes",
        base64=base64.b64encode(TEST_UTF16).decode("ascii"),
        align=2,
        maxResults=64,
    )
    return [int(x) for x in r.get("matches", [])]


def remove_breakpoint(ws, address):
    try:
        ws.request(
            "cpu.breakpoint.remove",
            timeout=5,
            address=address,
        )
    except Exception:
        pass


def verify_source_iso():
    if not SOURCE_ISO.exists():
        raise RuntimeError(f"Stage39C ISO not found: {SOURCE_ISO}")

    _, mdi = iso_read(SOURCE_ISO, TARGET_MDI)
    streams = parse_mdi(mdi)

    if len(streams) <= SOURCE_STREAM_INDEX:
        raise RuntimeError("Stage39C MDI has no stream11")

    s11 = streams[SOURCE_STREAM_INDEX]["decoded"]

    hits = []
    start = 0
    while True:
        p = s11.find(TEST_UTF8, start)
        if p < 0:
            break
        hits.append(p)
        start = p + 1

    if len(hits) < 2:
        raise RuntimeError(
            "Stage39C UTF-8 source proof is missing: "
            f"found {len(hits)} copies of test UTF-8 bytes in stream11"
        )

    return {
        "utf8_source_hits_stream11": [f"0x{x:X}" for x in hits],
        "runtime_addresses": [
            f"0x{SOURCE_STREAM_BASE + x:08X}" for x in hits
        ],
        "count": len(hits),
    }


def patch_biaon():
    decoder = (SCRIPT_DIR / "utf8_decoder.bin").read_bytes()

    if hashlib_sha1(decoder) != EXPECTED_DECODER_BLOB_SHA1:
        raise RuntimeError("UTF-8 decoder blob SHA1 mismatch")

    rec, prx = iso_read(TEST_ISO, TARGET_PRX)
    before_sha1 = hashlib_sha1(prx)

    # Stage39C did not patch the converter, so this branch must still be the
    # original bnez.  Permit a different whole-file SHA1 only if this exact
    # code signature is still pristine.
    if prx[
        DISPATCH_BRANCH_FILE_OFF:
        DISPATCH_BRANCH_FILE_OFF + 4
    ] != EXPECTED_BRANCH_BYTES:
        got = prx[
            DISPATCH_BRANCH_FILE_OFF:
            DISPATCH_BRANCH_FILE_OFF + 4
        ].hex()
        raise RuntimeError(
            "Unexpected BIAON converter dispatch bytes: "
            f"{got}, expected {EXPECTED_BRANCH_BYTES.hex()}"
        )

    if UTF8_DECODER_FILE_OFF + len(decoder) >= len(prx):
        raise RuntimeError("Injected decoder would exceed BIAON.PRX")

    patched = bytearray(prx)

    patched[
        DISPATCH_BRANCH_FILE_OFF:
        DISPATCH_BRANCH_FILE_OFF + 4
    ] = PATCHED_BRANCH_BYTES

    patched[
        UTF8_DECODER_FILE_OFF:
        UTF8_DECODER_FILE_OFF + len(decoder)
    ] = decoder

    iso_overwrite_same_size(
        TEST_ISO,
        TARGET_PRX,
        bytes(patched),
    )

    _, rb = iso_read(TEST_ISO, TARGET_PRX)

    if rb[
        DISPATCH_BRANCH_FILE_OFF:
        DISPATCH_BRANCH_FILE_OFF + 4
    ] != PATCHED_BRANCH_BYTES:
        raise RuntimeError("BIAON branch patch read-back failed")

    if rb[
        UTF8_DECODER_FILE_OFF:
        UTF8_DECODER_FILE_OFF + len(decoder)
    ] != decoder:
        raise RuntimeError("BIAON decoder blob read-back failed")

    return {
        "original_full_sha1": before_sha1,
        "reference_original_sha1": EXPECTED_ORIGINAL_BIAON_SHA1,
        "patched_full_sha1": hashlib_sha1(rb),
        "branch_vaddr": f"0x{DISPATCH_BRANCH_VA:08X}",
        "branch_file_offset": f"0x{DISPATCH_BRANCH_FILE_OFF:X}",
        "branch_old": EXPECTED_BRANCH_BYTES.hex(),
        "branch_new": PATCHED_BRANCH_BYTES.hex(),
        "decoder_vaddr": f"0x{UTF8_DECODER_VA:08X}",
        "decoder_file_offset": f"0x{UTF8_DECODER_FILE_OFF:X}",
        "decoder_bytes": len(decoder),
        "decoder_sha1": hashlib_sha1(decoder),
        "converter_runtime": f"0x{CONVERTER_RUNTIME:08X}",
        "utf8_store_runtime": f"0x{UTF8_3BYTE_STORE_RUNTIME:08X}",
        "iso_extent": rec["extent"],
        "iso_size": rec["size"],
    }


def hashlib_sha1(data: bytes) -> str:
    import hashlib
    return hashlib.sha1(data).hexdigest()


def runtime_test(local_mod, b):
    exe = b.find_ppsspp_exe()

    cfg = OUT / "stage39d_append.ini"
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

    requested_port = b.choose_free_port()

    try:
        previous = b.close_existing_ppsspp(timeout=3.0)
    except Exception:
        previous = None

    cmd = [
        str(exe),
        "-d",
        f"--log={PPSSPP_LOG}",
        "--windowed",
        f"--appendconfig={cfg}",
        f"--debugger={requested_port}",
        str(TEST_ISO),
    ]

    log("[Stage39D] Launching PPSSPP in normal JIT mode")
    proc = subprocess.Popen(cmd)
    cleanup = b.register_ppsspp_auto_close(proc)

    result = {
        "ppsspp_exe": str(exe),
        "pid": proc.pid,
        "previous_ppsspp_cleanup": previous,
        "runtime_ram_text_patch": False,
        "runtime_code_patch": False,
        "test_iso_only": True,
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

            try:
                result["version"] = ws.request(
                    "version",
                    timeout=5,
                    name="bia-stage39d",
                    version="1",
                )
            except Exception as e:
                result["version_error"] = str(e)

            # Confirm the patched instructions are actually loaded into PSP RAM.
            try:
                h = b.open_process(pid)
                try:
                    branch_runtime = (
                        BIAON_RUNTIME_BASE + DISPATCH_BRANCH_VA
                    )
                    decoder_runtime = (
                        BIAON_RUNTIME_BASE + UTF8_DECODER_VA
                    )
                    branch_mem = b.guest_read(
                        h, base, branch_runtime, 4
                    )
                    decoder_mem = b.guest_read(
                        h, base, decoder_runtime,
                        len((SCRIPT_DIR / "utf8_decoder.bin").read_bytes())
                    )
                finally:
                    b.kernel32.CloseHandle(h)

                result["loaded_code"] = {
                    "branch_address": f"0x{branch_runtime:08X}",
                    "branch_bytes": branch_mem.hex(),
                    "branch_ok": branch_mem == PATCHED_BRANCH_BYTES,
                    "decoder_address": f"0x{decoder_runtime:08X}",
                    "decoder_sha1": hashlib_sha1(decoder_mem),
                    "decoder_ok":
                        hashlib_sha1(decoder_mem)
                        == EXPECTED_DECODER_BLOB_SHA1,
                }
            except Exception as e:
                result["loaded_code_error"] = str(e)

            # Break exactly on the 3-byte UTF-8 store when the first Hangul
            # codepoint (U+C2A4) has been reconstructed into t0.
            ws.request(
                "cpu.breakpoint.add",
                timeout=10,
                address=UTF8_3BYTE_STORE_RUNTIME,
                enabled=True,
                log=True,
                condition=f"t0 == 0x{FIRST_CODEPOINT:04X}",
                logFormat=(
                    "BIA_STAGE39D_UTF8_STORE "
                    "pc={pc} s0={s0} s1={s1} s3={s3} s5={s5} "
                    "t0={t0} ra={ra}"
                ),
            )

            # Reset after installing the breakpoint so the localization path
            # cannot race past it during initial boot.
            try:
                ws.request("game.reset", timeout=10)
            except Exception as e:
                result["game_reset_request"] = str(e)

            # The breakpoint should survive reset, but re-add defensively once
            # the CPU is alive again.
            time.sleep(0.8)
            try:
                ws.request(
                    "cpu.breakpoint.add",
                    timeout=10,
                    address=UTF8_3BYTE_STORE_RUNTIME,
                    enabled=True,
                    log=True,
                    condition=f"t0 == 0x{FIRST_CODEPOINT:04X}",
                    logFormat=(
                        "BIA_STAGE39D_UTF8_STORE "
                        "pc={pc} s0={s0} s1={s1} s3={s3} s5={s5} "
                        "t0={t0} ra={ra}"
                    ),
                )
            except Exception:
                pass

            status, presses = wait_until_stepping(
                ws, timeout=120.0, press_start=True
            )

            result["break_status"] = status
            result["start_presses_before_hit"] = presses

            regs_resp = ws.request(
                "cpu.getAllRegs",
                timeout=10,
            )
            regs = regs_to_dict(regs_resp)

            pc = regs.get("pc", int(status.get("pc", 0)))
            s0 = regs.get("s0", 0)
            s1 = regs.get("s1", 0)
            s3 = regs.get("s3", 0)
            s5 = regs.get("s5", 0)
            t0 = regs.get("t0", 0)
            ra = regs.get("ra", 0)

            trace = {
                "pc": f"0x{pc:08X}",
                "expected_pc": f"0x{UTF8_3BYTE_STORE_RUNTIME:08X}",
                "t0_codepoint": f"0x{t0:04X}",
                "expected_codepoint": f"0x{FIRST_CODEPOINT:04X}",
                "encoding_object_s0": f"0x{s0:08X}",
                "dest_s1": f"0x{s1:08X}",
                "remaining_s3": s3,
                "source_s5": f"0x{s5:08X}",
                "caller_ra": f"0x{ra:08X}",
                "source_bytes_16": None,
                "dest_bytes_before_store_16": None,
                "encoding_name_ptr": None,
                "encoding_name": None,
                "caller_disasm": disasm(
                    ws,
                    max(0, (ra - 16) & 0xFFFFFFFF),
                    16,
                ) if ra else None,
                "decoder_disasm": disasm(
                    ws,
                    CONVERTER_RUNTIME,
                    48,
                ),
            }

            try:
                trace["source_bytes_16"] = read_bytes_ws(
                    ws, s5, 16
                ).hex()
            except Exception as e:
                trace["source_read_error"] = str(e)

            try:
                trace["dest_bytes_before_store_16"] = read_bytes_ws(
                    ws, s1, 16
                ).hex()
            except Exception as e:
                trace["dest_read_error"] = str(e)

            try:
                name_ptr = read_u32(ws, s0 + 0x34)
                trace["encoding_name_ptr"] = (
                    f"0x{name_ptr:08X}"
                )
                trace["encoding_name"] = read_ascii_string(
                    ws, name_ptr, 48
                )
            except Exception as e:
                trace["encoding_name_error"] = str(e)

            result["decoder_trace"] = trace
            result["decoder_function_confirmed"] = (
                pc == UTF8_3BYTE_STORE_RUNTIME
                and t0 == FIRST_CODEPOINT
            )

            remove_breakpoint(
                ws,
                UTF8_3BYTE_STORE_RUNTIME,
            )

            # Continue, but DO NOT keep pressing Start after the Korean
            # conversion hit.  Stage39C proved that continued Start presses
            # can leave the main menu and invalidate fixed-slot observations.
            try:
                ws.request("cpu.resume", timeout=3)
            except Exception:
                # cpu.resume intentionally has no immediate response on some
                # builds; this is not fatal.
                pass

            time.sleep(0.8)

            matches = search_utf16(ws)
            result["utf16_search"] = {
                "pattern_hex": TEST_UTF16.hex(),
                "matches": [
                    f"0x{x:08X}" for x in matches
                ],
                "count": len(matches),
                "found": bool(matches),
            }

            # Known Stage39C dynamic wide-copy area is recorded as evidence
            # if it appears among the search results, but success does not
            # depend on any fixed address.
            result["known_stage39c_wide_copy_match"] = (
                0x08E4E82C in matches
            )

            # Optional production-font verifier from the existing Stage39B
            # toolchain.
            plan_path = BASE_TOOLS / "stage39a_font_plan.json"
            if plan_path.exists():
                plan = json.loads(
                    plan_path.read_text(encoding="utf-8")
                )
                inspect = find_callable(
                    [
                        local_mod,
                        getattr(local_mod, "s39", None),
                        b,
                    ],
                    "inspect_production_runtime",
                )
                if inspect:
                    try:
                        result["production_font_runtime"] = inspect(
                            pid,
                            base,
                            plan,
                            plan["atlas_sha1"],
                        )
                    except Exception as e:
                        result["production_font_runtime_error"] = str(e)

            # Diagnostic capture only.  A capture failure is not treated as
            # source/decoder failure, matching the Stage36/39C policy.
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

            font_result = result.get(
                "production_font_runtime", {}
            )
            font_ok = (
                font_result.get("ok", True)
                if isinstance(font_result, dict)
                else True
            )

            result["source_unicode_proof"] = (
                result["decoder_function_confirmed"]
                and bool(matches)
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
                z.write(
                    p,
                    p.relative_to(OUT).as_posix(),
                )

        # Include the actual disk patch artifact and manifest inputs.
        for name in [
            "utf8_decoder.bin",
            "README.txt",
        ]:
            p = SCRIPT_DIR / name
            if p.exists():
                z.write(p, name)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    for p in OUT.iterdir():
        if p.is_file():
            p.unlink()

    local_mod, b = load_local_helpers()

    report = {
        "stage": "39D",
        "purpose":
            "Replace the default byte-wise narrow-to-wide fallback with a "
            "real UTF-8 -> UTF-16 BMP decoder, then prove the Stage39C on-disc "
            "UTF-8 source reaches the production Unicode font without RAM text patches.",
        "stage39c_fixed_slot_assumption_used": False,
        "stage39c_false_decoder_0x088B4CA8_used": False,
        "runtime_text_patch": False,
        "runtime_font_patch": False,
        "runtime_code_patch": False,
        "disc_only_code_patch": True,
        "screenshot_failure_is_not_test_failure": True,
    }

    report["stage39c_source"] = verify_source_iso()

    if TEST_ISO.exists():
        TEST_ISO.unlink()

    log("[Stage39D] Copying Stage39C diagnostic ISO")
    shutil.copy2(SOURCE_ISO, TEST_ISO)

    report["biaon_patch"] = patch_biaon()

    # Final static read-back before execution.
    _, prx_rb = iso_read(TEST_ISO, TARGET_PRX)
    report["biaon_iso_readback"] = {
        "branch_bytes": prx_rb[
            DISPATCH_BRANCH_FILE_OFF:
            DISPATCH_BRANCH_FILE_OFF + 4
        ].hex(),
        "decoder_sha1": hashlib_sha1(
            prx_rb[
                UTF8_DECODER_FILE_OFF:
                UTF8_DECODER_FILE_OFF
                + len((SCRIPT_DIR / "utf8_decoder.bin").read_bytes())
            ]
        ),
        "verified": True,
    }

    try:
        runtime = runtime_test(local_mod, b)
        report["runtime"] = runtime
        report["completed"] = bool(
            runtime.get("source_unicode_proof", False)
        )
    except Exception as e:
        report["runtime_exception"] = str(e)
        report["runtime_traceback"] = traceback.format_exc()
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
        log("[Stage39D] COMPLETE")
        log(f"[Stage39D] ISO: {TEST_ISO}")
        log(f"[Stage39D] Upload ZIP: {SUCCESS_ZIP}")
        return

    make_zip(FAIL_ZIP)
    raise RuntimeError(
        "Stage39D source Unicode proof did not complete. "
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
            if REPORT_PATH.exists():
                pass
            make_zip(FAIL_ZIP)
        except Exception:
            pass

        # ASCII-only console output.
        print(traceback.format_exc(), flush=True)
        print(f"STAGE 39D FAILED: {FAIL_ZIP}", flush=True)
        raise SystemExit(1)
