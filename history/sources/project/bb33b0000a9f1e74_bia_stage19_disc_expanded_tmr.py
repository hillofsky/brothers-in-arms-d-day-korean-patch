#!/usr/bin/env python3
from __future__ import annotations

import ctypes
from ctypes import wintypes
import hashlib
import json
import os
import shutil
import struct
import subprocess
import time
import traceback
import zipfile
import zlib
from pathlib import Path

ROOT = Path(r"PROJECT_ROOT")
LOG_DIR = ROOT / "log"
ANALYSIS_DIR = ROOT / "analysis" / "stage19_disc_expanded_tmr"
TEST_ISO = ROOT / "BIA_STAGE19_EXPANDED_FONT_TEST.iso"

GAME_ID = "ULUS10193"

TARGET_MDI = ["PSP_GAME", "USRDIR", "SYSTEM", "ON_MEMU_O.MDI"]
TARGET_DSL = ["PSP_GAME", "USRDIR", "SYSTEM", "ON_MEMU.DSL"]

EXPECTED_MDI_SHA1 = "22de1f889d1617199a3e21d4a1f63fcaf87b944a"
EXPECTED_DSL_SHA1 = "e009f2e259861f60d0aeeb03f46422d5473b88aa"

# Confirmed by Stage 18C frame dump.
TMR_OLD_FILE_OFF = 0x15D964
TMR_OLD_SIZE = 0x4000
TMR_DESC_OFF = 0x175137

# Magma relocatable texture descriptor formula:
#   source_descriptor_address = DSL_file_offset + 0x09566BDC
# Loader relocates this to:
#   runtime_address = DSL_file_offset + 0x084225DC
DSL_SOURCE_BIAS = 0x09566BDC
DSL_RUNTIME_BIAS = 0x084225DC

# Appended expanded TMR starts at an offset whose low nibble is 4,
# preserving 16-byte alignment after DSL_RUNTIME_BIAS (...DC).
TMR_NEW_FILE_OFF = 0x1751C4
TMR_NEW_SIZE = 0x8000

# MDI stream 19 is loaded at this fixed PSP address.
STREAM19_RAM_BASE = 0x09715020

# TMR font object / page table in decoded stream 19.
TMR_PAGE_TABLE_OFF = 0xE894
TMR_OBJ_OFF = TMR_PAGE_TABLE_OFF - 0x58
TMR_COUNT_OFF = TMR_OBJ_OFF + 0x50
TMR_GLYPH_PTR_OFF = TMR_OBJ_OFF + 0x54

# New permanent structures in the verified all-zero tail of stream 19.
TMR_NEW_GLYPH_ARRAY_OFF = 0x46000
TMR_NEW_D5_PAGE_OFF = 0x47000

OLD_GLYPH_COUNT = 151
NEW_GLYPH_INDEX = 151
NEW_GLYPH_COUNT = 152
GLYPH_REC_SIZE = 24

TEST_CP = 0xD55C
TEST_HIGH = 0xD5
TEST_LOW = 0x5C

STORY_GUEST = 0x08E41620

WM_APP = 0x8000
WM_USER_GET_BASE_POINTER = WM_APP + 0x3118
SW_RESTORE = 9

PROCESS_VM_READ = 0x0010
PROCESS_VM_WRITE = 0x0020
PROCESS_VM_OPERATION = 0x0008
PROCESS_QUERY_INFORMATION = 0x0400

INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
VK_TAB = 0x09
VK_RETURN = 0x0D

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


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class INPUTUNION(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT)]


class INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [
        ("type", wintypes.DWORD),
        ("u", INPUTUNION),
    ]


user32.SendInput.argtypes = [
    wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int
]
user32.SendInput.restype = wintypes.UINT


def log(s=""):
    print(s, flush=True)


def sha1_bytes(b):
    return hashlib.sha1(b).hexdigest()


def align_up(v, a):
    return (v + a - 1) & ~(a - 1)


def send_vk(vk, down=True):
    inp = INPUT()
    inp.type = INPUT_KEYBOARD
    inp.ki.wVk = vk
    inp.ki.wScan = 0
    inp.ki.dwFlags = 0 if down else KEYEVENTF_KEYUP
    inp.ki.time = 0
    inp.ki.dwExtraInfo = None
    sent = user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
    if sent != 1:
        raise RuntimeError(
            f"SendInput failed for VK 0x{vk:02X}: "
            f"{ctypes.get_last_error()}"
        )


def tap_vk(vk, hold=0.04):
    send_vk(vk, True)
    time.sleep(hold)
    send_vk(vk, False)


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
                raise RuntimeError(
                    f"ISO path not found: {'/'.join(parts)}"
                )
            extent = found["extent"]
            size = found["size"]

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
    f.seek(record_offset)
    ln = f.read(1)[0]
    if ln < 34:
        raise RuntimeError("Invalid directory record")

    # ISO9660 stores both little-endian and big-endian copies.
    f.seek(record_offset + 2)
    f.write(struct.pack("<I", extent))
    f.write(struct.pack(">I", extent))

    f.seek(record_offset + 10)
    f.write(struct.pack("<I", size))
    f.write(struct.pack(">I", size))


def update_volume_space_size(f, total_sectors):
    # Update every primary/supplementary volume descriptor that carries
    # the volume-space-size field. Stop at descriptor type 255.
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


def append_iso_file_and_repoint(
    iso: Path, target_parts, payload: bytes
):
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
            f.write(
                b"\x00" * (
                    padded_end - (new_off + len(payload))
                )
            )

        new_extent = new_off // 2048
        patch_dir_record_extent_size(
            f, rec["record_offset"], new_extent, len(payload)
        )

        total_sectors = padded_end // 2048
        update_volume_space_size(f, total_sectors)

    return {
        "old_extent": rec["extent"],
        "old_size": rec["size"],
        "new_extent": new_extent,
        "new_size": len(payload),
        "new_byte_offset": new_off,
    }


def valid_zlib_header(two):
    if len(two) != 2:
        return False
    cmf, flg = two
    return (
        (cmf & 0x0F) == 8
        and ((cmf << 8) + flg) % 31 == 0
    )


def parse_mdi(data: bytes):
    streams = []
    pos = 6
    idx = 0

    while pos + 4 <= len(data):
        csize = struct.unpack_from("<I", data, pos)[0]
        zpos = pos + 4

        if (
            csize <= 0
            or zpos + csize > len(data)
            or not valid_zlib_header(data[zpos:zpos+2])
        ):
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
            raise RuntimeError(
                f"Could not parse MDI at 0x{pos:X}"
            )

        comp = data[zpos:zpos+csize]
        dec = zlib.decompress(comp)

        streams.append({
            "index": idx,
            "size_field_pos": pos,
            "zpos": zpos,
            "csize": csize,
            "decoded": dec,
        })

        pos = zpos + csize
        idx += 1

    if pos != len(data):
        raise RuntimeError(
            f"MDI parse mismatch: 0x{pos:X}/0x{len(data):X}"
        )

    return streams


def patch_mdi_expanded_tmr(original: bytes):
    streams = parse_mdi(original)
    st = streams[19]

    if len(st["decoded"]) != 0x78000:
        raise RuntimeError(
            f"Unexpected stream19 size: {len(st['decoded'])}"
        )

    dec = bytearray(st["decoded"])

    old_count = struct.unpack_from(
        "<H", dec, TMR_COUNT_OFF
    )[0]
    old_ptr = struct.unpack_from(
        "<I", dec, TMR_GLYPH_PTR_OFF
    )[0]

    expected_old_ptr = 0x09723FD8
    if old_count != OLD_GLYPH_COUNT or old_ptr != expected_old_ptr:
        raise RuntimeError(
            f"Unexpected TMR font object: count={old_count}, "
            f"ptr=0x{old_ptr:08X}"
        )

    old_ptr_off = old_ptr - STREAM19_RAM_BASE

    # Confirm permanent target areas are currently unused.
    region_start = TMR_NEW_GLYPH_ARRAY_OFF
    region_end = TMR_NEW_D5_PAGE_OFF + 512
    if any(dec[region_start:region_end]):
        raise RuntimeError(
            "Chosen stream19 permanent expansion area is not zero"
        )

    # Copy all 151 current records, then rescale V coordinates because
    # the real texture is changing from 128x256 -> 128x512.
    recs = bytearray(
        dec[
            old_ptr_off:
            old_ptr_off + OLD_GLYPH_COUNT * GLYPH_REC_SIZE
        ]
    )

    for i in range(OLD_GLYPH_COUNT):
        off = i * GLYPH_REC_SIZE
        v0 = struct.unpack_from("<f", recs, off + 12)[0]
        v1 = struct.unpack_from("<f", recs, off + 20)[0]
        struct.pack_into("<f", recs, off + 12, v0 * 0.5)
        struct.pack_into("<f", recs, off + 20, v1 * 0.5)

    dec[
        TMR_NEW_GLYPH_ARRAY_OFF:
        TMR_NEW_GLYPH_ARRAY_OFF + len(recs)
    ] = recs

    # Append glyph #151 by cloning A's metrics and pointing its UV to the
    # new Korean cell in the lower half.
    A_MAP_VALUE = 34
    a_off = old_ptr_off + A_MAP_VALUE * GLYPH_REC_SIZE
    new_rec = bytearray(
        dec[a_off:a_off + GLYPH_REC_SIZE]
    )

    struct.pack_into("<H", new_rec, 0, TEST_CP)
    struct.pack_into("<f", new_rec, 8,  0.5 / 128.0)
    struct.pack_into("<f", new_rec, 12, 256.5 / 512.0)
    struct.pack_into("<f", new_rec, 16, 17.5 / 128.0)
    struct.pack_into("<f", new_rec, 20, 272.5 / 512.0)

    new_rec_off = (
        TMR_NEW_GLYPH_ARRAY_OFF
        + NEW_GLYPH_INDEX * GLYPH_REC_SIZE
    )
    dec[new_rec_off:new_rec_off+GLYPH_REC_SIZE] = new_rec

    # New independent D5 page.
    page = bytearray(512)
    struct.pack_into("<H", page, TEST_LOW * 2, NEW_GLYPH_INDEX)
    dec[
        TMR_NEW_D5_PAGE_OFF:
        TMR_NEW_D5_PAGE_OFF + 512
    ] = page

    # Point TMR font object at the expanded permanent structures.
    struct.pack_into(
        "<H", dec, TMR_COUNT_OFF, NEW_GLYPH_COUNT
    )
    struct.pack_into(
        "<I", dec, TMR_GLYPH_PTR_OFF,
        STREAM19_RAM_BASE + TMR_NEW_GLYPH_ARRAY_OFF
    )
    struct.pack_into(
        "<I", dec,
        TMR_PAGE_TABLE_OFF + TEST_HIGH * 4,
        STREAM19_RAM_BASE + TMR_NEW_D5_PAGE_OFF
    )

    comp = zlib.compress(bytes(dec), 9)

    rebuilt = (
        original[:st["size_field_pos"]]
        + struct.pack("<I", len(comp))
        + comp
        + original[st["zpos"] + st["csize"]:]
    )

    # Full reparse verification.
    vst = parse_mdi(rebuilt)[19]["decoded"]

    checks = {
        "count": struct.unpack_from(
            "<H", vst, TMR_COUNT_OFF
        )[0],
        "glyph_ptr": struct.unpack_from(
            "<I", vst, TMR_GLYPH_PTR_OFF
        )[0],
        "D5_ptr": struct.unpack_from(
            "<I",
            vst,
            TMR_PAGE_TABLE_OFF + TEST_HIGH * 4
        )[0],
        "D55C_map": struct.unpack_from(
            "<H",
            vst,
            TMR_NEW_D5_PAGE_OFF + TEST_LOW * 2
        )[0],
    }

    expected = {
        "count": NEW_GLYPH_COUNT,
        "glyph_ptr":
            STREAM19_RAM_BASE + TMR_NEW_GLYPH_ARRAY_OFF,
        "D5_ptr":
            STREAM19_RAM_BASE + TMR_NEW_D5_PAGE_OFF,
        "D55C_map": NEW_GLYPH_INDEX,
    }

    if checks != expected:
        raise RuntimeError(
            f"Rebuilt MDI verification failed: {checks}"
        )

    return rebuilt, {
        "old_stream19_csize": st["csize"],
        "new_stream19_csize": len(comp),
        "mdi_size_delta": len(rebuilt) - len(original),
        "new_glyph_count": NEW_GLYPH_COUNT,
        "new_glyph_ptr":
            f"0x{expected['glyph_ptr']:08X}",
        "new_D5_page":
            f"0x{expected['D5_ptr']:08X}",
        "D55C_map_value": NEW_GLYPH_INDEX,
    }


def encode_reloc_texaddr(file_off, bufw):
    source_addr = file_off + DSL_SOURCE_BIAS

    texaddr_word = (
        0xA0000000
        | (source_addr & 0x00FFFFF0)
    )

    # Bit 22 is the relocation marker present in every original
    # Magma texture descriptor. Bits 16..19 carry addr bits 24..27.
    texbuf_word = (
        0xA8000000
        | 0x00400000
        | (((source_addr >> 24) & 0xF) << 16)
        | (bufw & 0xFFFF)
    )

    return source_addr, texaddr_word, texbuf_word


def patch_dsl_expanded_tmr(original: bytes, expanded: bytes):
    if len(expanded) != TMR_NEW_SIZE:
        raise RuntimeError("Expanded TMR payload is not 0x8000 bytes")

    # Descriptor currently points to original TMR.
    old_source, old_a0, old_a8 = encode_reloc_texaddr(
        TMR_OLD_FILE_OFF, 128
    )

    got_a0 = struct.unpack_from(
        "<I", original, TMR_DESC_OFF + 0x00
    )[0]
    got_a8 = struct.unpack_from(
        "<I", original, TMR_DESC_OFF + 0x04
    )[0]
    got_b8 = struct.unpack_from(
        "<I", original, TMR_DESC_OFF + 0x08
    )[0]

    if (
        got_a0 != old_a0
        or got_a8 != old_a8
        or got_b8 != 0xB8000807
    ):
        raise RuntimeError(
            "Original TMR texture descriptor validation failed: "
            f"A0=0x{got_a0:08X}, "
            f"A8=0x{got_a8:08X}, "
            f"B8=0x{got_b8:08X}"
        )

    # Grow DSL until exact appended offset.
    if len(original) > TMR_NEW_FILE_OFF:
        raise RuntimeError(
            f"DSL unexpectedly larger than append point: "
            f"0x{len(original):X}"
        )

    patched = bytearray(original)
    patched.extend(
        b"\x00" * (TMR_NEW_FILE_OFF - len(patched))
    )
    patched.extend(expanded)

    new_source, new_a0, new_a8 = encode_reloc_texaddr(
        TMR_NEW_FILE_OFF, 128
    )

    struct.pack_into(
        "<I", patched, TMR_DESC_OFF + 0x00, new_a0
    )
    struct.pack_into(
        "<I", patched, TMR_DESC_OFF + 0x04, new_a8
    )
    struct.pack_into(
        "<I", patched, TMR_DESC_OFF + 0x08,
        0xB8000907
    )

    expected_runtime = TMR_NEW_FILE_OFF + DSL_RUNTIME_BIAS

    return bytes(patched), {
        "old_texture_file_offset":
            f"0x{TMR_OLD_FILE_OFF:X}",
        "new_texture_file_offset":
            f"0x{TMR_NEW_FILE_OFF:X}",
        "old_source_descriptor_address":
            f"0x{old_source:08X}",
        "new_source_descriptor_address":
            f"0x{new_source:08X}",
        "expected_runtime_texture_address":
            f"0x{expected_runtime:08X}",
        "new_A0": f"0x{new_a0:08X}",
        "new_A8": f"0x{new_a8:08X}",
        "new_B8": "0xB8000907",
        "new_dimensions": [128, 512],
        "new_dsl_size": len(patched),
        "expanded_raw_sha1": sha1_bytes(expanded),
    }


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
        for name in (
            "PPSSPPWindows64.exe",
            "PPSSPPDebug64.exe",
        ):
            try:
                hits = list(codex.rglob(name))
            except OSError:
                hits = []
            if hits:
                return max(
                    hits, key=lambda p: p.stat().st_mtime_ns
                )

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
        raise RuntimeError(
            r"Original ISO not found under PROJECT_ROOT"
        )

    named = [
        p for p in isos
        if "BROTHERS" in p.name.upper()
        or "D-DAY" in p.name.upper()
    ]

    return max(
        named or isos, key=lambda p: p.stat().st_size
    )


def write_append_config():
    cfg = ANALYSIS_DIR / "stage19_append.ini"
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


def find_ppsspp_hwnd(timeout=30):
    end = time.time() + timeout

    while time.time() < end:
        hwnd = user32.FindWindowW(
            "PPSSPPWnd", None
        )
        if hwnd:
            return hwnd
        time.sleep(0.2)

    return 0


def get_pid_base(hwnd):
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(
        hwnd, ctypes.byref(pid)
    )

    lo = int(user32.SendMessageW(
        hwnd, WM_USER_GET_BASE_POINTER, 0, 0
    )) & 0xFFFFFFFF
    hi = int(user32.SendMessageW(
        hwnd, WM_USER_GET_BASE_POINTER, 0, 1
    )) & 0xFFFFFFFF

    base = (hi << 32) | lo

    if not pid.value or not base:
        raise RuntimeError(
            "Could not obtain PPSSPP PID/base pointer"
        )

    return pid.value, base


def open_process(pid):
    h = kernel32.OpenProcess(
        PROCESS_VM_READ
        | PROCESS_VM_WRITE
        | PROCESS_VM_OPERATION
        | PROCESS_QUERY_INFORMATION,
        False,
        pid,
    )

    if not h:
        raise RuntimeError(
            f"OpenProcess failed "
            f"({ctypes.get_last_error()})"
        )

    return h


def rpm(h, addr, size):
    buf = (ctypes.c_ubyte * size)()
    got = ctypes.c_size_t()

    ok = kernel32.ReadProcessMemory(
        h,
        ctypes.c_void_p(addr),
        ctypes.byref(buf),
        size,
        ctypes.byref(got),
    )

    if not ok or got.value != size:
        raise RuntimeError(
            f"ReadProcessMemory failed at "
            f"host 0x{addr:X}"
        )

    return bytes(buf)


def wpm(h, addr, data):
    buf = ctypes.create_string_buffer(
        data, len(data)
    )
    wrote = ctypes.c_size_t()

    ok = kernel32.WriteProcessMemory(
        h,
        ctypes.c_void_p(addr),
        buf,
        len(data),
        ctypes.byref(wrote),
    )

    if not ok or wrote.value != len(data):
        raise RuntimeError(
            f"WriteProcessMemory failed at "
            f"host 0x{addr:X}"
        )


def guest_read(h, base, guest, size):
    return rpm(h, base + guest, size)


def guest_write(h, base, guest, data):
    wpm(h, base + guest, data)


def foreground(hwnd):
    user32.ShowWindow(hwnd, SW_RESTORE)
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.25)


def wait_for_story_sendinput(hwnd, timeout=120):
    """
    Unlike Stage18C, this uses Windows SendInput rather than PostMessage.
    PPSSPP sees these as actual keyboard events.

    Hold Tab continuously for fast-forward and press Enter repeatedly until
    the proven live Story slot appears.
    """
    foreground(hwnd)

    start = time.time()
    next_start = start + 0.75
    presses = 0
    tab_down = False

    try:
        send_vk(VK_TAB, True)
        tab_down = True
        log("[auto] SendInput: Tab DOWN (fast-forward)")

        while time.time() - start < timeout:
            try:
                pid, base = get_pid_base(hwnd)
                h = open_process(pid)
                try:
                    cur = guest_read(
                        h, base, STORY_GUEST, 10
                    )
                    if cur == "Story".encode(
                        "utf-16le"
                    ):
                        return (
                            pid,
                            base,
                            {
                                "method":
                                    "SendInput Tab-hold + Enter-repeat",
                                "start_presses": presses,
                                "elapsed_seconds":
                                    round(time.time() - start, 3),
                            },
                        )
                finally:
                    kernel32.CloseHandle(h)
            except Exception:
                pass

            now = time.time()

            if now >= next_start:
                foreground(hwnd)
                tap_vk(VK_RETURN, 0.035)
                presses += 1
                next_start = now + 0.75

            time.sleep(0.10)

    finally:
        if tab_down:
            try:
                send_vk(VK_TAB, False)
            except Exception:
                pass
            log("[auto] SendInput: Tab UP")

    raise RuntimeError(
        f"Story not detected after "
        f"{presses} Start presses"
    )


def capture(hwnd, path: Path, helper: Path):
    foreground(hwnd)

    p = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(helper),
            "-Hwnd",
            str(int(hwnd)),
            "-OutFile",
            str(path),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    if (
        p.returncode != 0
        or not path.exists()
    ):
        raise RuntimeError(
            "Screenshot capture faileLOCAL_PATH"
            + (p.stdout or "")
        )


def verify_loaded_expanded_font(
    h, base, expanded_sha1
):
    count_addr = (
        STREAM19_RAM_BASE
        + TMR_COUNT_OFF
    )
    ptr_addr = (
        STREAM19_RAM_BASE
        + TMR_GLYPH_PTR_OFF
    )
    d5_slot = (
        STREAM19_RAM_BASE
        + TMR_PAGE_TABLE_OFF
        + TEST_HIGH * 4
    )

    count = struct.unpack(
        "<H",
        guest_read(h, base, count_addr, 2)
    )[0]

    glyph_ptr = struct.unpack(
        "<I",
        guest_read(h, base, ptr_addr, 4)
    )[0]

    d5 = struct.unpack(
        "<I",
        guest_read(h, base, d5_slot, 4)
    )[0]

    map_value = struct.unpack(
        "<H",
        guest_read(
            h,
            base,
            d5 + TEST_LOW * 2,
            2,
        ),
    )[0]

    expected_ptr = (
        STREAM19_RAM_BASE
        + TMR_NEW_GLYPH_ARRAY_OFF
    )
    expected_d5 = (
        STREAM19_RAM_BASE
        + TMR_NEW_D5_PAGE_OFF
    )

    if (
        count != NEW_GLYPH_COUNT
        or glyph_ptr != expected_ptr
        or d5 != expected_d5
        or map_value != NEW_GLYPH_INDEX
    ):
        raise RuntimeError(
            "Expanded TMR MDI structure did not load "
            f"as expected: count={count}, "
            f"ptr=0x{glyph_ptr:08X}, "
            f"d5=0x{d5:08X}, map={map_value}"
        )

    runtime_tex = (
        TMR_NEW_FILE_OFF
        + DSL_RUNTIME_BIAS
    )

    tex = guest_read(
        h, base, runtime_tex, TMR_NEW_SIZE
    )
    tex_sha1 = sha1_bytes(tex)

    if tex_sha1 != expanded_sha1:
        raise RuntimeError(
            "Expanded TMR texture was not loaded at "
            f"0x{runtime_tex:08X}: "
            f"{tex_sha1} != {expanded_sha1}"
        )

    return {
        "glyph_count": count,
        "glyph_ptr": f"0x{glyph_ptr:08X}",
        "D5_page": f"0x{d5:08X}",
        "D55C_map": map_value,
        "expanded_texture_runtime_address":
            f"0x{runtime_tex:08X}",
        "expanded_texture_sha1": tex_sha1,
    }


def make_zip(path: Path, entries):
    with zipfile.ZipFile(
        path,
        "w",
        zipfile.ZIP_DEFLATED,
        compresslevel=6,
    ) as z:
        for src, arc in entries:
            p = Path(src)
            if p.exists():
                z.write(p, arc)


def main():
    LOG_DIR.mkdir(
        parents=True, exist_ok=True
    )
    ANALYSIS_DIR.mkdir(
        parents=True, exist_ok=True
    )

    script_dir = Path(__file__).resolve().parent
    helper = (
        script_dir / "capture_ppsspp.ps1"
    )
    expanded_path = (
        script_dir
        / "tmr18_expanded_128x512_swizzled.bin"
    )
    expanded = expanded_path.read_bytes()
    expanded_sha1 = sha1_bytes(expanded)

    source_iso = find_original_iso()
    exe = find_ppsspp_exe()
    cfg = write_append_config()

    report = {
        "stage": 19,
        "purpose":
            "disc-native 128x512 TMR expansion using appended DSL texture and permanent MDI glyph/page structures",
        "source_iso": str(source_iso),
        "test_iso": str(TEST_ISO),
        "ppsspp_exe": str(exe),
        "expanded_tmr_raw_sha1":
            expanded_sha1,
        "texture_replacement_enabled":
            False,
        "runtime_font_patch":
            False,
    }

    log("=" * 80)
    log(
        "BIA Stage 19 - real disc atlas expansion"
    )
    log("=" * 80)

    if TEST_ISO.exists():
        TEST_ISO.unlink()

    log("[auto] Copy original ISO")
    shutil.copy2(source_iso, TEST_ISO)

    mdi_rec, mdi = iso_read_file(
        source_iso, TARGET_MDI
    )
    dsl_rec, dsl = iso_read_file(
        source_iso, TARGET_DSL
    )

    if sha1_bytes(mdi) != EXPECTED_MDI_SHA1:
        raise RuntimeError(
            "ON_MEMU_O.MDI SHA1 mismatch"
        )

    if sha1_bytes(dsl) != EXPECTED_DSL_SHA1:
        raise RuntimeError(
            "ON_MEMU.DSL SHA1 mismatch"
        )

    patched_mdi, mdi_info = (
        patch_mdi_expanded_tmr(mdi)
    )
    patched_dsl, dsl_info = (
        patch_dsl_expanded_tmr(
            dsl, expanded
        )
    )

    log("[auto] Append relocated DSL to ISO")
    dsl_iso = append_iso_file_and_repoint(
        TEST_ISO,
        TARGET_DSL,
        patched_dsl,
    )

    log("[auto] Append relocated MDI to ISO")
    mdi_iso = append_iso_file_and_repoint(
        TEST_ISO,
        TARGET_MDI,
        patched_mdi,
    )

    report["mdi_patch"] = mdi_info
    report["dsl_patch"] = dsl_info
    report["dsl_iso_relocation"] = dsl_iso
    report["mdi_iso_relocation"] = mdi_iso

    # Verify ISO now returns exactly the rebuilt resources.
    _, dsl_rb = iso_read_file(
        TEST_ISO, TARGET_DSL
    )
    _, mdi_rb = iso_read_file(
        TEST_ISO, TARGET_MDI
    )

    if (
        dsl_rb != patched_dsl
        or mdi_rb != patched_mdi
    ):
        raise RuntimeError(
            "Repointed ISO file read-back mismatch"
        )

    report["iso_readback_verified"] = True

    before_png = (
        ANALYSIS_DIR / "stage19_before.png"
    )
    after_png = (
        ANALYSIS_DIR / "stage19_after.png"
    )
    ppsspp_log = (
        ANALYSIS_DIR
        / "stage19_ppsspp_debug.log"
    )
    report_path = (
        ANALYSIS_DIR
        / "stage19_report.json"
    )

    # Fresh emulator.
    old = user32.FindWindowW(
        "PPSSPPWnd", None
    )
    if old:
        user32.SendMessageW(
            old, 0x0010, 0, 0
        )
        for _ in range(30):
            if not user32.FindWindowW(
                "PPSSPPWnd", None
            ):
                break
            time.sleep(0.2)

    cmd = [
        str(exe),
        "-d",
        f"--log={ppsspp_log}",
        "--windowed",
        f"--appendconfig={cfg}",
        str(TEST_ISO),
    ]

    log(
        "[auto] Boot expanded-font test ISO"
    )
    subprocess.Popen(cmd)

    hwnd = find_ppsspp_hwnd(30)
    if not hwnd:
        raise RuntimeError(
            "PPSSPP window did not appear"
        )

    pid, base, boot_info = (
        wait_for_story_sendinput(
            hwnd, 120
        )
    )

    report["pid"] = pid
    report["psp_base"] = (
        f"0x{base:016X}"
    )
    report["boot_automation"] = boot_info
    report["menu_detected"] = True

    log("[auto] BEFORE screenshot")
    capture(hwnd, before_png, helper)

    h = open_process(pid)
    restores = []

    try:
        loaded = verify_loaded_expanded_font(
            h, base, expanded_sha1
        )
        report[
            "loaded_expanded_font"
        ] = loaded

        # Runtime modifies ONLY the visible test string.
        # Glyph table, Unicode page, UV, texture address/size and pixels
        # all come from the patched ISO.
        old_story = guest_read(
            h, base, STORY_GUEST, 10
        )

        if (
            old_story
            != "Story".encode("utf-16le")
        ):
            raise RuntimeError(
                "Story slot mismatch"
            )

        restores.append(
            (STORY_GUEST, old_story)
        )

        test = struct.pack(
            "<5H",
            TEST_CP,
            TEST_CP,
            TEST_CP,
            TEST_CP,
            TEST_CP,
        )
        guest_write(
            h, base, STORY_GUEST, test
        )

        time.sleep(1.5)

        log("[auto] AFTER screenshot")
        capture(
            hwnd, after_png, helper
        )

        report[
            "runtime_text_patch_only"
        ] = True

    finally:
        for guest, old_bytes in reversed(
            restores
        ):
            try:
                guest_write(
                    h,
                    base,
                    guest,
                    old_bytes,
                )
            except Exception:
                pass

        kernel32.CloseHandle(h)

    report["ram_restored"] = True
    report["expected_after"] = (
        "한한한한한"
    )
    report[
        "expected_other_menu_labels"
    ] = (
        "Skirmish / Options / Profile remain normal"
    )
    report["completed"] = True

    report_path.write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    upload = (
        LOG_DIR / "bia_stage19_upload.zip"
    )

    make_zip(
        upload,
        [
            (
                report_path,
                "stage19_report.json",
            ),
            (
                before_png,
                "stage19_before.png",
            ),
            (
                after_png,
                "stage19_after.png",
            ),
            (
                ppsspp_log,
                "stage19_ppsspp_debug.log",
            ),
            (
                cfg,
                "stage19_append.ini",
            ),
        ],
    )

    log()
    log("=" * 80)
    log("Stage 19 complete")
    log(f"Test ISO: {TEST_ISO}")
    log(f"Upload  : {upload}")
    log("=" * 80)

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())

    except Exception:
        # Always release physically injected keys on failure.
        try:
            send_vk(VK_TAB, False)
            send_vk(VK_RETURN, False)
        except Exception:
            pass

        LOG_DIR.mkdir(
            parents=True, exist_ok=True
        )
        ANALYSIS_DIR.mkdir(
            parents=True, exist_ok=True
        )

        failure = (
            ANALYSIS_DIR / "FAILURE.txt"
        )
        failure.write_text(
            traceback.format_exc(),
            encoding="utf-8",
        )

        fail_zip = (
            LOG_DIR
            / "fail_bia_stage19_upload.zip"
        )

        try:
            make_zip(
                fail_zip,
                [
                    (
                        failure,
                        "FAILURE.txt",
                    ),
                    (
                        ANALYSIS_DIR
                        / "stage19_report.json",
                        "stage19_report.json",
                    ),
                    (
                        ANALYSIS_DIR
                        / "stage19_before.png",
                        "stage19_before.png",
                    ),
                    (
                        ANALYSIS_DIR
                        / "stage19_after.png",
                        "stage19_after.png",
                    ),
                    (
                        ANALYSIS_DIR
                        / "stage19_ppsspp_debug.log",
                        "stage19_ppsspp_debug.log",
                    ),
                    (
                        ANALYSIS_DIR
                        / "stage19_append.ini",
                        "stage19_append.ini",
                    ),
                ],
            )
        except Exception:
            pass

        print()
        print("=" * 80)
        print("STAGE 19 FAILED")
        print(
            f"Failure ZIP: {fail_zip}"
        )
        print("=" * 80)
        traceback.print_exc()
        raise
