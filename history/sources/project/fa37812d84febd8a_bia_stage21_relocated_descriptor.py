#!/usr/bin/env python3
from __future__ import annotations

import base64
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
import secrets
import shutil
import socket
import struct
import subprocess
import time
import traceback
import zipfile
import zlib
from pathlib import Path

ROOT = Path(r"PROJECT_ROOT")
LOG_DIR = ROOT / "log"
ANALYSIS_DIR = ROOT / "analysis" / "stage21_relocated_descriptor"
TEST_ISO = ROOT / "BIA_STAGE21_RELOC_DESCRIPTOR_TEST.iso"

TARGET_MDI = ["PSP_GAME", "USRDIR", "SYSTEM", "ON_MEMU_O.MDI"]
TARGET_DSL = ["PSP_GAME", "USRDIR", "SYSTEM", "ON_MEMU.DSL"]

EXPECTED_MDI_SHA1 = "22de1f889d1617199a3e21d4a1f63fcaf87b944a"
EXPECTED_DSL_SHA1 = "e009f2e259861f60d0aeeb03f46422d5473b88aa"

# Confirmed original TMR descriptor.
TMR_DESC_OFF = 0x175137

# Sequential MDI memory-image layout for streams 0..34.
MDI_SEQ_BASE = 0x08E2D020
MDI_STREAM_SIZE = 0x78000

STREAM19_INDEX = 19
STREAM19_RAM_BASE = MDI_SEQ_BASE + STREAM19_INDEX * MDI_STREAM_SIZE
STREAM22_INDEX = 22
STREAM22_RAM_BASE = MDI_SEQ_BASE + STREAM22_INDEX * MDI_STREAM_SIZE

# TMR font object inside stream19.
TMR_PAGE_TABLE_OFF = 0xE894
TMR_OBJ_OFF = TMR_PAGE_TABLE_OFF - 0x58
TMR_COUNT_OFF = TMR_OBJ_OFF + 0x50
TMR_GLYPH_PTR_OFF = TMR_OBJ_OFF + 0x54

# Proven persistent static hole in stream19.
STATIC_HOLE_START = 0x6AF0
STATIC_HOLE_END   = 0x9570
TMR_NEW_GLYPH_ARRAY_OFF = 0x6B00
TMR_NEW_D5_PAGE_OFF = 0x7A00

OLD_GLYPH_COUNT = 151
NEW_GLYPH_INDEX = 151
NEW_GLYPH_COUNT = 152
GLYPH_REC_SIZE = 24

TEST_CP = 0xD55C
TEST_HIGH = 0xD5
TEST_LOW = 0x5C

TMR_TEX_ADDR = STREAM22_RAM_BASE

# Magma DSL loader relocation discovered from original TMR/AB18 pairs.
# source_descriptor_address - runtime_texture_address is constant.
DSL_RELOC_DELTA = 0x01144600

# Original TMR descriptor is transformed into this runtime copy.
# Confirmed byte-for-byte in the original main-menu RAM dump.
TMR_RUNTIME_DESC = 0x08E693C0
TMR_TEX_SIZE = 0x8000
TMR_TEX_W = 128
TMR_TEX_H = 512

STORY_GUEST = 0x08E41620

WM_APP = 0x8000
WM_USER_GET_BASE_POINTER = WM_APP + 0x3118
SW_RESTORE = 9

PROCESS_VM_READ = 0x0010
PROCESS_VM_WRITE = 0x0020
PROCESS_VM_OPERATION = 0x0008
PROCESS_QUERY_INFORMATION = 0x0400

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
user32 = ctypes.WinDLL("user32", use_last_error=True)

user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
user32.FindWindowW.restype = wintypes.HWND
user32.SendMessageW.argtypes = [
    wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM
]
user32.SendMessageW.restype = ctypes.c_ssize_t
user32.GetWindowThreadProcessId.argtypes = [
    wintypes.HWND, ctypes.POINTER(wintypes.DWORD)
]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.SetForegroundWindow.restype = wintypes.BOOL
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.ShowWindow.restype = wintypes.BOOL

kernel32.OpenProcess.argtypes = [
    wintypes.DWORD, wintypes.BOOL, wintypes.DWORD
]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.ReadProcessMemory.argtypes = [
    wintypes.HANDLE, wintypes.LPCVOID, wintypes.LPVOID,
    ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)
]
kernel32.ReadProcessMemory.restype = wintypes.BOOL
kernel32.WriteProcessMemory.argtypes = [
    wintypes.HANDLE, wintypes.LPVOID, wintypes.LPCVOID,
    ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)
]
kernel32.WriteProcessMemory.restype = wintypes.BOOL
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL


def log(s=""):
    print(s, flush=True)


def sha1_bytes(b):
    return hashlib.sha1(b).hexdigest()


# ---------------- ISO9660 ----------------

def iso_norm_name(raw: bytes) -> str:
    if raw == b"\x00":
        return "."
    if raw == b"\x01":
        return ".."
    s = raw.decode("ascii", "replace")
    if ";" in s:
        s = s.split(";", 1)[0]
    return s.upper()


def iso_read_record(f, off):
    f.seek(off)
    b = f.read(1)
    if not b:
        return None
    ln = b[0]
    if ln == 0:
        return {"length": 0}
    rec = b + f.read(ln - 1)
    if len(rec) != ln or ln < 34:
        return None
    nlen = rec[32]
    return {
        "length": ln,
        "extent": struct.unpack_from("<I", rec, 2)[0],
        "size": struct.unpack_from("<I", rec, 10)[0],
        "flags": rec[25],
        "name": iso_norm_name(rec[33:33+nlen]),
        "record_offset": off,
    }


def iso_list_dir(f, extent, size):
    pos = extent * 2048
    end = pos + size
    while pos < end:
        f.seek(pos)
        b = f.read(1)
        if not b:
            break
        ln = b[0]
        if ln == 0:
            pos = ((pos // 2048) + 1) * 2048
            continue
        rec = iso_read_record(f, pos)
        if not rec:
            raise RuntimeError(f"Bad ISO directory record at 0x{pos:X}")
        yield rec
        pos += rec["length"]


def iso_find_record(iso: Path, parts):
    with iso.open("rb") as f:
        f.seek(16 * 2048)
        pvd = f.read(2048)
        if len(pvd) != 2048 or pvd[0] != 1 or pvd[1:6] != b"CD001":
            raise RuntimeError("ISO9660 PVD not found")

        root_len = pvd[156]
        root = pvd[156:156+root_len]
        extent = struct.unpack_from("<I", root, 2)[0]
        size = struct.unpack_from("<I", root, 10)[0]

        found = None
        for part in parts:
            found = None
            for rec in iso_list_dir(f, extent, size):
                if rec["name"] == part.upper():
                    found = rec
                    break
            if not found:
                raise RuntimeError(f"ISO path not found: {'/'.join(parts)}")
            extent, size = found["extent"], found["size"]
        return found


def iso_read_file(iso: Path, parts):
    rec = iso_find_record(iso, parts)
    with iso.open("rb") as f:
        f.seek(rec["extent"] * 2048)
        data = f.read(rec["size"])
    if len(data) != rec["size"]:
        raise RuntimeError("Short ISO read")
    return rec, data


def patch_dir_record_extent_size(f, record_offset, extent, size):
    f.seek(record_offset + 2)
    f.write(struct.pack("<I", extent))
    f.write(struct.pack(">I", extent))
    f.seek(record_offset + 10)
    f.write(struct.pack("<I", size))
    f.write(struct.pack(">I", size))


def update_volume_space_size(f, total_sectors):
    sector = 16
    while True:
        off = sector * 2048
        f.seek(off)
        vd = bytearray(f.read(2048))
        if len(vd) != 2048 or vd[1:6] != b"CD001":
            break
        typ = vd[0]
        if typ in (1, 2):
            struct.pack_into("<I", vd, 80, total_sectors)
            struct.pack_into(">I", vd, 84, total_sectors)
            f.seek(off)
            f.write(vd)
        if typ == 255:
            break
        sector += 1


def align_up(v, a):
    return (v + a - 1) & ~(a - 1)


def append_iso_file_and_repoint(iso: Path, target_parts, payload: bytes):
    rec = iso_find_record(iso, target_parts)
    with iso.open("r+b") as f:
        f.seek(0, os.SEEK_END)
        eof = f.tell()
        new_off = align_up(eof, 2048)
        if new_off > eof:
            f.write(b"\x00" * (new_off - eof))

        f.seek(new_off)
        f.write(payload)

        padded_end = align_up(new_off + len(payload), 2048)
        if padded_end > new_off + len(payload):
            f.write(b"\x00" * (padded_end - (new_off + len(payload))))

        new_extent = new_off // 2048
        patch_dir_record_extent_size(
            f, rec["record_offset"], new_extent, len(payload)
        )
        update_volume_space_size(f, padded_end // 2048)

    return {
        "old_extent": rec["extent"],
        "old_size": rec["size"],
        "new_extent": new_extent,
        "new_size": len(payload),
    }


def overwrite_iso_same_size(iso: Path, target_parts, payload: bytes):
    rec = iso_find_record(iso, target_parts)
    if len(payload) != rec["size"]:
        raise RuntimeError("same-size overwrite required")
    with iso.open("r+b") as f:
        f.seek(rec["extent"] * 2048)
        f.write(payload)


# ---------------- MDI ----------------

def valid_zlib_header(two):
    if len(two) != 2:
        return False
    cmf, flg = two
    return (cmf & 0x0F) == 8 and ((cmf << 8) + flg) % 31 == 0


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
                "size_field_pos": pos,
                "zpos": zpos,
                "csize": csize,
                "decoded": dec,
            })
            pos = zpos + csize
            idx += 1
            continue

        # Optional 4-byte region/load marker before the next stream.
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

        raise RuntimeError(f"MDI parse failed at 0x{pos:X}")

    if pos != len(data):
        raise RuntimeError("MDI parse did not end at EOF")

    return streams


def rebuild_mdi(original: bytes, replacements: dict[int, bytes]):
    streams = parse_mdi(original)
    by_pos = []
    for idx, dec in replacements.items():
        st = streams[idx]
        comp = zlib.compress(dec, 9)
        by_pos.append((st["size_field_pos"], st, comp))

    by_pos.sort()
    out = bytearray()
    cur = 0

    for pos, st, comp in by_pos:
        out += original[cur:pos]
        out += struct.pack("<I", len(comp))
        out += comp
        cur = st["zpos"] + st["csize"]

    out += original[cur:]
    return bytes(out)


def patch_mdi(original: bytes, expanded_tex: bytes):
    streams = parse_mdi(original)
    if len(streams) <= STREAM22_INDEX:
        raise RuntimeError("MDI does not contain stream22")

    s19 = streams[STREAM19_INDEX]
    s22 = streams[STREAM22_INDEX]

    if len(s19["decoded"]) != MDI_STREAM_SIZE:
        raise RuntimeError("stream19 unexpected size")
    if len(s22["decoded"]) != MDI_STREAM_SIZE:
        raise RuntimeError("stream22 unexpected size")
    if any(s22["decoded"]):
        raise RuntimeError("stream22 is not all-zero in original MDI")

    dec19 = bytearray(s19["decoded"])
    dec22 = bytearray(s22["decoded"])

    # Validate persistent stream19 hole.
    if any(dec19[STATIC_HOLE_START:STATIC_HOLE_END]):
        raise RuntimeError("stream19 static hole not zero")

    old_count = struct.unpack_from("<H", dec19, TMR_COUNT_OFF)[0]
    old_ptr = struct.unpack_from("<I", dec19, TMR_GLYPH_PTR_OFF)[0]
    if old_count != OLD_GLYPH_COUNT or old_ptr != 0x09723FD8:
        raise RuntimeError(
            f"Unexpected TMR font object count={old_count} ptr=0x{old_ptr:08X}"
        )

    old_ptr_off = old_ptr - STREAM19_RAM_BASE

    # Copy all original records into persistent static hole.
    recs = bytearray(
        dec19[
            old_ptr_off:
            old_ptr_off + OLD_GLYPH_COUNT * GLYPH_REC_SIZE
        ]
    )

    # Real texture becomes 2x taller: old glyphs remain in the top half.
    for i in range(OLD_GLYPH_COUNT):
        o = i * GLYPH_REC_SIZE
        v0 = struct.unpack_from("<f", recs, o + 12)[0]
        v1 = struct.unpack_from("<f", recs, o + 20)[0]
        struct.pack_into("<f", recs, o + 12, v0 * 0.5)
        struct.pack_into("<f", recs, o + 20, v1 * 0.5)

    array_end = TMR_NEW_GLYPH_ARRAY_OFF + len(recs)
    if array_end > TMR_NEW_D5_PAGE_OFF:
        raise RuntimeError("glyph array overlaps D5 page")

    dec19[
        TMR_NEW_GLYPH_ARRAY_OFF:
        TMR_NEW_GLYPH_ARRAY_OFF + len(recs)
    ] = recs

    # New #151 record uses A metrics, but bottom-half Korean bitmap UV.
    A_MAP_VALUE = 34
    a_off = old_ptr_off + A_MAP_VALUE * GLYPH_REC_SIZE
    new_rec = bytearray(dec19[a_off:a_off+GLYPH_REC_SIZE])
    struct.pack_into("<H", new_rec, 0, TEST_CP)
    struct.pack_into("<f", new_rec, 8,  0.5 / 128.0)
    struct.pack_into("<f", new_rec, 12, 256.5 / 512.0)
    struct.pack_into("<f", new_rec, 16, 17.5 / 128.0)
    struct.pack_into("<f", new_rec, 20, 272.5 / 512.0)

    nr = TMR_NEW_GLYPH_ARRAY_OFF + NEW_GLYPH_INDEX * GLYPH_REC_SIZE
    dec19[nr:nr+GLYPH_REC_SIZE] = new_rec

    # Independent D5 Unicode page.
    page = bytearray(512)
    struct.pack_into("<H", page, TEST_LOW * 2, NEW_GLYPH_INDEX)
    dec19[TMR_NEW_D5_PAGE_OFF:TMR_NEW_D5_PAGE_OFF+512] = page

    # Redirect font object.
    struct.pack_into("<H", dec19, TMR_COUNT_OFF, NEW_GLYPH_COUNT)
    struct.pack_into(
        "<I", dec19, TMR_GLYPH_PTR_OFF,
        STREAM19_RAM_BASE + TMR_NEW_GLYPH_ARRAY_OFF
    )
    struct.pack_into(
        "<I", dec19,
        TMR_PAGE_TABLE_OFF + TEST_HIGH * 4,
        STREAM19_RAM_BASE + TMR_NEW_D5_PAGE_OFF
    )

    # Store the complete expanded raw texture in a wholly unused, persistent
    # memory-image stream. No DSL growth is needed.
    if len(expanded_tex) != TMR_TEX_SIZE:
        raise RuntimeError("expanded texture wrong size")
    dec22[:len(expanded_tex)] = expanded_tex

    rebuilt = rebuild_mdi(original, {
        STREAM19_INDEX: bytes(dec19),
        STREAM22_INDEX: bytes(dec22),
    })

    # Reparse verification.
    vs = parse_mdi(rebuilt)
    v19 = vs[STREAM19_INDEX]["decoded"]
    v22 = vs[STREAM22_INDEX]["decoded"]

    checks = {
        "count": struct.unpack_from("<H", v19, TMR_COUNT_OFF)[0],
        "glyph_ptr": struct.unpack_from("<I", v19, TMR_GLYPH_PTR_OFF)[0],
        "D5_ptr": struct.unpack_from(
            "<I", v19, TMR_PAGE_TABLE_OFF + TEST_HIGH * 4
        )[0],
        "D55C_map": struct.unpack_from(
            "<H", v19, TMR_NEW_D5_PAGE_OFF + TEST_LOW * 2
        )[0],
        "texture_sha1": sha1_bytes(v22[:TMR_TEX_SIZE]),
    }
    expected = {
        "count": NEW_GLYPH_COUNT,
        "glyph_ptr": STREAM19_RAM_BASE + TMR_NEW_GLYPH_ARRAY_OFF,
        "D5_ptr": STREAM19_RAM_BASE + TMR_NEW_D5_PAGE_OFF,
        "D55C_map": NEW_GLYPH_INDEX,
        "texture_sha1": sha1_bytes(expanded_tex),
    }
    if checks != expected:
        raise RuntimeError(f"MDI rebuild verification failed: {checks}")

    return rebuilt, {
        "stream19_old_csize": s19["csize"],
        "stream19_new_csize": vs[STREAM19_INDEX]["csize"],
        "stream22_old_csize": s22["csize"],
        "stream22_new_csize": vs[STREAM22_INDEX]["csize"],
        "new_glyph_ptr": f"0x{expected['glyph_ptr']:08X}",
        "new_D5_page": f"0x{expected['D5_ptr']:08X}",
        "texture_runtime_address": f"0x{TMR_TEX_ADDR:08X}",
        "texture_sha1": expected["texture_sha1"],
    }


def patch_dsl_descriptor(original: bytes):
    """
    Keep Magma's native relocation path.

    Original proof:
      DSL source descriptor address : 0x096C4540
      runtime texture address       : 0x0857FF40
      difference                    : 0x01144600

    AB18 has the exact same delta.

    Therefore, to make the loader produce runtime texture 0x0987D020,
    encode source address:
      0x0987D020 + 0x01144600 = 0x0A9C1620

    The relocation marker is bit 22 (0x00400000) in TEXBUFWIDTH's data.
    """
    patched = bytearray(original)

    old_a0, old_a8, old_b8 = struct.unpack_from(
        "<III", original, TMR_DESC_OFF
    )
    if (
        old_a0 != 0xA06C4540
        or old_a8 != 0xA8490080
        or old_b8 != 0xB8000807
    ):
        raise RuntimeError(
            "Original TMR descriptor mismatch: "
            f"A0=0x{old_a0:08X}, A8=0x{old_a8:08X}, "
            f"B8=0x{old_b8:08X}"
        )

    source_addr = TMR_TEX_ADDR + DSL_RELOC_DELTA

    new_a0 = (
        0xA0000000
        | (source_addr & 0x00FFFFFF)
    )
    new_a8 = (
        0xA8000000
        | 0x00400000
        | (((source_addr >> 24) & 0x0F) << 16)
        | TMR_TEX_W
    )
    new_b8 = 0xB8000907  # 128x512

    struct.pack_into(
        "<III",
        patched,
        TMR_DESC_OFF,
        new_a0,
        new_a8,
        new_b8,
    )

    expected_runtime_a0 = (
        0xA0000000
        | (TMR_TEX_ADDR & 0x00FFFFFF)
    )
    expected_runtime_a8 = (
        0xA8000000
        | (((TMR_TEX_ADDR >> 24) & 0x0F) << 16)
        | TMR_TEX_W
    )

    return bytes(patched), {
        "old_A0": f"0x{old_a0:08X}",
        "old_A8": f"0x{old_a8:08X}",
        "old_B8": f"0x{old_b8:08X}",
        "relocation_delta": f"0x{DSL_RELOC_DELTA:08X}",
        "target_runtime_texture":
            f"0x{TMR_TEX_ADDR:08X}",
        "encoded_source_address":
            f"0x{source_addr:08X}",
        "new_source_A0": f"0x{new_a0:08X}",
        "new_source_A8": f"0x{new_a8:08X}",
        "new_source_B8": f"0x{new_b8:08X}",
        "expected_runtime_descriptor_address":
            f"0x{TMR_RUNTIME_DESC:08X}",
        "expected_runtime_A0":
            f"0x{expected_runtime_a0:08X}",
        "expected_runtime_A8":
            f"0x{expected_runtime_a8:08X}",
        "expected_runtime_B8":
            f"0x{new_b8:08X}",
    }




# ---------------- PPSSPP process ----------------

def find_stage09_memstick():
    summary = ROOT / "analysis" / "stage09_texture_dump" / "summary.json"
    if summary.exists():
        try:
            data = json.loads(summary.read_text(encoding="utf-8"))
            for s in data.get("dump_dirs", []):
                q = Path(s)
                while q != q.parent:
                    if q.name.lower() == "memstick":
                        return q
                    q = q.parent
        except Exception:
            pass
    known = Path(
        r"LOCAL_PATH"
        r"\c-users-admin-downloads\work\ppsspp\memstick"
    )
    return known if known.is_dir() else None


def find_ppsspp_exe():
    candidates = []
    memstick = find_stage09_memstick()
    if memstick:
        b = memstick.parent
        candidates += [
            b / "PPSSPPWindows64.exe",
            b / "PPSSPPDebug64.exe",
            b / "PPSSPPWindows.exe",
        ]
    candidates += [
        ROOT / "PPSSPPWindows64.exe",
        ROOT / "ppsspp" / "PPSSPPWindows64.exe",
    ]
    for p in candidates:
        if p.is_file():
            return p

    codex = Path.home() / "Documents" / "Codex"
    if codex.is_dir():
        for name in ("PPSSPPWindows64.exe", "PPSSPPDebug64.exe"):
            hits = list(codex.rglob(name))
            if hits:
                return max(hits, key=lambda p: p.stat().st_mtime_ns)
    raise RuntimeError("PPSSPP executable not found")


def find_original_iso():
    isos = []
    for p in ROOT.glob("*.iso"):
        if not p.is_file():
            continue
        u = p.name.upper()
        if "STAGE" in u or "TEST" in u:
            continue
        isos.append(p)
    if not isos:
        raise RuntimeError(r"Original ISO not found under PROJECT_ROOT")
    named = [
        p for p in isos
        if "BROTHERS" in p.name.upper() or "D-DAY" in p.name.upper()
    ]
    return max(named or isos, key=lambda p: p.stat().st_size)


def write_append_config():
    cfg = ANALYSIS_DIR / "stage21_append.ini"
    cfg.write_text(
        "[Debugger]\n"
        "ShowDeveloperMenu = True\n"
        "\n"
        "[Graphics]\n"
        "ReplaceTextures = False\n"
        "SaveNewTextures = False\n",
        encoding="utf-8"
    )
    return cfg


def choose_free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]
    finally:
        s.close()


def wait_for_actual_debugger_port(log_path: Path, timeout=30):
    import re
    pat = re.compile(
        r"HTTP .*server started on port\s+(\d+):\s*debugger-webserver"
    )
    end = time.time() + timeout
    while time.time() < end:
        if log_path.exists():
            txt = log_path.read_text(encoding="utf-8", errors="replace")
            hits = pat.findall(txt)
            if hits:
                return int(hits[-1])
        time.sleep(0.2)
    raise RuntimeError("debugger-webserver port not found in PPSSPP log")


def find_ppsspp_hwnd(timeout=30):
    end = time.time() + timeout
    while time.time() < end:
        hwnd = user32.FindWindowW("PPSSPPWnd", None)
        if hwnd:
            return hwnd
        time.sleep(0.2)
    return 0


def get_pid_base(hwnd):
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    lo = int(user32.SendMessageW(
        hwnd, WM_USER_GET_BASE_POINTER, 0, 0
    )) & 0xFFFFFFFF
    hi = int(user32.SendMessageW(
        hwnd, WM_USER_GET_BASE_POINTER, 0, 1
    )) & 0xFFFFFFFF
    base = (hi << 32) | lo
    if not pid.value or not base:
        raise RuntimeError("Could not obtain PPSSPP PID/base pointer")
    return pid.value, base


def open_process(pid):
    h = kernel32.OpenProcess(
        PROCESS_VM_READ | PROCESS_VM_WRITE |
        PROCESS_VM_OPERATION | PROCESS_QUERY_INFORMATION,
        False, pid
    )
    if not h:
        raise RuntimeError(f"OpenProcess failed ({ctypes.get_last_error()})")
    return h


def rpm(h, addr, size):
    buf = (ctypes.c_ubyte * size)()
    got = ctypes.c_size_t()
    ok = kernel32.ReadProcessMemory(
        h, ctypes.c_void_p(addr), ctypes.byref(buf),
        size, ctypes.byref(got)
    )
    if not ok or got.value != size:
        raise RuntimeError(f"ReadProcessMemory failed at 0x{addr:X}")
    return bytes(buf)


def wpm(h, addr, data):
    buf = ctypes.create_string_buffer(data, len(data))
    wrote = ctypes.c_size_t()
    ok = kernel32.WriteProcessMemory(
        h, ctypes.c_void_p(addr), buf,
        len(data), ctypes.byref(wrote)
    )
    if not ok or wrote.value != len(data):
        raise RuntimeError(f"WriteProcessMemory failed at 0x{addr:X}")


def guest_read(h, base, guest, size):
    return rpm(h, base + guest, size)


def guest_write(h, base, guest, data):
    wpm(h, base + guest, data)


def foreground(hwnd):
    user32.ShowWindow(hwnd, SW_RESTORE)
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.15)


def capture(hwnd, path: Path, helper: Path):
    foreground(hwnd)
    p = subprocess.run(
        [
            "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
            "-File", str(helper),
            "-Hwnd", str(int(hwnd)),
            "-OutFile", str(path),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if p.returncode != 0 or not path.exists():
        raise RuntimeError("Screenshot capture faileLOCAL_PATH" + (p.stdout or ""))


# ---------------- PPSSPP native WebSocket debugger ----------------

class MiniWebSocket:
    def __init__(self, host, port, path="/debugger",
                 protocol="debugger.ppsspp.org", timeout=20):
        self.host = host
        self.port = port
        self.path = path
        self.protocol = protocol
        self.timeout = timeout
        self.sock = None
        self.ticket = 1000

    def connect(self):
        s = socket.create_connection((self.host, self.port), timeout=5)
        s.settimeout(self.timeout)
        self.sock = s

        key = base64.b64encode(secrets.token_bytes(16)).decode("ascii")
        req = (
            f"GET {self.path} HTTP/1.1\r\n"
            f"Host: {self.host}:{self.port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n"
            f"Sec-WebSocket-Protocol: {self.protocol}\r\n"
            "\r\n"
        ).encode("ascii")
        self.sock.sendall(req)

        data = bytearray()
        while b"\r\n\r\n" not in data:
            b = self.sock.recv(4096)
            if not b:
                raise RuntimeError("WebSocket handshake closed")
            data.extend(b)
        if b" 101 " not in bytes(data).split(b"\r\n", 1)[0]:
            raise RuntimeError("WebSocket upgrade failed")

    def close(self):
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None

    def _read_exact(self, n):
        out = bytearray()
        while len(out) < n:
            b = self.sock.recv(n-len(out))
            if not b:
                raise EOFError("WebSocket closed")
            out.extend(b)
        return bytes(out)

    def _send_frame(self, payload: bytes):
        mask = secrets.token_bytes(4)
        n = len(payload)
        if n < 126:
            hdr = bytes([0x81, 0x80 | n])
        elif n <= 0xFFFF:
            hdr = bytes([0x81, 0x80 | 126]) + struct.pack(">H", n)
        else:
            hdr = bytes([0x81, 0x80 | 127]) + struct.pack(">Q", n)
        enc = bytes(payload[i] ^ mask[i & 3] for i in range(n))
        self.sock.sendall(hdr + mask + enc)

    def send_json(self, obj):
        self._send_frame(
            json.dumps(obj, separators=(",", ":")).encode("utf-8")
        )

    def recv_json(self, timeout=None):
        if timeout is not None:
            self.sock.settimeout(timeout)
        while True:
            b1, b2 = self._read_exact(2)
            opcode = b1 & 0x0F
            n = b2 & 0x7F
            if n == 126:
                n = struct.unpack(">H", self._read_exact(2))[0]
            elif n == 127:
                n = struct.unpack(">Q", self._read_exact(8))[0]
            mask = self._read_exact(4) if (b2 & 0x80) else None
            payload = self._read_exact(n)
            if mask:
                payload = bytes(
                    payload[i] ^ mask[i & 3] for i in range(n)
                )
            if opcode == 9:
                continue
            if opcode == 8:
                raise EOFError("WebSocket closed")
            if opcode != 1:
                continue
            return json.loads(payload.decode("utf-8", "replace"))

    def request(self, event, timeout=20, **params):
        self.ticket += 1
        ticket = self.ticket
        obj = {"event": event, "ticket": ticket}
        obj.update(params)
        self.send_json(obj)

        end = time.time() + timeout
        while time.time() < end:
            msg = self.recv_json(max(0.1, end-time.time()))
            if msg.get("ticket") != ticket:
                continue
            if msg.get("event") == "error":
                raise RuntimeError(msg.get("message", "debugger error"))
            if msg.get("event") == event:
                return msg
        raise TimeoutError(event)


def connect_debugger(port):
    errors = []
    for host in ("::1", "127.0.0.1"):
        ws = MiniWebSocket(host, port)
        try:
            ws.connect()
            return ws, host
        except Exception as e:
            errors.append(f"{host}: {e}")
            ws.close()
    raise RuntimeError("Debugger connection failed: " + "; ".join(errors))


def wait_for_story_native(hwnd, ws, pid, base, timeout=120):
    """
    No Windows keyboard injection at all.

    - Try PPSSPP native game.speed.set(fastForward=true).
    - Repeatedly inject the actual PSP Start button using
      input.buttons.press.
    - Poll the proven Story RAM slot.
    """
    speed_supported = False
    speed_response = None
    speed_error = None

    try:
        speed_response = ws.request(
            "game.speed.set",
            timeout=5,
            fastForward=True,
        )
        speed_supported = True
        log(f"[auto] PPSSPP native fast-forward ON: {speed_response}")
    except Exception as e:
        speed_error = str(e)
        log(f"[auto] Native fast-forward unavailable: {e}")

    start = time.time()
    presses = 0
    h = open_process(pid)

    try:
        while time.time() - start < timeout:
            cur = guest_read(h, base, STORY_GUEST, 10)
            if cur == "Story".encode("utf-16le"):
                if speed_supported:
                    try:
                        ws.request(
                            "game.speed.set",
                            timeout=5,
                            fastForward=False,
                        )
                    except Exception:
                        pass

                return {
                    "input_method": "PPSSPP WebSocket input.buttons.press",
                    "fast_forward_supported": speed_supported,
                    "fast_forward_response": speed_response,
                    "fast_forward_error": speed_error,
                    "start_presses": presses,
                    "elapsed_seconds": round(time.time() - start, 3),
                }

            try:
                ws.request(
                    "input.buttons.press",
                    timeout=5,
                    button="start",
                    duration=2,
                )
                presses += 1
            except Exception as e:
                raise RuntimeError(
                    f"Native PSP Start injection failed: {e}"
                )

            time.sleep(0.15)

    finally:
        if speed_supported:
            try:
                ws.request(
                    "game.speed.set",
                    timeout=3,
                    fastForward=False,
                )
            except Exception:
                pass
        kernel32.CloseHandle(h)

    raise RuntimeError(f"Story not detected after {presses} native Start presses")


def verify_loaded(h, base, tex_sha1):
    count = struct.unpack(
        "<H",
        guest_read(
            h, base,
            STREAM19_RAM_BASE + TMR_COUNT_OFF,
            2
        )
    )[0]
    ptr = struct.unpack(
        "<I",
        guest_read(
            h, base,
            STREAM19_RAM_BASE + TMR_GLYPH_PTR_OFF,
            4
        )
    )[0]
    d5 = struct.unpack(
        "<I",
        guest_read(
            h, base,
            STREAM19_RAM_BASE
            + TMR_PAGE_TABLE_OFF
            + TEST_HIGH * 4,
            4
        )
    )[0]
    mv = struct.unpack(
        "<H",
        guest_read(
            h, base,
            d5 + TEST_LOW * 2,
            2
        )
    )[0]

    tex = guest_read(
        h, base,
        TMR_TEX_ADDR,
        TMR_TEX_SIZE
    )
    got_sha1 = sha1_bytes(tex)

    expected_ptr = (
        STREAM19_RAM_BASE
        + TMR_NEW_GLYPH_ARRAY_OFF
    )
    expected_d5 = (
        STREAM19_RAM_BASE
        + TMR_NEW_D5_PAGE_OFF
    )

    # Crucial Stage21 check: inspect Magma's transformed runtime GE commands.
    runtime_desc = guest_read(
        h, base, TMR_RUNTIME_DESC, 12
    )
    rt_a0, rt_a8, rt_b8 = struct.unpack(
        "<III", runtime_desc
    )

    expected_a0 = (
        0xA0000000
        | (TMR_TEX_ADDR & 0x00FFFFFF)
    )
    expected_a8 = (
        0xA8000000
        | (((TMR_TEX_ADDR >> 24) & 0x0F) << 16)
        | TMR_TEX_W
    )
    expected_b8 = 0xB8000907

    errors = []

    if count != NEW_GLYPH_COUNT:
        errors.append(
            f"count={count} expected={NEW_GLYPH_COUNT}"
        )
    if ptr != expected_ptr:
        errors.append(
            f"glyph_ptr=0x{ptr:08X} "
            f"expected=0x{expected_ptr:08X}"
        )
    if d5 != expected_d5:
        errors.append(
            f"D5=0x{d5:08X} "
            f"expected=0x{expected_d5:08X}"
        )
    if mv != NEW_GLYPH_INDEX:
        errors.append(
            f"D55C={mv} expected={NEW_GLYPH_INDEX}"
        )
    if got_sha1 != tex_sha1:
        errors.append(
            f"texture_sha1={got_sha1} "
            f"expected={tex_sha1}"
        )
    if (
        rt_a0 != expected_a0
        or rt_a8 != expected_a8
        or rt_b8 != expected_b8
    ):
        errors.append(
            "runtime_descriptor="
            f"[0x{rt_a0:08X},0x{rt_a8:08X},0x{rt_b8:08X}] "
            "expected="
            f"[0x{expected_a0:08X},0x{expected_a8:08X},"
            f"0x{expected_b8:08X}]"
        )

    info = {
        "glyph_count": count,
        "glyph_ptr": f"0x{ptr:08X}",
        "D5_page": f"0x{d5:08X}",
        "D55C_map": mv,
        "texture_address":
            f"0x{TMR_TEX_ADDR:08X}",
        "texture_sha1": got_sha1,
        "runtime_descriptor_address":
            f"0x{TMR_RUNTIME_DESC:08X}",
        "runtime_A0": f"0x{rt_a0:08X}",
        "runtime_A8": f"0x{rt_a8:08X}",
        "runtime_B8": f"0x{rt_b8:08X}",
        "expected_runtime_A0":
            f"0x{expected_a0:08X}",
        "expected_runtime_A8":
            f"0x{expected_a8:08X}",
        "expected_runtime_B8":
            f"0x{expected_b8:08X}",
        "runtime_descriptor_matches":
            not any(
                x.startswith("runtime_descriptor=")
                for x in errors
            ),
    }

    # Always save the diagnostic even if validation fails.
    probe = ANALYSIS_DIR / "stage21_runtime_descriptor.json"
    probe.write_text(
        json.dumps(info, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    if errors:
        raise RuntimeError(
            "Disc structures/runtime descriptor validation faileLOCAL_PATH"
            + "\n".join(errors)
        )

    return info




def make_zip(path: Path, entries):
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for src, arc in entries:
            p = Path(src)
            if p.exists():
                z.write(p, arc)


def main():
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)

    script_dir = Path(__file__).resolve().parent
    helper = script_dir / "capture_ppsspp.ps1"
    expanded = (
        script_dir / "tmr18_expanded_128x512_swizzled.bin"
    ).read_bytes()
    expanded_sha1 = sha1_bytes(expanded)

    source_iso = find_original_iso()
    exe = find_ppsspp_exe()
    cfg = write_append_config()
    requested_port = choose_free_port()

    report = {
        "stage": 21,
        "purpose":
            "Use MDI stream22 texture with Magma-native relocation descriptor and verify transformed runtime GE commands",
        "source_iso": str(source_iso),
        "test_iso": str(TEST_ISO),
        "ppsspp_exe": str(exe),
        "texture_replacement_enabled": False,
        "texture_storage": {
            "mdi_stream": STREAM22_INDEX,
            "runtime_address": f"0x{TMR_TEX_ADDR:08X}",
            "bytes": TMR_TEX_SIZE,
            "sha1": expanded_sha1,
        },
    }

    log("=" * 80)
    log("BIA Stage 21 - relocated descriptor expanded TMR")
    log("=" * 80)

    if TEST_ISO.exists():
        TEST_ISO.unlink()
    shutil.copy2(source_iso, TEST_ISO)

    _, mdi = iso_read_file(source_iso, TARGET_MDI)
    _, dsl = iso_read_file(source_iso, TARGET_DSL)

    if sha1_bytes(mdi) != EXPECTED_MDI_SHA1:
        raise RuntimeError("MDI SHA1 mismatch")
    if sha1_bytes(dsl) != EXPECTED_DSL_SHA1:
        raise RuntimeError("DSL SHA1 mismatch")

    patched_mdi, mdi_info = patch_mdi(mdi, expanded)
    patched_dsl, dsl_info = patch_dsl_descriptor(dsl)

    # MDI grows because stream22 now contains real texture data.
    mdi_iso_info = append_iso_file_and_repoint(
        TEST_ISO, TARGET_MDI, patched_mdi
    )

    # DSL remains exact same size: descriptor-only patch.
    overwrite_iso_same_size(TEST_ISO, TARGET_DSL, patched_dsl)

    report["mdi_patch"] = mdi_info
    report["dsl_descriptor_patch"] = dsl_info
    report["mdi_iso_relocation"] = mdi_iso_info

    _, mdi_rb = iso_read_file(TEST_ISO, TARGET_MDI)
    _, dsl_rb = iso_read_file(TEST_ISO, TARGET_DSL)
    if mdi_rb != patched_mdi or dsl_rb != patched_dsl:
        raise RuntimeError("ISO read-back mismatch")
    report["iso_readback_verified"] = True

    before_png = ANALYSIS_DIR / "stage21_before.png"
    after_png = ANALYSIS_DIR / "stage21_after.png"
    ppsspp_log = ANALYSIS_DIR / "stage21_ppsspp_debug.log"
    report_path = ANALYSIS_DIR / "stage21_report.json"

    # Fresh PPSSPP.
    old = user32.FindWindowW("PPSSPPWnd", None)
    if old:
        user32.SendMessageW(old, 0x0010, 0, 0)
        time.sleep(1)

    cmd = [
        str(exe),
        "-d",
        f"--log={ppsspp_log}",
        "--windowed",
        f"--appendconfig={cfg}",
        f"--debugger={requested_port}",
        str(TEST_ISO),
    ]
    subprocess.Popen(cmd)

    hwnd = find_ppsspp_hwnd(30)
    if not hwnd:
        raise RuntimeError("PPSSPP window did not appear")

    # Wait until PID/base are available.
    end = time.time() + 30
    pid = base = None
    while time.time() < end:
        try:
            pid, base = get_pid_base(hwnd)
            if pid and base:
                break
        except Exception:
            pass
        time.sleep(0.2)
    if not pid or not base:
        raise RuntimeError("PPSSPP memory base not available")

    actual_port = wait_for_actual_debugger_port(ppsspp_log, 30)
    ws, host = connect_debugger(actual_port)

    try:
        report["debugger_host"] = host
        report["debugger_port"] = actual_port

        try:
            report["version"] = ws.request(
                "version",
                timeout=5,
                name="bia-stage20",
                version="1",
            )
        except Exception as e:
            report["version_error"] = str(e)

        boot_info = wait_for_story_native(hwnd, ws, pid, base, 120)
        report["boot_automation"] = boot_info
        report["menu_detected"] = True

        capture(hwnd, before_png, helper)

        h = open_process(pid)
        restores = []
        try:
            loaded = verify_loaded(h, base, expanded_sha1)
            report["loaded_font"] = loaded

            old_story = guest_read(h, base, STORY_GUEST, 10)
            if old_story != "Story".encode("utf-16le"):
                raise RuntimeError("Story slot mismatch before text test")

            restores.append((STORY_GUEST, old_story))
            test = struct.pack(
                "<5H", TEST_CP, TEST_CP, TEST_CP, TEST_CP, TEST_CP
            )
            guest_write(h, base, STORY_GUEST, test)

            time.sleep(1.0)
            capture(hwnd, after_png, helper)
            report["runtime_patch_scope"] = "Story UTF-16 text only"

        finally:
            for guest, old_bytes in reversed(restores):
                try:
                    guest_write(h, base, guest, old_bytes)
                except Exception:
                    pass
            kernel32.CloseHandle(h)

    finally:
        ws.close()

    report["completed"] = True
    report["expected_before"] = "normal Story/Skirmish/Options/Profile"
    report["expected_after"] = "한한한한한; other menu labels normal"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    upload = LOG_DIR / "bia_stage21_upload.zip"
    make_zip(upload, [
        (report_path, "stage21_report.json"),
        (before_png, "stage21_before.png"),
        (after_png, "stage21_after.png"),
        (ppsspp_log, "stage21_ppsspp_debug.log"),
        (cfg, "stage21_append.ini"),
        (
            ANALYSIS_DIR / "stage21_runtime_descriptor.json",
            "stage21_runtime_descriptor.json"
        ),
    ])

    log()
    log("=" * 80)
    log("Stage 21 complete")
    log(f"Upload: {upload}")
    log("=" * 80)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)

        failure = ANALYSIS_DIR / "FAILURE.txt"
        failure.write_text(traceback.format_exc(), encoding="utf-8")

        fail_zip = LOG_DIR / "fail_bia_stage21_upload.zip"
        try:
            make_zip(fail_zip, [
                (failure, "FAILURE.txt"),
                (ANALYSIS_DIR / "stage21_report.json", "stage21_report.json"),
                (ANALYSIS_DIR / "stage21_before.png", "stage21_before.png"),
                (ANALYSIS_DIR / "stage21_after.png", "stage21_after.png"),
                (ANALYSIS_DIR / "stage21_ppsspp_debug.log",
                 "stage21_ppsspp_debug.log"),
                (ANALYSIS_DIR / "stage21_append.ini", "stage21_append.ini"),
                (
                    ANALYSIS_DIR / "stage21_runtime_descriptor.json",
                    "stage21_runtime_descriptor.json"
                ),
            ])
        except Exception:
            pass

        print()
        print("=" * 80)
        print("STAGE 21 FAILED")
        print(f"Failure ZIP: {fail_zip}")
        print("=" * 80)
        traceback.print_exc()
        raise
