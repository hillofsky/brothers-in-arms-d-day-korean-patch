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
ANALYSIS_DIR = ROOT / "analysis" / "stage16_disc_native_font"
TEST_ISO = ROOT / "BIA_STAGE16_DISC_FONT_TEST.iso"

GAME_ID = "ULUS10193"

EXPECTED_MDI_SHA1 = "22de1f889d1617199a3e21d4a1f63fcaf87b944a"
EXPECTED_DSL_SHA1 = "e009f2e259861f60d0aeeb03f46422d5473b88aa"
EXPECTED_TMR_RAW_SHA1 = "b64ac2e19f620bcc6049f60315ed3352276fc9af"
EXPECTED_PATCHED_TMR_RAW_SHA1 = "15b9d31d7bf6238fc8e020b2b45473eced30cf9e"

TARGET_MDI = ["PSP_GAME", "USRDIR", "SYSTEM", "ON_MEMU_O.MDI"]
TARGET_DSL = ["PSP_GAME", "USRDIR", "SYSTEM", "ON_MEMU.DSL"]

# Confirmed ON_MEMU.DSL raw 4bpp swizzled texture locations.
TMR_RAW_OFF = 0x15D964
TMR_RAW_SIZE = 0x4000
AB_RAW_OFF = 0x1619A4
AB_RAW_SIZE = 0x8000

# MDI stream 19 loaded at 0x09715020.
STREAM19_RAM_BASE = 0x09715020

# Confirmed decoded offsets inside MDI stream 19.
TMR_PAGE_TABLE_OFF = 0xE894
TMR_PAGE21_OFF = 0x10000
AB_PAGE_TABLE_OFF = 0x10284
AB_PAGE21_OFF = 0x11700

TEST_CP = 0xD55C
TEST_HIGH = 0xD5
TEST_LOW = 0x5C
A_MAP_VALUE = 34

STORY_GUEST = 0x08E41620

WM_APP = 0x8000
WM_USER_GET_BASE_POINTER = WM_APP + 0x3118
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
SW_RESTORE = 9

PROCESS_VM_READ = 0x0010
PROCESS_VM_WRITE = 0x0020
PROCESS_VM_OPERATION = 0x0008
PROCESS_QUERY_INFORMATION = 0x0400

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
user32 = ctypes.WinDLL("user32", use_last_error=True)

user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
user32.FindWindowW.restype = wintypes.HWND
user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.SendMessageW.restype = ctypes.c_ssize_t
user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.PostMessageW.restype = wintypes.BOOL
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.SetForegroundWindow.restype = wintypes.BOOL
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.ShowWindow.restype = wintypes.BOOL

kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
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


def sha1_file(p: Path):
    h = hashlib.sha1()
    with p.open("rb") as f:
        while True:
            b = f.read(1024 * 1024)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


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
    first = f.read(1)
    if not first:
        return None
    ln = first[0]
    if ln == 0:
        return {"length": 0}
    rec = first + f.read(ln - 1)
    if len(rec) != ln or ln < 34:
        return None
    nlen = rec[32]
    return {
        "length": ln,
        "extent": struct.unpack_from("<I", rec, 2)[0],
        "size": struct.unpack_from("<I", rec, 10)[0],
        "flags": rec[25],
        "name": iso_norm_name(rec[33:33+nlen]),
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


def iso_find(iso: Path, parts):
    with iso.open("rb") as f:
        f.seek(16 * 2048)
        pvd = f.read(2048)
        if len(pvd) != 2048 or pvd[0] != 1 or pvd[1:6] != b"CD001":
            raise RuntimeError("ISO9660 PVD not found")
        root_len = pvd[156]
        root = pvd[156:156+root_len]
        extent = struct.unpack_from("<I", root, 2)[0]
        size = struct.unpack_from("<I", root, 10)[0]

        for part in parts:
            found = None
            for rec in iso_list_dir(f, extent, size):
                if rec["name"] == part.upper():
                    found = rec
                    break
            if not found:
                raise RuntimeError(f"ISO path not found: {'/'.join(parts)}")
            extent, size = found["extent"], found["size"]

        return extent, size


def iso_read_file(iso: Path, parts):
    extent, size = iso_find(iso, parts)
    with iso.open("rb") as f:
        f.seek(extent * 2048)
        data = f.read(size)
    if len(data) != size:
        raise RuntimeError(f"Short ISO read: {'/'.join(parts)}")
    return extent, data


def iso_overwrite_same_size(iso: Path, parts, new_data: bytes):
    extent, old_size = iso_find(iso, parts)
    if len(new_data) != old_size:
        raise RuntimeError(
            f"Same-size patch required for {'/'.join(parts)}: "
            f"{len(new_data)} != {old_size}"
        )
    with iso.open("r+b") as f:
        f.seek(extent * 2048)
        f.write(new_data)
    return extent


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

        if csize <= 0 or zpos + csize > len(data) or not valid_zlib_header(data[zpos:zpos+2]):
            # MDI occasionally has a 4-byte load-address/region marker.
            if pos + 8 <= len(data):
                c2 = struct.unpack_from("<I", data, pos + 4)[0]
                z2 = pos + 8
                if c2 > 0 and z2 + c2 <= len(data) and valid_zlib_header(data[z2:z2+2]):
                    pos += 4
                    continue
            raise RuntimeError(f"Could not parse MDI at 0x{pos:X}")

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
            f"MDI parse ended at 0x{pos:X}, size 0x{len(data):X}"
        )
    return streams


def patch_mdi_unicode_pages(original: bytes):
    streams = parse_mdi(original)
    if len(streams) <= 19:
        raise RuntimeError(f"Expected >=20 MDI streams, found {len(streams)}")

    st = streams[19]
    if len(st["decoded"]) != 491520:
        raise RuntimeError(
            f"Unexpected stream19 decoded size: {len(st['decoded'])}"
        )

    dec = bytearray(st["decoded"])

    # Validate known page 0 / page 21 pointers before editing.
    tmr_page0 = struct.unpack_from("<I", dec, TMR_PAGE_TABLE_OFF + 0x00*4)[0]
    tmr_page21 = struct.unpack_from("<I", dec, TMR_PAGE_TABLE_OFF + 0x21*4)[0]
    ab_page0 = struct.unpack_from("<I", dec, AB_PAGE_TABLE_OFF + 0x00*4)[0]
    ab_page21 = struct.unpack_from("<I", dec, AB_PAGE_TABLE_OFF + 0x21*4)[0]

    expected = {
        "tmr_page0": 0x09724E10,
        "tmr_page21": 0x09725020,
        "ab_page0": 0x09726510,
        "ab_page21": 0x09726720,
    }
    actual = {
        "tmr_page0": tmr_page0,
        "tmr_page21": tmr_page21,
        "ab_page0": ab_page0,
        "ab_page21": ab_page21,
    }
    if actual != expected:
        raise RuntimeError(
            "MDI page-table validation failed: "
            + json.dumps(
                {k: f"0x{v:08X}" for k, v in actual.items()},
                ensure_ascii=False
            )
        )

    # Permanent preload equivalent of Stage12:
    # page_table[D5] -> existing U+21xx page
    # page21[0x5C] -> A glyph
    struct.pack_into(
        "<I", dec,
        TMR_PAGE_TABLE_OFF + TEST_HIGH * 4,
        tmr_page21
    )
    struct.pack_into(
        "<H", dec,
        TMR_PAGE21_OFF + TEST_LOW * 2,
        A_MAP_VALUE
    )

    struct.pack_into(
        "<I", dec,
        AB_PAGE_TABLE_OFF + TEST_HIGH * 4,
        ab_page21
    )
    struct.pack_into(
        "<H", dec,
        AB_PAGE21_OFF + TEST_LOW * 2,
        A_MAP_VALUE
    )

    # Use a smaller memLevel to produce a stream shorter than the original.
    # Keep the MDI byte layout unchanged by padding AFTER the zlib end marker.
    # zlib accepts trailing bytes; verify the exact decoded output afterward.
    co = zlib.compressobj(
        level=9,
        method=zlib.DEFLATED,
        wbits=15,
        memLevel=5,
        strategy=zlib.Z_DEFAULT_STRATEGY,
    )
    comp = co.compress(bytes(dec)) + co.flush()

    if len(comp) > st["csize"]:
        raise RuntimeError(
            f"Patched stream19 does not fit original slot: "
            f"{len(comp)} > {st['csize']}"
        )

    padded = comp + b"\x00" * (st["csize"] - len(comp))
    if zlib.decompress(padded) != bytes(dec):
        raise RuntimeError("Padded zlib stream verification failed")

    patched = bytearray(original)
    patched[st["zpos"]:st["zpos"]+st["csize"]] = padded

    # Verify reparsing and values.
    vst = parse_mdi(bytes(patched))[19]["decoded"]
    checks = [
        (
            struct.unpack_from("<I", vst, TMR_PAGE_TABLE_OFF + TEST_HIGH*4)[0],
            tmr_page21,
            "TMR D5 pointer",
        ),
        (
            struct.unpack_from("<H", vst, TMR_PAGE21_OFF + TEST_LOW*2)[0],
            A_MAP_VALUE,
            "TMR D55C map",
        ),
        (
            struct.unpack_from("<I", vst, AB_PAGE_TABLE_OFF + TEST_HIGH*4)[0],
            ab_page21,
            "AB D5 pointer",
        ),
        (
            struct.unpack_from("<H", vst, AB_PAGE21_OFF + TEST_LOW*2)[0],
            A_MAP_VALUE,
            "AB D55C map",
        ),
    ]
    for got, want, label in checks:
        if got != want:
            raise RuntimeError(f"{label}: got {got}, expected {want}")

    return bytes(patched), {
        "stream_index": 19,
        "original_csize": st["csize"],
        "new_deflate_size_before_padding": len(comp),
        "padding_bytes": st["csize"] - len(comp),
        "tmr_D5_pointer": f"0x{tmr_page21:08X}",
        "ab_D5_pointer": f"0x{ab_page21:08X}",
        "D55C_map_value": A_MAP_VALUE,
    }


def patch_dsl_tmr(original: bytes, payload: bytes):
    if len(payload) != TMR_RAW_SIZE:
        raise RuntimeError("Bundled TMR payload has wrong size")

    if sha1_bytes(original[TMR_RAW_OFF:TMR_RAW_OFF+TMR_RAW_SIZE]) != EXPECTED_TMR_RAW_SHA1:
        raise RuntimeError("Original TMR raw texture segment SHA1 mismatch")

    if sha1_bytes(payload) != EXPECTED_PATCHED_TMR_RAW_SHA1:
        raise RuntimeError("Bundled patched TMR raw texture SHA1 mismatch")

    patched = bytearray(original)
    patched[TMR_RAW_OFF:TMR_RAW_OFF+TMR_RAW_SIZE] = payload

    return bytes(patched), {
        "tmr_raw_offset": f"0x{TMR_RAW_OFF:X}",
        "tmr_raw_size": TMR_RAW_SIZE,
        "original_tmr_raw_sha1": EXPECTED_TMR_RAW_SHA1,
        "patched_tmr_raw_sha1": EXPECTED_PATCHED_TMR_RAW_SHA1,
        "ab_raw_offset_confirmed_but_not_modified": f"0x{AB_RAW_OFF:X}",
        "ab_raw_size": AB_RAW_SIZE,
    }


def find_stage09_memstick():
    summary = ROOT / "analysis" / "stage09_texture_dump" / "summary.json"
    if summary.exists():
        try:
            data = json.loads(summary.read_text(encoding="utf-8"))
            for s in data.get("dump_dirs", []):
                p = Path(s)
                q = p
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
        base = memstick.parent
        candidates += [
            base / "PPSSPPWindows64.exe",
            base / "PPSSPPDebug64.exe",
            base / "PPSSPPWindows.exe",
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
            try:
                hits = list(codex.rglob(name))
            except OSError:
                hits = []
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
    cfg = ANALYSIS_DIR / "stage16_append.ini"
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
        hwnd = user32.FindWindowW("PPSSPPWnd", None)
        if hwnd:
            return hwnd
        time.sleep(0.25)
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
        raise RuntimeError("Could not obtain PPSSPP process/base pointer")

    return pid.value, base


def open_process(pid):
    h = kernel32.OpenProcess(
        PROCESS_VM_READ | PROCESS_VM_WRITE |
        PROCESS_VM_OPERATION | PROCESS_QUERY_INFORMATION,
        False, pid
    )
    if not h:
        raise RuntimeError(
            f"OpenProcess failed ({ctypes.get_last_error()})"
        )
    return h


def rpm(h, addr, size):
    buf = (ctypes.c_ubyte * size)()
    got = ctypes.c_size_t()
    ok = kernel32.ReadProcessMemory(
        h, ctypes.c_void_p(addr), ctypes.byref(buf),
        size, ctypes.byref(got)
    )
    if not ok or got.value != size:
        raise RuntimeError(f"ReadProcessMemory failed at host 0x{addr:X}")
    return bytes(buf)


def wpm(h, addr, data):
    buf = ctypes.create_string_buffer(data, len(data))
    wrote = ctypes.c_size_t()
    ok = kernel32.WriteProcessMemory(
        h, ctypes.c_void_p(addr), buf,
        len(data), ctypes.byref(wrote)
    )
    if not ok or wrote.value != len(data):
        raise RuntimeError(f"WriteProcessMemory failed at host 0x{addr:X}")


def guest_read(h, base, guest, size):
    return rpm(h, base + guest, size)


def guest_write(h, base, guest, data):
    wpm(h, base + guest, data)


def foreground(hwnd):
    user32.ShowWindow(hwnd, SW_RESTORE)
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.25)


def tap_key(hwnd, vk):
    foreground(hwnd)
    user32.PostMessageW(hwnd, WM_KEYDOWN, vk, 0)
    time.sleep(0.05)
    user32.PostMessageW(hwnd, WM_KEYUP, vk, 0)


def wait_for_story(hwnd, timeout=120):
    end = time.time() + timeout
    next_input = time.time() + 8
    n = 0

    while time.time() < end:
        try:
            pid, base = get_pid_base(hwnd)
            h = open_process(pid)
            try:
                if guest_read(h, base, STORY_GUEST, 10) == "Story".encode("utf-16le"):
                    return pid, base
            finally:
                kernel32.CloseHandle(h)
        except Exception:
            pass

        if time.time() >= next_input:
            tap_key(hwnd, 0x0D if n % 2 == 0 else 0x5A)
            n += 1
            next_input = time.time() + 5

        time.sleep(0.4)

    raise RuntimeError("Main menu Story state not detected within 120 seconds")


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


def verify_loaded_disc_font(h, base):
    # These are the confirmed font page table locations after ON_MEMU_O.MDI loads.
    checks = []
    for name, page_table, expected_page21 in [
        ("TMR18", 0x097238B4, 0x09725020),
        ("AB18", 0x097252A4, 0x09726720),
    ]:
        d5 = struct.unpack(
            "<I",
            guest_read(h, base, page_table + TEST_HIGH * 4, 4)
        )[0]
        if d5 != expected_page21:
            raise RuntimeError(
                f"{name}: preload D5 page mismatch: "
                f"0x{d5:08X} != 0x{expected_page21:08X}"
            )
        mv = struct.unpack(
            "<H",
            guest_read(h, base, expected_page21 + TEST_LOW * 2, 2)
        )[0]
        if mv != A_MAP_VALUE:
            raise RuntimeError(
                f"{name}: preload D55C map mismatch: {mv} != {A_MAP_VALUE}"
            )
        checks.append({
            "font": name,
            "D5_page": f"0x{d5:08X}",
            "D55C_map_value": mv,
        })
    return checks


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
    payload = (script_dir / "tmr18_hanA_swizzled.bin").read_bytes()

    source_iso = find_original_iso()
    exe = find_ppsspp_exe()
    cfg = write_append_config()

    report = {
        "stage": 16,
        "purpose": "disc-native font path: patch ISO MDI Unicode page + DSL 4bpp font pixels, with PPSSPP texture replacement disabled",
        "source_iso": str(source_iso),
        "test_iso": str(TEST_ISO),
        "ppsspp_exe": str(exe),
        "test_codepoint": "U+D55C",
        "runtime_patch_scope": "Story UTF-16 string only; font map/bitmap must come from patched ISO",
        "texture_replacement_enabled": False,
    }

    log("=" * 80)
    log("BIA Stage 16 - disc-native Korean glyph proof")
    log("=" * 80)

    # Build a fresh test ISO.
    if TEST_ISO.exists():
        TEST_ISO.unlink()
    log("[auto] Original ISO -> Stage16 test ISO copy")
    shutil.copy2(source_iso, TEST_ISO)

    _, mdi = iso_read_file(source_iso, TARGET_MDI)
    _, dsl = iso_read_file(source_iso, TARGET_DSL)

    report["source_mdi_sha1"] = sha1_bytes(mdi)
    report["source_dsl_sha1"] = sha1_bytes(dsl)

    if report["source_mdi_sha1"] != EXPECTED_MDI_SHA1:
        raise RuntimeError(
            f"ON_MEMU_O.MDI SHA1 mismatch: {report['source_mdi_sha1']}"
        )
    if report["source_dsl_sha1"] != EXPECTED_DSL_SHA1:
        raise RuntimeError(
            f"ON_MEMU.DSL SHA1 mismatch: {report['source_dsl_sha1']}"
        )

    patched_mdi, mdi_info = patch_mdi_unicode_pages(mdi)
    patched_dsl, dsl_info = patch_dsl_tmr(dsl, payload)

    mdi_extent = iso_overwrite_same_size(TEST_ISO, TARGET_MDI, patched_mdi)
    dsl_extent = iso_overwrite_same_size(TEST_ISO, TARGET_DSL, patched_dsl)

    report["mdi_patch"] = mdi_info
    report["dsl_patch"] = dsl_info
    report["mdi_iso_extent"] = mdi_extent
    report["dsl_iso_extent"] = dsl_extent
    report["patched_mdi_sha1"] = sha1_bytes(patched_mdi)
    report["patched_dsl_sha1"] = sha1_bytes(patched_dsl)

    # Read back test ISO exact bytes.
    _, mdi_rb = iso_read_file(TEST_ISO, TARGET_MDI)
    _, dsl_rb = iso_read_file(TEST_ISO, TARGET_DSL)
    if mdi_rb != patched_mdi or dsl_rb != patched_dsl:
        raise RuntimeError("ISO read-back verification failed")
    report["iso_readback_verified"] = True

    before_png = ANALYSIS_DIR / "stage16_before.png"
    after_png = ANALYSIS_DIR / "stage16_after.png"
    ppsspp_log = ANALYSIS_DIR / "stage16_ppsspp_debug.log"
    report_path = ANALYSIS_DIR / "stage16_report.json"

    # Ensure fresh PPSSPP.
    old = user32.FindWindowW("PPSSPPWnd", None)
    if old:
        user32.PostMessageW(old, 0x0010, 0, 0)
        for _ in range(30):
            if not user32.FindWindowW("PPSSPPWnd", None):
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

    log("[auto] Patched test ISO boot (ReplaceTextures=False)")
    proc = subprocess.Popen(cmd)

    hwnd = find_ppsspp_hwnd(30)
    if not hwnd:
        raise RuntimeError("PPSSPP window did not appear")

    pid, base = wait_for_story(hwnd, 120)
    report["pid"] = pid
    report["psp_base"] = f"0x{base:016X}"
    report["menu_detected"] = True

    log("[auto] BEFORE screenshot")
    capture(hwnd, before_png, helper)

    h = open_process(pid)
    restores = []
    try:
        report["loaded_font_checks"] = verify_loaded_disc_font(h, base)
        report["disc_font_map_loaded_verified"] = True

        # IMPORTANT: only patch visible test string at runtime.
        # Font lookup and bitmap are already coming from the test ISO.
        old_story = guest_read(h, base, STORY_GUEST, 10)
        if old_story != "Story".encode("utf-16le"):
            raise RuntimeError("Story slot mismatch before runtime text-only patch")

        restores.append((STORY_GUEST, old_story))
        test = struct.pack("<5H", TEST_CP, TEST_CP, TEST_CP, TEST_CP, TEST_CP)
        guest_write(h, base, STORY_GUEST, test)

        if guest_read(h, base, STORY_GUEST, 10) != test:
            raise RuntimeError("Story text-only patch verification failed")

        time.sleep(1.5)

        log("[auto] AFTER screenshot")
        capture(hwnd, after_png, helper)
        report["runtime_text_patch_verified"] = True

    finally:
        for guest, old_bytes in reversed(restores):
            try:
                guest_write(h, base, guest, old_bytes)
            except Exception:
                pass
        kernel32.CloseHandle(h)

    report["ram_restored"] = True
    report["completed"] = True
    report["expected_after"] = "한한한한한"
    report["before_png"] = str(before_png)
    report["after_png"] = str(after_png)

    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    upload = LOG_DIR / "bia_stage16_upload.zip"
    make_zip(upload, [
        (report_path, "stage16_report.json"),
        (before_png, "stage16_before.png"),
        (after_png, "stage16_after.png"),
        (ppsspp_log, "stage16_ppsspp_debug.log"),
        (cfg, "stage16_append.ini"),
    ])

    log()
    log("=" * 80)
    log("Stage 16 complete")
    log(f"Test ISO: {TEST_ISO}")
    log(f"Upload  : {upload}")
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

        fail_zip = LOG_DIR / "fail_bia_stage16_upload.zip"
        try:
            make_zip(fail_zip, [
                (failure, "FAILURE.txt"),
                (ANALYSIS_DIR / "stage16_before.png", "stage16_before.png"),
                (ANALYSIS_DIR / "stage16_after.png", "stage16_after.png"),
                (ANALYSIS_DIR / "stage16_ppsspp_debug.log", "stage16_ppsspp_debug.log"),
                (ANALYSIS_DIR / "stage16_append.ini", "stage16_append.ini"),
            ])
        except Exception:
            pass

        print()
        print("=" * 80)
        print("STAGE 16 FAILED")
        print(f"Failure ZIP: {fail_zip}")
        print("=" * 80)
        traceback.print_exc()
        raise
