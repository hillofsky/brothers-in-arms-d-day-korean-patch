#!/usr/bin/env python3
from __future__ import annotations

import atexit
import base64
import ctypes
from ctypes import wintypes
import hashlib
import json
import re
import os
import secrets
import shutil
import socket
import struct
import subprocess
import time
import traceback
import threading
import zipfile
import zlib
from pathlib import Path

ROOT = Path(r"PROJECT_ROOT")
LOG_DIR = ROOT / "log"
ANALYSIS_DIR = ROOT / "analysis" / "stage32_permanent_dsx"
TEST_ISO = ROOT / "BIA_STAGE32_PERMANENT_DSX_TEST.iso"
STAGE21_ISO = ROOT / "BIA_STAGE21_RELOC_DESCRIPTOR_TEST.iso"
STAGE20_ISO = ROOT / "BIA_STAGE20_MDI_TEXTURE_TEST.iso"

TARGET_MDI = ["PSP_GAME", "USRDIR", "SYSTEM", "ON_MEMU_O.MDI"]
TARGET_DSL = ["PSP_GAME", "USRDIR", "SYSTEM", "ON_MEMU.DSL"]
TARGET_DSX = ["PSP_GAME", "USRDIR", "SYSTEM", "ON_MEMU.DSX"]

EXPECTED_MDI_SHA1 = "22de1f889d1617199a3e21d4a1f63fcaf87b944a"
EXPECTED_DSL_SHA1 = "e009f2e259861f60d0aeeb03f46422d5473b88aa"
EXPECTED_DSX_SHA1 = "ba7c719245fb2b85c42f285f5aec9db40a800523"

# Confirmed original TMR descriptor.
TMR_DESC_OFF = 0x175137

# Stage30 exact TMR relocation entry in original ON_MEMU.DSL.
TMR_RELOC_ENTRY_OFF = 0x169E12
TMR_RELOC_OLD = (0x40006580, 0x00000080, 0x4011BF40)
TMR_RELOC_BASE2 = 0x08464000
TMR_B8_SOURCE_OFF = TMR_DESC_OFF + 8


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

# Stage27 PPSSPP log already proved this exact write PC.
KNOWN_WRITER_PC = 0x0881BF60
# Stage27 log proved the real descriptor relocation writes:
#   0x08C3CAA8 sw a3,0(a2)  -> TEXADDR0
#   0x08C3CAC4 sw a2,0(a3)  -> TEXBUFWIDTH0
#
# The writer uses the uncached/mirrored 0x48xxxxxx alias.
RELOC_BREAK_PC = 0x08C3CAA8
RELOC_DEST_ALIAS = 0x48E693C0
TRACE_BREAK_PC = RELOC_BREAK_PC
TRACE_CONDITION = "a2 == 0x48E693C0 && a3 == 0xA057FF40"
DECODER_FUNC_START = 0x0881BD20
DECODER_FUNC_END   = 0x0881C2D4
DECODER_SAVED_RA_SP_OFF = 0x310
DECODER_SAVED_S4_SP_OFF = 0x308

GE_DUMP_START = 0x08400000
GE_DUMP_SIZE  = 0x00064000
SUBLIST_DUMP_START = 0x08E00000
SUBLIST_DUMP_SIZE  = 0x00080000
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
PROCESS_TERMINATE = 0x0001

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
user32 = ctypes.WinDLL("user32", use_last_error=True)

user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
user32.FindWindowW.restype = wintypes.HWND
user32.SendMessageW.argtypes = [
    wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM
]
user32.SendMessageW.restype = ctypes.c_ssize_t
user32.PostMessageW.argtypes = [
    wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM
]
user32.PostMessageW.restype = wintypes.BOOL
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
kernel32.TerminateProcess.argtypes = [
    wintypes.HANDLE, wintypes.UINT
]
kernel32.TerminateProcess.restype = wintypes.BOOL


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
    """
    Permanent Stage31 MDI patch.

    Stage26 proved the correct real-128x512 UV convention:
      - existing Latin glyph V values must remain EXACTLY original
      - new Korean glyph must use renderer-space V ~= 256.5..272.5

    Earlier Stage19-25 divided all V coordinates by 2, which caused the
    garbled menu.  Stage31 never performs that division.
    """
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

    if any(dec19[STATIC_HOLE_START:STATIC_HOLE_END]):
        raise RuntimeError("stream19 static hole not zero")

    old_count = struct.unpack_from("<H", dec19, TMR_COUNT_OFF)[0]
    old_ptr = struct.unpack_from("<I", dec19, TMR_GLYPH_PTR_OFF)[0]
    if old_count != OLD_GLYPH_COUNT or old_ptr != 0x09723FD8:
        raise RuntimeError(
            f"Unexpected TMR font object count={old_count} "
            f"ptr=0x{old_ptr:08X}"
        )

    old_ptr_off = old_ptr - STREAM19_RAM_BASE

    # Copy all 151 original glyph records UNCHANGED.
    recs = bytearray(
        dec19[
            old_ptr_off:
            old_ptr_off + OLD_GLYPH_COUNT * GLYPH_REC_SIZE
        ]
    )

    array_end = TMR_NEW_GLYPH_ARRAY_OFF + len(recs)
    if array_end > TMR_NEW_D5_PAGE_OFF:
        raise RuntimeError("glyph array overlaps D5 page")

    dec19[
        TMR_NEW_GLYPH_ARRAY_OFF:
        TMR_NEW_GLYPH_ARRAY_OFF + len(recs)
    ] = recs

    # New #151 uses A's metrics but points below the original 256px atlas.
    #
    # The renderer multiplies these normalized record values by its original
    # 256-unit UV scale before the GE sees integer texel coordinates.
    # Therefore lower-half 512-atlas texels use V > 1.0 here.
    A_MAP_VALUE = 34
    a_off = old_ptr_off + A_MAP_VALUE * GLYPH_REC_SIZE
    new_rec = bytearray(dec19[a_off:a_off+GLYPH_REC_SIZE])
    struct.pack_into("<H", new_rec, 0, TEST_CP)
    struct.pack_into("<f", new_rec, 8,  0.5 / 128.0)
    struct.pack_into("<f", new_rec, 12, 256.5 / 256.0)
    struct.pack_into("<f", new_rec, 16, 17.5 / 128.0)
    struct.pack_into("<f", new_rec, 20, 272.5 / 256.0)

    nr = TMR_NEW_GLYPH_ARRAY_OFF + NEW_GLYPH_INDEX * GLYPH_REC_SIZE
    dec19[nr:nr+GLYPH_REC_SIZE] = new_rec

    # Independent U+D5xx lookup page.
    page = bytearray(512)
    struct.pack_into("<H", page, TEST_LOW * 2, NEW_GLYPH_INDEX)
    dec19[TMR_NEW_D5_PAGE_OFF:TMR_NEW_D5_PAGE_OFF+512] = page

    # Redirect TMR font object to expanded record array/page.
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

    if len(expanded_tex) != TMR_TEX_SIZE:
        raise RuntimeError("expanded texture wrong size")

    # Entire 128x512 CLUT4 TMR atlas lives in proven-unused stream22.
    dec22[:len(expanded_tex)] = expanded_tex

    rebuilt = rebuild_mdi(original, {
        STREAM19_INDEX: bytes(dec19),
        STREAM22_INDEX: bytes(dec22),
    })

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
        raise RuntimeError(
            f"Stage31 MDI rebuild verification failed: {checks}"
        )

    # Verify the relocated original Latin records are byte-for-byte original.
    relocated_records = v19[
        TMR_NEW_GLYPH_ARRAY_OFF:
        TMR_NEW_GLYPH_ARRAY_OFF + OLD_GLYPH_COUNT * GLYPH_REC_SIZE
    ]
    original_records = s19["decoded"][
        old_ptr_off:
        old_ptr_off + OLD_GLYPH_COUNT * GLYPH_REC_SIZE
    ]
    if relocated_records != original_records:
        raise RuntimeError("Latin glyph records changed unexpectedly")

    nr_bytes = v19[nr:nr+GLYPH_REC_SIZE]
    new_v0 = struct.unpack_from("<f", nr_bytes, 12)[0]
    new_v1 = struct.unpack_from("<f", nr_bytes, 20)[0]

    return rebuilt, {
        "stream19_old_csize": s19["csize"],
        "stream19_new_csize": vs[STREAM19_INDEX]["csize"],
        "stream22_old_csize": s22["csize"],
        "stream22_new_csize": vs[STREAM22_INDEX]["csize"],
        "new_glyph_ptr": f"0x{expected['glyph_ptr']:08X}",
        "new_D5_page": f"0x{expected['D5_ptr']:08X}",
        "latin_records_unchanged": True,
        "korean_record_v0": new_v0,
        "korean_record_v1": new_v1,
        "texture_runtime_address": f"0x{TMR_TEX_ADDR:08X}",
        "texture_sha1": expected["texture_sha1"],
    }




def patch_dsl_descriptor(original: bytes):
    """
    Permanent Stage31 DSL patch based on Stage30's exact runtime trace.

    Stage30 captured relocation entry #89:
      file offset 0x169E12
      e0 = 0x40006580
      e1 = 0x00000080
      e2 = 0x4011BF40

    Engine relocation:
      address = 0x08464000 + (e2 & 0x3FFFFFFF)
              = 0x0857FF40

    Target:
      0x0987D020

    Therefore:
      new offset = 0x0987D020 - 0x08464000 = 0x01419020
      new e2     = 0x40000000 | 0x01419020 = 0x41419020

    A0/A8 in the old guessed descriptor at 0x175137 are deliberately left
    untouched.  Only its B8 TEXSIZE word is changed as the remaining
    source-data candidate for 128x512.
    """
    patched = bytearray(original)

    old_entry = struct.unpack_from(
        "<III", original, TMR_RELOC_ENTRY_OFF
    )
    if old_entry != TMR_RELOC_OLD:
        raise RuntimeError(
            "TMR relocation entry mismatch at "
            f"0x{TMR_RELOC_ENTRY_OFF:X}: "
            + "/".join(f"{x:08X}" for x in old_entry)
        )

    delta = TMR_TEX_ADDR - TMR_RELOC_BASE2
    if delta < 0 or delta >= 0x40000000:
        raise RuntimeError("TMR relocation target outside base2 range")

    new_e2 = 0x40000000 | delta
    expected_e2 = 0x41419020
    if new_e2 != expected_e2:
        raise RuntimeError(
            f"Unexpected calculated relocation e2 0x{new_e2:08X}"
        )

    struct.pack_into(
        "<I", patched, TMR_RELOC_ENTRY_OFF + 8, new_e2
    )

    # Remaining GE TEXSIZE command candidate.
    old_b8 = struct.unpack_from(
        "<I", original, TMR_B8_SOURCE_OFF
    )[0]
    if old_b8 != 0xB8000807:
        raise RuntimeError(
            f"TMR B8 source mismatch: 0x{old_b8:08X}"
        )
    struct.pack_into(
        "<I", patched, TMR_B8_SOURCE_OFF, 0xB8000907
    )

    # Make sure the exact relocation triple is unique in the source DSL.
    old_bytes = struct.pack("<III", *TMR_RELOC_OLD)
    occurrence_count = original.count(old_bytes)
    if occurrence_count != 1:
        raise RuntimeError(
            f"Expected unique TMR relocation entry, found {occurrence_count}"
        )

    # Verify patched bytes.
    rb_entry = struct.unpack_from(
        "<III", patched, TMR_RELOC_ENTRY_OFF
    )
    rb_b8 = struct.unpack_from(
        "<I", patched, TMR_B8_SOURCE_OFF
    )[0]

    expected_runtime = descriptor_words_for_expanded_tmr()

    return bytes(patched), {
        "relocation_file_offset": f"0x{TMR_RELOC_ENTRY_OFF:X}",
        "old_entry": [f"0x{x:08X}" for x in old_entry],
        "new_entry": [f"0x{x:08X}" for x in rb_entry],
        "relocation_base2": f"0x{TMR_RELOC_BASE2:08X}",
        "target_runtime_texture": f"0x{TMR_TEX_ADDR:08X}",
        "new_e2": f"0x{new_e2:08X}",
        "unique_old_entry_occurrences": occurrence_count,
        "b8_source_offset": f"0x{TMR_B8_SOURCE_OFF:X}",
        "old_B8": f"0x{old_b8:08X}",
        "new_B8": f"0x{rb_b8:08X}",
        "source_A0_A8_left_untouched": True,
        "expected_runtime_descriptor": [
            f"0x{x:08X}" for x in expected_runtime
        ],
    }





# ---------------- DSX ----------------

def parse_dsx(data: bytes):
    """
    ON_MEMU.DSX is the runtime compressed form of ON_MEMU.DSL.

    Layout:
      repeated:
        u32 uncompressed_size
        u32 compressed_size
        zlib payload

    Concatenating all decompressed blocks reproduces ON_MEMU.DSL exactly.
    """
    blocks = []
    pos = 0
    logical_off = 0

    while pos + 8 <= len(data):
        usize, csize = struct.unpack_from("<II", data, pos)
        zpos = pos + 8

        if (
            usize <= 0
            or csize <= 0
            or zpos + csize > len(data)
        ):
            raise RuntimeError(
                f"DSX parse failed at 0x{pos:X}: "
                f"usize={usize} csize={csize}"
            )

        comp = data[zpos:zpos+csize]
        dec = zlib.decompress(comp)
        if len(dec) != usize:
            raise RuntimeError(
                f"DSX block size mismatch at 0x{pos:X}: "
                f"header={usize}, decoded={len(dec)}"
            )

        blocks.append({
            "index": len(blocks),
            "header_off": pos,
            "zpos": zpos,
            "usize": usize,
            "csize": csize,
            "logical_off": logical_off,
            "decoded": dec,
            "original_comp": comp,
        })

        logical_off += usize
        pos = zpos + csize

    if pos != len(data):
        raise RuntimeError(
            f"DSX parse did not end at EOF: "
            f"0x{pos:X} / 0x{len(data):X}"
        )

    return blocks


def dsx_logical_bytes(data: bytes):
    return b"".join(
        b["decoded"] for b in parse_dsx(data)
    )


def rebuild_dsx_from_logical(original_dsx: bytes, logical: bytes):
    blocks = parse_dsx(original_dsx)
    original_logical = b"".join(
        b["decoded"] for b in blocks
    )

    if len(logical) != len(original_logical):
        raise RuntimeError(
            "Patched DSL logical size differs from DSX logical size"
        )

    out = bytearray()
    changed = []

    for b in blocks:
        lo = b["logical_off"]
        hi = lo + b["usize"]
        wanted = logical[lo:hi]

        if wanted == b["decoded"]:
            comp = b["original_comp"]
        else:
            comp = zlib.compress(wanted, 9)
            changed.append({
                "index": b["index"],
                "logical_start": f"0x{lo:X}",
                "logical_end": f"0x{hi:X}",
                "old_csize": b["csize"],
                "new_csize": len(comp),
            })

        out += struct.pack(
            "<II", len(wanted), len(comp)
        )
        out += comp

    rebuilt = bytes(out)
    rb_logical = dsx_logical_bytes(rebuilt)
    if rb_logical != logical:
        raise RuntimeError(
            "Rebuilt DSX does not decompress to patched DSL"
        )

    return rebuilt, {
        "block_count": len(blocks),
        "old_size": len(original_dsx),
        "new_size": len(rebuilt),
        "changed_blocks": changed,
        "logical_size": len(logical),
        "logical_sha1":
            hashlib.sha1(logical).hexdigest(),
        "rebuilt_sha1":
            hashlib.sha1(rebuilt).hexdigest(),
        "logical_matches_patched_dsl": True,
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
    cfg = ANALYSIS_DIR / "stage32_append.ini"
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


def record_gpu_frame(ws, out_path: Path):
    """
    Ask PPSSPP itself to record the next complete GPU frame.
    PPSSPP returns the .ppdmp as a base64 data URI.
    """
    log(f"[auto] Recording GPU frame -> {out_path.name}")
    rec = ws.request(
        "gpu.record.dump",
        timeout=90,
    )
    uri = rec.get("uri", "")
    prefix = "data:application/octet-stream;base64,"
    if not uri.startswith(prefix):
        raise RuntimeError(
            "gpu.record.dump returned no ppdmp data URI"
        )

    raw = base64.b64decode(
        uri[len(prefix):],
        validate=False,
    )
    if not raw.startswith(b"PPSSPPGE"):
        raise RuntimeError(
            f"Unexpected ppdmp magic: {raw[:16]!r}"
        )

    out_path.write_bytes(raw)

    info = {
        "path": str(out_path),
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "magic": raw[:8].decode("ascii", "replace"),
    }
    if len(raw) >= 12:
        info["version"] = struct.unpack_from("<I", raw, 8)[0]

    log(
        f"[auto] GPU frame recorded: "
        f"{len(raw)} bytes, sha256={info['sha256']}"
    )
    return info


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
        self.unsolicited = []

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

    def _recv_text_message(self, timeout=None):
        """
        Receive one complete WebSocket text message.

        PPSSPP's gpu.record.dump response contains a large base64 data URI.
        It is commonly split across RFC6455 continuation frames.  Stage25
        incorrectly parsed the first fragment as a complete JSON object.

        This implementation:
          - handles fragmented text messages (opcode 1 + opcode 0)
          - handles ping/pong control frames interleaved between fragments
          - handles optional server masking
          - rejects unexpected binary messages
        """
        if timeout is not None:
            self.sock.settimeout(timeout)

        assembled = bytearray()
        started = False

        while True:
            b1, b2 = self._read_exact(2)
            fin = (b1 & 0x80) != 0
            opcode = b1 & 0x0F
            masked = (b2 & 0x80) != 0
            n = b2 & 0x7F

            if n == 126:
                n = struct.unpack(">H", self._read_exact(2))[0]
            elif n == 127:
                n = struct.unpack(">Q", self._read_exact(8))[0]

            mask = self._read_exact(4) if masked else None
            payload = self._read_exact(n)

            if mask:
                payload = bytes(
                    payload[i] ^ mask[i & 3]
                    for i in range(n)
                )

            # Ping: reply with a masked Pong and keep receiving the message.
            if opcode == 9:
                pong_mask = secrets.token_bytes(4)
                plen = len(payload)
                if plen < 126:
                    hdr = bytes([0x8A, 0x80 | plen])
                elif plen <= 0xFFFF:
                    hdr = (
                        bytes([0x8A, 0x80 | 126])
                        + struct.pack(">H", plen)
                    )
                else:
                    hdr = (
                        bytes([0x8A, 0x80 | 127])
                        + struct.pack(">Q", plen)
                    )
                enc = bytes(
                    payload[i] ^ pong_mask[i & 3]
                    for i in range(plen)
                )
                self.sock.sendall(
                    hdr + pong_mask + enc
                )
                continue

            if opcode == 10:  # Pong
                continue

            if opcode == 8:
                raise EOFError(
                    "WebSocket server closed connection"
                )

            if opcode == 1:  # Text, first fragment.
                assembled = bytearray(payload)
                started = True
            elif opcode == 0 and started:  # Continuation.
                assembled.extend(payload)
            elif opcode == 2:
                # PPSSPP debugger JSON protocol should not answer with
                # a binary message for these events.
                if fin:
                    raise RuntimeError(
                        "Unexpected binary WebSocket message"
                    )
                continue
            else:
                # Ignore unrelated/unexpected frame types.
                if fin and not started:
                    continue

            if fin and started:
                return bytes(assembled)

    def recv_json(self, timeout=None):
        raw = self._recv_text_message(timeout)

        try:
            return json.loads(
                raw.decode("utf-8", "strict")
            )
        except Exception as e:
            # Persist a small diagnostic without writing the huge base64
            # response into the failure ZIP.
            try:
                diag = {
                    "error": repr(e),
                    "message_bytes": len(raw),
                    "prefix": raw[:512].decode(
                        "utf-8", "replace"
                    ),
                    "suffix": raw[-512:].decode(
                        "utf-8", "replace"
                    ),
                }
                p = (
                    ANALYSIS_DIR
                    / "stage25b_websocket_parse_failure.json"
                )
                p.write_text(
                    json.dumps(
                        diag,
                        ensure_ascii=False,
                        indent=2,
                    ),
                    encoding="utf-8",
                )
            except Exception:
                pass
            raise


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
                self.unsolicited.append(msg)
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


def inspect_loaded(h, base, tex_sha1):
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
        h, base, TMR_TEX_ADDR, TMR_TEX_SIZE
    )
    got_sha1 = sha1_bytes(tex)

    expected_ptr = (
        STREAM19_RAM_BASE + TMR_NEW_GLYPH_ARRAY_OFF
    )
    expected_d5 = (
        STREAM19_RAM_BASE + TMR_NEW_D5_PAGE_OFF
    )

    info = {
        "glyph_count": count,
        "glyph_ptr": f"0x{ptr:08X}",
        "expected_glyph_ptr": f"0x{expected_ptr:08X}",
        "D5_page": f"0x{d5:08X}",
        "expected_D5_page": f"0x{expected_d5:08X}",
        "D55C_map": mv,
        "texture_address": f"0x{TMR_TEX_ADDR:08X}",
        "texture_sha1": got_sha1,
        "texture_expected_sha1": tex_sha1,
    }

    if (
        count != NEW_GLYPH_COUNT
        or ptr != expected_ptr
        or d5 != expected_d5
        or mv != NEW_GLYPH_INDEX
        or got_sha1 != tex_sha1
    ):
        raise RuntimeError(
            "Patched MDI/texture did not load correctly: "
            + json.dumps(info, ensure_ascii=False)
        )

    return info


def descriptor_words_for_expanded_tmr():
    return (
        0xA0000000 | (TMR_TEX_ADDR & 0x00FFFFFF),
        0xA8000000
        | (((TMR_TEX_ADDR >> 24) & 0x0F) << 16)
        | TMR_TEX_W,
        0xB8000907,
    )


def pre_menu_descriptor_watcher(pid, base, stop_event, stats):
    """
    Patch the proven transformed TMR descriptor AS SOON AS it appears,
    before the first Story menu is constructed.

    Stage22C patched the same address only after the menu already existed.
    """
    old = (0xA057FF40, 0xA8080080, 0xB8000807)
    new = descriptor_words_for_expanded_tmr()

    first_seen = None
    first_patch = None
    patches = 0
    reads = 0
    observed = {}

    h = open_process(pid)
    try:
        while not stop_event.is_set():
            try:
                raw = guest_read(
                    h, base, TMR_RUNTIME_DESC, 12
                )
                cur = struct.unpack("<III", raw)
                reads += 1

                key = "/".join(f"{x:08X}" for x in cur)
                observed[key] = observed.get(key, 0) + 1

                if cur == old:
                    if first_seen is None:
                        first_seen = time.time()

                    guest_write(
                        h, base, TMR_RUNTIME_DESC,
                        struct.pack("<III", *new)
                    )
                    patches += 1
                    if first_patch is None:
                        first_patch = time.time()

                # If loader writes only part of it at a time, repair any
                # old component only when the remaining words look like the
                # original/new TMR descriptor family.
                elif (
                    cur[0] in (old[0], new[0])
                    and cur[1] in (old[1], new[1])
                    and cur[2] in (old[2], new[2])
                    and cur != new
                ):
                    guest_write(
                        h, base, TMR_RUNTIME_DESC,
                        struct.pack("<III", *new)
                    )
                    patches += 1
                    if first_patch is None:
                        first_patch = time.time()

            except Exception:
                pass

            time.sleep(0.002)

    finally:
        kernel32.CloseHandle(h)

    stats["reads"] = reads
    stats["patches"] = patches
    stats["first_seen_epoch"] = first_seen
    stats["first_patch_epoch"] = first_patch
    stats["observed_descriptors"] = observed
    stats["target"] = [
        f"0x{x:08X}" for x in new
    ]


def dump_runtime_regions(h, base):
    ge = guest_read(
        h, base, GE_DUMP_START, GE_DUMP_SIZE
    )
    sub = guest_read(
        h, base, SUBLIST_DUMP_START, SUBLIST_DUMP_SIZE
    )

    ge_path = ANALYSIS_DIR / "stage27_ge_08400000.bin"
    sub_path = ANALYSIS_DIR / "stage27_sublist_08e00000.bin"
    ge_path.write_bytes(ge)
    sub_path.write_bytes(sub)

    # Inventory interesting words/pointers for the next step.
    interesting = {
        "A057FF40": 0xA057FF40,
        "A087D020": 0xA087D020,
        "A8080080": 0xA8080080,
        "A8090080": 0xA8090080,
        "B8000807": 0xB8000807,
        "B8000907": 0xB8000907,
        "ptr_08E693C0": 0x08E693C0,
        "ptr_08E08D40": 0x08E08D40,
    }

    inv = {}
    for name, value in interesting.items():
        pat = struct.pack("<I", value)
        hits = []

        for label, start, blob in [
            ("GE", GE_DUMP_START, ge),
            ("SUB", SUBLIST_DUMP_START, sub),
        ]:
            pos = 0
            while True:
                pos = blob.find(pat, pos)
                if pos < 0:
                    break
                if pos % 4 == 0:
                    hits.append(
                        f"{label}:0x{start+pos:08X}"
                    )
                pos += 1
        inv[name] = hits

    inv_path = ANALYSIS_DIR / "stage27_runtime_inventory.json"
    inv_path.write_text(
        json.dumps(inv, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    return ge_path, sub_path, inv_path, inv





def inspect_tmr_vertex_uv_samples(ppdmp_path: Path):
    """
    Lightweight ppdmp summary is intentionally not parsed here; the runtime
    proof below reads the actual glyph records directly.  This helper exists
    only to keep report structure explicit.
    """
    return {
        "note": (
            "Stage25B offline comparison proved the only deterministic "
            "vertex change in the two TMR18 draws was V texture coordinates "
            "being exactly halved."
        )
    }


def patch_loaded_tmr_uvs(h, base):
    """
    Stage25B GPU-frame comparison proved:
      - actual GE texture is correctly 128x512
      - actual TEXTURE0 payload is the exact expanded 0x8000-byte atlas
      - only TMR draw vertices differ deterministically from the good frame:
          U unchanged
          V_bad = floor(V_good / 2)

    Cause: Stage19+ divided every glyph-record V0/V1 by 2, which was correct
    for PPSSPP texture replacement but WRONG for a real 512-high GE texture.

    Fix proof:
      - multiply V0/V1 by 2 for all 152 relocated glyph records
      - this restores original Latin texel coordinates
      - new #151 becomes bottom-half V ~= 256.5..272.5 in renderer space
    """
    count_addr = STREAM19_RAM_BASE + TMR_COUNT_OFF
    ptr_addr = STREAM19_RAM_BASE + TMR_GLYPH_PTR_OFF

    count = struct.unpack(
        "<H", guest_read(h, base, count_addr, 2)
    )[0]
    ptr = struct.unpack(
        "<I", guest_read(h, base, ptr_addr, 4)
    )[0]

    if count != NEW_GLYPH_COUNT:
        raise RuntimeError(
            f"Expected {NEW_GLYPH_COUNT} TMR glyph records, got {count}"
        )

    expected_ptr = STREAM19_RAM_BASE + TMR_NEW_GLYPH_ARRAY_OFF
    if ptr != expected_ptr:
        raise RuntimeError(
            f"Unexpected TMR glyph ptr 0x{ptr:08X}, "
            f"expected 0x{expected_ptr:08X}"
        )

    size = count * GLYPH_REC_SIZE
    original = guest_read(h, base, ptr, size)
    fixed = bytearray(original)

    samples_before = []
    samples_after = []

    # Representative records: space-ish first record, A map record 34,
    # final original record 150, and new Korean record 151.
    sample_indices = {0, 34, 150, 151}

    for i in range(count):
        off = i * GLYPH_REC_SIZE

        v0 = struct.unpack_from("<f", fixed, off + 12)[0]
        v1 = struct.unpack_from("<f", fixed, off + 20)[0]

        if i in sample_indices:
            samples_before.append({
                "index": i,
                "codepoint": struct.unpack_from("<H", fixed, off)[0],
                "v0": v0,
                "v1": v1,
            })

        struct.pack_into("<f", fixed, off + 12, v0 * 2.0)
        struct.pack_into("<f", fixed, off + 20, v1 * 2.0)

        if i in sample_indices:
            samples_after.append({
                "index": i,
                "codepoint": struct.unpack_from("<H", fixed, off)[0],
                "v0": v0 * 2.0,
                "v1": v1 * 2.0,
            })

    guest_write(h, base, ptr, bytes(fixed))

    rb = guest_read(h, base, ptr, size)
    if rb != bytes(fixed):
        raise RuntimeError("TMR glyph UV write-back verification failed")

    # New Korean record should now address the lower half of the 512 atlas.
    nr_off = NEW_GLYPH_INDEX * GLYPH_REC_SIZE
    new_v0 = struct.unpack_from("<f", rb, nr_off + 12)[0]
    new_v1 = struct.unpack_from("<f", rb, nr_off + 20)[0]

    return ptr, original, {
        "glyph_count": count,
        "glyph_ptr": f"0x{ptr:08X}",
        "operation": "multiply every glyph record V0/V1 by 2.0",
        "samples_before": samples_before,
        "samples_after": samples_after,
        "korean_record_v0": new_v0,
        "korean_record_v1": new_v1,
        "expected_korean_texel_v_approx": [256.5, 272.5],
    }




def install_descriptor_pause_breakpoint(ws, timeout=45.0):
    """
    Pause only when the relocation function writes the exact original TMR
    TEXADDR0 word into the shared runtime descriptor slot.

      PC 0x08C3CAA8 : sw a3,0(a2)

    Stage27 log proves this writer later stores:
      0x48E693C0 -> first GE word
      0x48E693C4 -> second GE word

    Stage29 proved this destination is reused by other textures.  The
    exact TMR menu state is identified by both:
      a2 == 0x48E693C0
      a3 == 0xA057FF40
    """
    end = time.time() + timeout
    attempts = 0
    last_error = None

    while time.time() < end:
        attempts += 1
        try:
            result = ws.request(
                "cpu.breakpoint.add",
                timeout=3,
                address=RELOC_BREAK_PC,
                enabled=True,
                log=True,
                condition=TRACE_CONDITION,
                logFormat=(
                    "BIA_STAGE29 relocation: "
                    "pc={pc} a0={a0} a1={a1} a2={a2} a3={a3} "
                    "t1={t1} t3={t3} s0={s0}"
                ),
            )
            return {
                "attempts": attempts,
                "condition": TRACE_CONDITION,
                "break_pc": f"0x{RELOC_BREAK_PC:08X}",
                "destination_alias":
                    f"0x{RELOC_DEST_ALIAS:08X}",
                "result": result,
            }
        except Exception as e:
            last_error = str(e)
            if "CPU not started" in last_error:
                time.sleep(0.020)
                continue
            raise RuntimeError(
                f"cpu.breakpoint.add failed after {attempts} attempts: "
                f"{last_error}"
            )

    raise RuntimeError(
        f"CPU/debugger did not become ready within {timeout:.1f}s. "
        f"Last error: {last_error}"
    )


def remove_descriptor_pause_breakpoint(ws):
    try:
        return ws.request(
            "cpu.breakpoint.remove",
            timeout=10,
            address=TRACE_BREAK_PC,
        )
    except Exception as e:
        return {"error": str(e)}



def fire_and_forget(ws, event, **params):
    obj = {"event": event}
    obj.update(params)
    ws.send_json(obj)


def send_request_no_wait(ws, event, **params):
    """
    Send a normal ticketed debugger request but do NOT wait for its reply.

    This is required while a CPU breakpoint may fire as a side effect of
    input.buttons.press.  Stage28 blocked inside ws.request(buttons.press)
    exactly when the conditional decoder breakpoint paused the emulated CPU.

    The next ordinary ws.request() call will drain this old reply as an
    unsolicited ticket and continue waiting for its own response.
    """
    ws.ticket += 1
    ticket = ws.ticket
    obj = {"event": event, "ticket": ticket}
    obj.update(params)
    ws.send_json(obj)
    return ticket


def wait_cpu_running(ws, timeout=10.0):
    end = time.time() + timeout
    last = None
    while time.time() < end:
        last = ws.request("cpu.status", timeout=3)
        if not last.get("stepping", False):
            return last
        time.sleep(0.03)
    raise RuntimeError(f"CPU did not resume: {last}")


def regs_to_dict(resp):
    result = {}
    for cat in resp.get("categories", []):
        names = cat.get("registerNames") or []
        vals = cat.get("uintValues") or []
        for name, val in zip(names, vals):
            result[name.lower()] = int(val)
    return result


def hexregs(regs, names):
    return {
        n: f"0x{int(regs.get(n, 0)) & 0xFFFFFFFF:08X}"
        for n in names
    }


def safe_guest_dump(h, base, address, before, after, filename):
    start = max(0, address - before)
    size = before + after
    try:
        blob = guest_read(h, base, start, size)
    except Exception:
        return None

    p = ANALYSIS_DIR / filename
    p.write_bytes(blob)
    meta = p.with_suffix(p.suffix + ".txt")
    meta.write_text(
        f"guest_start=0x{start:08X}\n"
        f"focus=0x{address:08X}\n"
        f"size=0x{size:X}\n",
        encoding="utf-8",
    )
    return p


def disasm_window(ws, address, before=0x60, count=56):
    start = max(0x08000000, (address - before) & ~3)
    try:
        return ws.request(
            "memory.disasm",
            timeout=10,
            address=start,
            count=count,
            displaySymbols=True,
            compact=False,
        )
    except Exception as e:
        return {"error": str(e), "address": f"0x{address:08X}"}


def u32(h, base, addr):
    return struct.unpack("<I", guest_read(h, base, addr, 4))[0]


def s32(v):
    return v - 0x100000000 if v & 0x80000000 else v


def collect_pause_snapshot(ws, pid, base):
    """
    Decode the exact relocation-table entry which produces TMR TEXADDR0/A8.

    z_un_08c3c9bc uses:
      s0+0x04 : destination data base
      s0+0x10 : relocation base #1
      s0+0x34 : relocation base #2
      s0+0x6C : 12-byte relocation entry table
      s0+0x70 : entry count

    At 0x08C3CAA8:
      a0 = entry index
      a1 = entry_index * 12
      a2 = destination address
      a3 = first GE word to store
      t1 = destination + 4
      t3 = high/prefix part for second GE word
      s0 = relocation object
    """
    status = ws.request("cpu.status", timeout=5)
    regs_resp = ws.request("cpu.getAllRegs", timeout=10)
    regs = regs_to_dict(regs_resp)

    pc = int(regs.get("pc", status.get("pc", 0)))
    obj = int(regs.get("s0", 0))
    entry_index = int(regs.get("a0", 0))
    entry_byte_off = int(regs.get("a1", 0))
    dest = int(regs.get("a2", 0))
    first_word = int(regs.get("a3", 0))
    dest_plus4 = int(regs.get("t1", 0))
    second_prefix = int(regs.get("t3", 0))

    h = open_process(pid)
    artifacts = []
    try:
        fields = {}
        for off, name in [
            (0x04, "data_base"),
            (0x10, "reloc_base_1"),
            (0x34, "reloc_base_2"),
            (0x6C, "reloc_table"),
            (0x70, "reloc_count"),
            (0x78, "reloc2_table"),
            (0x7C, "reloc2_count"),
        ]:
            fields[name] = u32(h, base, obj + off) if obj else 0

        table = fields["reloc_table"]
        count = fields["reloc_count"]
        entry_ptr = (table + entry_byte_off) & 0xFFFFFFFF

        e0 = u32(h, base, entry_ptr + 0)
        e1 = u32(h, base, entry_ptr + 4)
        e2_raw = u32(h, base, entry_ptr + 8)
        e2_signed = s32(e2_raw)

        # Reconstruct exactly the address logic in z_un_08c3c9bc.
        mode = None
        if e2_signed < 0:
            relocated = (-e2_signed) & 0xFFFFFFFF
            mode = "negative_absolute"
        elif e2_raw & 0x40000000:
            relocated = (
                fields["reloc_base_2"]
                + (e2_raw & 0x3FFFFFFF)
            ) & 0xFFFFFFFF
            mode = "base2_plus_30bit_offset"
        else:
            relocated = (
                fields["reloc_base_1"] + e2_raw
            ) & 0xFFFFFFFF
            mode = "base1_plus_offset"

        calc_first = (
            0xA0000000
            | (relocated & 0x00FFFFFF)
        ) & 0xFFFFFFFF
        calc_second = (
            0xA8000000
            | (((relocated >> 24) & 0xFF) << 16)
            | e1
        ) & 0xFFFFFFFF

        expected_dest = (
            fields["data_base"] + e0
        ) & 0xFFFFFFFF

        # Locate relocation table inside the sequential MDI runtime image.
        mdi_mapping = None
        if MDI_SEQ_BASE <= entry_ptr < MDI_SEQ_BASE + 50 * MDI_STREAM_SIZE:
            rel = entry_ptr - MDI_SEQ_BASE
            stream_index = rel // MDI_STREAM_SIZE
            decoded_offset = rel % MDI_STREAM_SIZE
            mdi_mapping = {
                "stream_index": stream_index,
                "decoded_offset": f"0x{decoded_offset:X}",
                "entry_decoded_offset":
                    f"0x{decoded_offset:X}",
            }

        if dest != RELOC_DEST_ALIAS:
            raise RuntimeError(
                f"Unexpected relocation destination 0x{dest:08X}"
            )
        if first_word != 0xA057FF40:
            raise RuntimeError(
                f"Expected exact TMR A057FF40, got 0x{first_word:08X}"
            )

        snapshot = {
            "cpu_status": status,
            "pc": f"0x{pc:08X}",
            "expected_pc": f"0x{RELOC_BREAK_PC:08X}",
            "pc_matches": pc == RELOC_BREAK_PC,
            "condition": TRACE_CONDITION,
            "registers": hexregs(
                regs,
                [
                    "a0","a1","a2","a3",
                    "t0","t1","t2","t3",
                    "s0","s1","s2","s3","s4","s5","s6","s7",
                    "sp","ra","pc",
                ],
            ),
            "relocation_object": {
                "object": f"0x{obj:08X}",
                **{
                    k: f"0x{v:08X}"
                    for k, v in fields.items()
                },
            },
            "relocation_entry": {
                "index": entry_index,
                "entry_byte_offset": f"0x{entry_byte_off:X}",
                "entry_ptr": f"0x{entry_ptr:08X}",
                "dest_offset_e0": f"0x{e0:08X}",
                "second_word_low_e1": f"0x{e1:08X}",
                "reloc_value_e2_raw": f"0x{e2_raw:08X}",
                "reloc_value_e2_signed": e2_signed,
                "mode": mode,
                "calculated_relocated_address":
                    f"0x{relocated:08X}",
                "expected_destination":
                    f"0x{expected_dest:08X}",
                "actual_destination_a2":
                    f"0x{dest:08X}",
                "first_word_a3":
                    f"0x{first_word:08X}",
                "calculated_first_word":
                    f"0x{calc_first:08X}",
                "dest_plus4_t1":
                    f"0x{dest_plus4:08X}",
                "second_prefix_t3":
                    f"0x{second_prefix:08X}",
                "calculated_second_word":
                    f"0x{calc_second:08X}",
            },
            "mdi_mapping": mdi_mapping,
            "target_for_final_patch": {
                "runtime_texture":
                    f"0x{TMR_TEX_ADDR:08X}",
                "current_relocated_texture":
                    f"0x{relocated:08X}",
                "required_runtime_delta":
                    f"0x{(TMR_TEX_ADDR - relocated) & 0xFFFFFFFF:08X}",
                "current_entry_e2":
                    f"0x{e2_raw:08X}",
                "wanted_first_word":
                    f"0x{(0xA0000000 | (TMR_TEX_ADDR & 0xFFFFFF)):08X}",
                "wanted_second_word":
                    f"0x{(0xA8000000 | (((TMR_TEX_ADDR >> 24) & 0xFF) << 16) | TMR_TEX_W):08X}",
                "wanted_texsize_word": "0xB8000907",
            },
        }

        # Save focused raw evidence.
        dumps = [
            (obj, 0x20, 0xC0, "stage30_object_neighborhood.bin"),
            (entry_ptr, 0x80, 0x180, "stage30_table_neighborhood.bin"),
            (dest & 0x0FFFFFFF, 0x100, 0x200,
             "stage30_descriptor_neighborhood.bin"),
        ]
        for addr, before, after, name in dumps:
            if not addr:
                continue
            p = safe_guest_dump(
                h, base, addr, before, after, name
            )
            if p:
                artifacts.append(p)
                artifacts.append(
                    p.with_suffix(p.suffix + ".txt")
                )

    finally:
        kernel32.CloseHandle(h)

    disasm = {
        "relocation_writer":
            disasm_window(ws, pc, 0x100, 128),
    }

    return snapshot, disasm, artifacts


def advance_until_descriptor_pause(hwnd, ws, pid, base, timeout=180):
    """
    Repeatedly inject PSP Start without waiting for the input request's reply.

    Stage28 reached PC 0x0881BF54 immediately before our conditional breakpoint,
    then timed out inside ws.request("input.buttons.press").  In other words,
    the breakpoint likely paused emulation before PPSSPP sent that input
    request's normal response, preventing this script from ever polling
    cpu.status.

    Stage28B sends Start asynchronously, then polls cpu.status independently.
    """
    start = time.time()
    presses = 0
    pending_input_tickets = []
    h = open_process(pid)

    try:
        while time.time() - start < timeout:
            # First check whether a previously-triggered breakpoint has paused.
            try:
                status = ws.request("cpu.status", timeout=2)
            except (socket.timeout, TimeoutError):
                # The socket remains valid. A delayed response from a previous
                # asynchronous input request may still be queued; retry status.
                time.sleep(0.02)
                continue

            if status.get("stepping", False):
                return {
                    "paused": True,
                    "status": status,
                    "start_presses": presses,
                    "pending_input_tickets": pending_input_tickets[-20:],
                    "elapsed_seconds":
                        round(time.time() - start, 3),
                }

            # If Story somehow appears before the break, stop and report it.
            try:
                cur = guest_read(
                    h, base, STORY_GUEST, 10
                )
                if cur == "Story".encode("utf-16le"):
                    return {
                        "paused": False,
                        "story_reached_first": True,
                        "status": status,
                        "start_presses": presses,
                        "pending_input_tickets": pending_input_tickets[-20:],
                        "elapsed_seconds":
                            round(time.time() - start, 3),
                    }
            except Exception:
                pass

            # IMPORTANT: do not wait for this request.  The CPU can pause
            # between button injection and the normal reply.
            ticket = send_request_no_wait(
                ws,
                "input.buttons.press",
                button="start",
                duration=2,
            )
            pending_input_tickets.append(ticket)
            presses += 1

            # Poll quickly for ~180 ms before injecting Start again.
            poll_end = time.time() + 0.18
            while time.time() < poll_end:
                try:
                    status = ws.request("cpu.status", timeout=1)
                except (socket.timeout, TimeoutError):
                    time.sleep(0.015)
                    continue

                if status.get("stepping", False):
                    return {
                        "paused": True,
                        "status": status,
                        "start_presses": presses,
                        "pending_input_tickets": pending_input_tickets[-20:],
                        "elapsed_seconds":
                            round(time.time() - start, 3),
                    }

                time.sleep(0.015)

    finally:
        kernel32.CloseHandle(h)

    raise RuntimeError(
        f"Neither conditional decoder breakpoint nor Story reached "
        f"within {timeout}s"
    )



def make_zip(path: Path, entries):
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for src, arc in entries:
            p = Path(src)
            if p.exists():
                z.write(p, arc)



def copy_file_with_progress(src: Path, dst: Path, chunk_size=64 * 1024 * 1024):
    total = src.stat().st_size
    copied = 0
    next_pct = 0

    with src.open("rb") as fi, dst.open("wb") as fo:
        while True:
            buf = fi.read(chunk_size)
            if not buf:
                break
            fo.write(buf)
            copied += len(buf)

            pct = int(copied * 100 / total) if total else 100
            if pct >= next_pct:
                log(
                    f"[auto] ISO copy: {pct:3d}% "
                    f"({copied / (1024**3):.2f} / "
                    f"{total / (1024**3):.2f} GiB)"
                )
                next_pct = ((pct // 5) + 1) * 5

    shutil.copystat(src, dst)
    log("[auto] ISO copy complete")


def prepare_boot_iso(source_iso: Path, expanded: bytes):
    """
    Build Stage32 from the pristine ISO.

    Critical Stage31 finding:
      ON_MEMU.DSX is the runtime compressed representation of ON_MEMU.DSL.
      Decompressing all 94 DSX blocks and concatenating them reproduces the
      DSL byte-for-byte.

    Therefore permanent descriptor changes must be applied to BOTH:
      ON_MEMU.DSL  (logical/plain form)
      ON_MEMU.DSX  (runtime compressed form actually consumed by the game)
    """
    log(f"[auto] Building fresh permanent DSX test ISO: {TEST_ISO}")

    if TEST_ISO.exists():
        TEST_ISO.unlink()

    copy_file_with_progress(source_iso, TEST_ISO)

    log("[auto] Reading pristine MDI / DSL / DSX")
    _, mdi = iso_read_file(source_iso, TARGET_MDI)
    _, dsl = iso_read_file(source_iso, TARGET_DSL)
    _, dsx = iso_read_file(source_iso, TARGET_DSX)

    if sha1_bytes(mdi) != EXPECTED_MDI_SHA1:
        raise RuntimeError("MDI SHA1 mismatch")
    if sha1_bytes(dsl) != EXPECTED_DSL_SHA1:
        raise RuntimeError("DSL SHA1 mismatch")
    if sha1_bytes(dsx) != EXPECTED_DSX_SHA1:
        raise RuntimeError("DSX SHA1 mismatch")

    original_dsx_logical = dsx_logical_bytes(dsx)
    if original_dsx_logical != dsl:
        raise RuntimeError(
            "Original DSX does not decompress exactly to original DSL"
        )

    log("[auto] Building corrected permanent MDI")
    patched_mdi, mdi_info = patch_mdi(mdi, expanded)

    log("[auto] Patching logical DSL descriptor sources")
    patched_dsl, dsl_info = patch_dsl_descriptor(dsl)

    log("[auto] Rebuilding runtime DSX from patched DSL")
    patched_dsx, dsx_info = rebuild_dsx_from_logical(
        dsx, patched_dsl
    )

    # The two known modifications must land in DSX blocks 90 and 93.
    changed_indices = [
        x["index"] for x in dsx_info["changed_blocks"]
    ]
    if changed_indices != [90, 93]:
        raise RuntimeError(
            f"Unexpected changed DSX blocks: {changed_indices}"
        )

    log("[auto] Writing expanded MDI as new ISO extent")
    mdi_iso_info = append_iso_file_and_repoint(
        TEST_ISO, TARGET_MDI, patched_mdi
    )

    log("[auto] Writing patched plain DSL")
    overwrite_iso_same_size(
        TEST_ISO, TARGET_DSL, patched_dsl
    )

    log("[auto] Writing rebuilt runtime DSX as new ISO extent")
    dsx_iso_info = append_iso_file_and_repoint(
        TEST_ISO, TARGET_DSX, patched_dsx
    )

    log("[auto] Verifying Stage32 ISO read-back")
    _, mdi_rb = iso_read_file(TEST_ISO, TARGET_MDI)
    _, dsl_rb = iso_read_file(TEST_ISO, TARGET_DSL)
    _, dsx_rb = iso_read_file(TEST_ISO, TARGET_DSX)

    if mdi_rb != patched_mdi:
        raise RuntimeError("MDI ISO read-back mismatch")
    if dsl_rb != patched_dsl:
        raise RuntimeError("DSL ISO read-back mismatch")
    if dsx_rb != patched_dsx:
        raise RuntimeError("DSX ISO read-back mismatch")
    if dsx_logical_bytes(dsx_rb) != dsl_rb:
        raise RuntimeError(
            "ISO DSX logical output != ISO patched DSL"
        )

    return TEST_ISO, {
        "mode": "fresh_from_original",
        "path": str(TEST_ISO),
        "mdi_patch": mdi_info,
        "dsl_permanent_patch": dsl_info,
        "dsx_permanent_patch": dsx_info,
        "mdi_iso_relocation": mdi_iso_info,
        "dsx_iso_relocation": dsx_iso_info,
        "iso_readback_verified": True,
        "dsx_decompresses_exactly_to_patched_dsl": True,
    }





def close_existing_ppsspp(timeout=3.0):
    """
    Close an old PPSSPP instance without ever blocking on SendMessage(WM_CLOSE).

    1) PostMessage(WM_CLOSE) asynchronously.
    2) Wait up to timeout seconds.
    3) If the exact PPSSPP window is still alive, terminate only its process.
    """
    WM_CLOSE = 0x0010

    hwnd = user32.FindWindowW("PPSSPPWnd", None)
    if not hwnd:
        log("[auto] No existing PPSSPP instance")
        return {"found": False}

    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    old_pid = int(pid.value)

    log(
        f"[auto] Existing PPSSPP found: HWND=0x{int(hwnd):X}, "
        f"PID={old_pid}"
    )
    log("[auto] Requesting asynchronous PPSSPP close")

    user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)

    end = time.time() + timeout
    while time.time() < end:
        if not user32.FindWindowW("PPSSPPWnd", None):
            log("[auto] Existing PPSSPP closed normally")
            return {
                "found": True,
                "pid": old_pid,
                "closed_normally": True,
            }
        time.sleep(0.10)

    log(
        f"[auto] PPSSPP did not close within {timeout:.1f}s; "
        f"terminating PID {old_pid}"
    )

    h = kernel32.OpenProcess(
        PROCESS_TERMINATE | PROCESS_QUERY_INFORMATION,
        False,
        old_pid,
    )
    if not h:
        raise RuntimeError(
            f"Could not open old PPSSPP PID {old_pid} for termination "
            f"(Win32 {ctypes.get_last_error()})"
        )

    try:
        if not kernel32.TerminateProcess(h, 0):
            raise RuntimeError(
                f"TerminateProcess failed for PPSSPP PID {old_pid} "
                f"(Win32 {ctypes.get_last_error()})"
            )
    finally:
        kernel32.CloseHandle(h)

    end = time.time() + 3.0
    while time.time() < end:
        if not user32.FindWindowW("PPSSPPWnd", None):
            log("[auto] Existing PPSSPP process terminated")
            return {
                "found": True,
                "pid": old_pid,
                "closed_normally": False,
                "terminated": True,
            }
        time.sleep(0.10)

    raise RuntimeError("Old PPSSPP window still exists after process termination")



def register_ppsspp_auto_close(proc):
    """
    Always close the PPSSPP instance launched by this stage when Python exits.

    Normal path:
      PostMessage(WM_CLOSE) -> wait up to 3 seconds.
    Fallback:
      terminate only this exact subprocess PID.
    """
    def cleanup():
        try:
            if proc.poll() is not None:
                return

            WM_CLOSE = 0x0010
            hwnd = user32.FindWindowW("PPSSPPWnd", None)
            if hwnd:
                win_pid = wintypes.DWORD()
                user32.GetWindowThreadProcessId(
                    hwnd, ctypes.byref(win_pid)
                )
                if int(win_pid.value) == int(proc.pid):
                    user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)

            try:
                proc.wait(timeout=3.0)
                return
            except Exception:
                pass

            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=2.0)
                except Exception:
                    pass
        except Exception:
            pass

    atexit.register(cleanup)
    return cleanup



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
        "stage": 32,
        "purpose":
            "Prove permanent MDI + DSL + runtime DSX TMR relocation, corrected UV, "
            "and 128x512 TEXSIZE without any runtime descriptor/font watcher",
        "source_iso": str(source_iso),
        "test_iso": str(TEST_ISO),
        "ppsspp_exe": str(exe),
        "texture_replacement_enabled": False,
        "runtime_font_patch_enabled": False,
        "runtime_descriptor_watcher_enabled": False,
        "texture_storage": {
            "mdi_stream": STREAM22_INDEX,
            "runtime_address": f"0x{TMR_TEX_ADDR:08X}",
            "bytes": TMR_TEX_SIZE,
            "sha1": expanded_sha1,
        },
    }

    log("=" * 80)
    log("BIA Stage 32 - permanent DSX/DSL font proof")
    log("=" * 80)

    boot_iso, iso_info = prepare_boot_iso(
        source_iso, expanded
    )
    report["boot_iso"] = str(boot_iso)
    report["iso_prepare"] = iso_info

    before_png = ANALYSIS_DIR / "stage32_menu_english.png"
    after_png = ANALYSIS_DIR / "stage32_menu_korean.png"
    ppsspp_log = ANALYSIS_DIR / "stage32_ppsspp_debug.log"
    report_path = ANALYSIS_DIR / "stage32_report.json"

    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    report["previous_ppsspp"] = close_existing_ppsspp(timeout=3.0)

    # Normal JIT: Stage31 is no longer a breakpoint experiment.
    cmd = [
        str(exe),
        "-d",
        f"--log={ppsspp_log}",
        "--windowed",
        f"--appendconfig={cfg}",
        f"--debugger={requested_port}",
        str(boot_iso),
    ]

    log("[auto] Launching PPSSPP in normal JIT mode")
    proc = subprocess.Popen(cmd)
    cleanup_ppsspp = register_ppsspp_auto_close(proc)
    report["launched_ppsspp_pid"] = proc.pid
    report["ppsspp_auto_close"] = True

    hwnd = find_ppsspp_hwnd(30)
    if not hwnd:
        raise RuntimeError("PPSSPP window did not appear")

    end_wait = time.time() + 30
    pid = base = None
    while time.time() < end_wait:
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

    success_zip = LOG_DIR / "bia_stage32_upload.zip"
    fail_zip = LOG_DIR / "fail_bia_stage32_upload.zip"

    try:
        report["debugger_host"] = host
        report["debugger_port"] = actual_port

        try:
            report["version"] = ws.request(
                "version",
                timeout=5,
                name="bia-stage32",
                version="1",
            )
        except Exception as e:
            report["version_error"] = str(e)

        log("[auto] Native Start automation -> Story")
        boot_info = wait_for_story_native(
            hwnd, ws, pid, base, 120
        )
        report["boot_automation"] = boot_info
        report["menu_detected"] = True

        h = open_process(pid)
        old_story = None
        try:
            loaded = inspect_loaded(
                h, base, expanded_sha1
            )
            report["loaded_font"] = loaded

            runtime_desc = struct.unpack(
                "<III",
                guest_read(
                    h, base, TMR_RUNTIME_DESC, 12
                )
            )
            expected_desc = descriptor_words_for_expanded_tmr()

            report["runtime_descriptor"] = [
                f"0x{x:08X}" for x in runtime_desc
            ]
            report["expected_runtime_descriptor"] = [
                f"0x{x:08X}" for x in expected_desc
            ]
            report["runtime_descriptor_matches"] = (
                runtime_desc == expected_desc
            )
            report["permanent_A0_A8_match"] = (
                runtime_desc[:2] == expected_desc[:2]
            )
            report["permanent_B8_match"] = (
                runtime_desc[2] == expected_desc[2]
            )

            capture(hwnd, before_png, helper)

            report_path.write_text(
                json.dumps(
                    report,
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            if runtime_desc != expected_desc:
                raise RuntimeError(
                    "Permanent descriptor proof failed: "
                    f"got {[f'0x{x:08X}' for x in runtime_desc]}, "
                    f"expected {[f'0x{x:08X}' for x in expected_desc]}"
                )

            # Runtime change is ONLY test text, never font/descriptor data.
            old_story = guest_read(
                h, base, STORY_GUEST, 10
            )
            if old_story != "Story".encode("utf-16le"):
                raise RuntimeError(
                    "Story UTF-16 slot mismatch before Korean test"
                )

            korean = struct.pack(
                "<5H",
                TEST_CP, TEST_CP, TEST_CP,
                TEST_CP, TEST_CP,
            )
            guest_write(
                h, base, STORY_GUEST, korean
            )

            time.sleep(1.0)
            capture(hwnd, after_png, helper)

            # Re-check permanent descriptor after Korean redraw.
            desc_after = struct.unpack(
                "<III",
                guest_read(
                    h, base, TMR_RUNTIME_DESC, 12
                )
            )
            report["runtime_descriptor_after_korean"] = [
                f"0x{x:08X}" for x in desc_after
            ]

            report["runtime_patch_scope"] = (
                "Story UTF-16 test text only; "
                "NO font/UV/texture/descriptor RAM patch"
            )
            report["permanent_font_proof"] = True
            report["completed"] = True

        finally:
            if old_story is not None:
                try:
                    guest_write(
                        h, base, STORY_GUEST, old_story
                    )
                except Exception:
                    pass
            kernel32.CloseHandle(h)

    finally:
        ws.close()

    # Close PPSSPP as soon as test use is finished, before packaging.
    try:
        cleanup_ppsspp()
        report["ppsspp_closed_after_test"] = True
    except Exception as e:
        report["ppsspp_close_error"] = str(e)

    report_path.write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    make_zip(success_zip, [
        (report_path, "stage32_report.json"),
        (ppsspp_log, "stage32_ppsspp_debug.log"),
        (cfg, "stage32_append.ini"),
        (before_png, "stage32_menu_english.png"),
        (after_png, "stage32_menu_korean.png"),
    ])

    log(f"Stage 32 complete: {success_zip}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)

        failure = ANALYSIS_DIR / "FAILURE.txt"
        failure.write_text(
            traceback.format_exc(),
            encoding="utf-8",
        )

        fail_zip = LOG_DIR / "fail_bia_stage32_upload.zip"
        make_zip(fail_zip, [
            (failure, "FAILURE.txt"),
            (
                ANALYSIS_DIR / "stage32_report.json",
                "stage32_report.json"
            ),
            (
                ANALYSIS_DIR / "stage32_ppsspp_debug.log",
                "stage32_ppsspp_debug.log"
            ),
            (
                ANALYSIS_DIR / "stage32_append.ini",
                "stage32_append.ini"
            ),
            (
                ANALYSIS_DIR / "stage32_menu_english.png",
                "stage32_menu_english.png"
            ),
            (
                ANALYSIS_DIR / "stage32_menu_korean.png",
                "stage32_menu_korean.png"
            ),
        ])
        print(traceback.format_exc(), flush=True)
        print(f"STAGE 32 FAILED: {fail_zip}", flush=True)
        raise SystemExit(1)
