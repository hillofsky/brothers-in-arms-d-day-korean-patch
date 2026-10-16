#!/usr/bin/env python3
from __future__ import annotations

import ctypes
from ctypes import wintypes
import json
import os
import shutil
import struct
import subprocess
import sys
import time
import traceback
import atexit
import zipfile
from pathlib import Path

ROOT = Path(r"PROJECT_ROOT")
LOG_DIR = ROOT / "log"
ANALYSIS_DIR = ROOT / "analysis" / "stage15_expanded_atlas"

WM_APP = 0x8000
WM_USER_GET_BASE_POINTER = WM_APP + 0x3118
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
SW_RESTORE = 9

PROCESS_VM_READ = 0x0010
PROCESS_VM_WRITE = 0x0020
PROCESS_VM_OPERATION = 0x0008
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_TERMINATE = 0x0001

STORY_GUEST = 0x08E41620

PSP_RAM_START = 0x08800000
PSP_RAM_END   = 0x0A000000

# Prefer the large high-RAM free area observed in prior main-menu dumps,
# but verify it live every run. This is only temporary scratch for a few frames.
SCRATCH_SCAN_START = 0x09C00000
SCRATCH_SCAN_END   = 0x09E80000
SCRATCH_BLOCK_SIZE = 0x2000
SCRATCH_ALIGN      = 0x1000

# Confirmed in Stage 12.
FONT_LAYOUTS = [
    {
        "name": "TMR18",
        "page_table": 0x097238B4,
    },
    {
        "name": "AB18",
        "page_table": 0x097252A4,
    },
]

TEST_CP = 0xD55C
TEST_HIGH = TEST_CP >> 8       # D5
TEST_LOW = TEST_CP & 0xFF      # 5C
A_MAP_VALUE = 34               # glyph index 33 + 1

TMR_ATLAS = "0857ff40f65c4402a4ab474d.png"
AB_ATLAS  = "08583f8013cdbd38892cdd5d.png"

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
user32 = ctypes.WinDLL("user32", use_last_error=True)

# Window/process APIs.
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


def log(msg=""):
    print(msg, flush=True)


def find_stage09_memstick() -> Path | None:
    summary = ROOT / "analysis" / "stage09_texture_dump" / "summary.json"
    if summary.exists():
        try:
            data = json.loads(summary.read_text(encoding="utf-8"))
            for s in data.get("dump_dirs", []):
                p = Path(s)
                # ...\memstick\PSP\TEXTURES\ULUS10193\new
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
    if known.is_dir():
        return known
    return None



def find_texture_game_dir() -> Path:
    # Locate the ULUS10193 texture replacement directory using Stage 09 data.
    summary = ROOT / "analysis" / "stage09_texture_dump" / "summary.json"
    candidates = []
    if summary.exists():
        try:
            data = json.loads(summary.read_text(encoding="utf-8"))
            for s in data.get("dump_dirs", []):
                p = Path(s)
                if p.name.lower() == "new":
                    candidates.append(p.parent)
        except Exception:
            pass

    known = Path(
        r"LOCAL_PATH"
        r"\c-users-admin-downloads\work\ppsspp\memstick"
        r"\PSP\TEXTURES\ULUS10193"
    )
    candidates.append(known)

    for p in candidates:
        if p.is_dir():
            return p

    raise RuntimeError("PPSSPP ULUS10193 texture replacement directory not found.")


def install_test_replacements(script_dir: Path):
    game_dir = find_texture_game_dir()
    installed = []

    for name in (TMR_ATLAS, AB_ATLAS):
        src = script_dir / name
        if not src.is_file():
            raise RuntimeError(f"Bundled replacement missing: {src}")

        dst = game_dir / name
        backup = game_dir / (name + ".stage15_backup")

        if backup.exists():
            backup.unlink()

        existed = dst.exists()
        if existed:
            shutil.copy2(dst, backup)

        shutil.copy2(src, dst)
        installed.append({
            "dst": dst,
            "backup": backup,
            "existed": existed,
        })

    return game_dir, installed


def restore_test_replacements(installed):
    errors = []
    for item in reversed(installed):
        dst = item["dst"]
        backup = item["backup"]
        existed = item["existed"]
        try:
            if existed:
                shutil.copy2(backup, dst)
                backup.unlink(missing_ok=True)
            else:
                dst.unlink(missing_ok=True)
                backup.unlink(missing_ok=True)
        except Exception as e:
            errors.append(f"{dst}: {e}")
    return errors


def find_ppsspp_exe() -> Path:
    candidates = []

    # Best: infer from the Stage 09 portable PPSSPP tree.
    memstick = find_stage09_memstick()
    if memstick:
        base = memstick.parent
        candidates += [
            base / "PPSSPPWindows64.exe",
            base / "PPSSPPDebug64.exe",
            base / "PPSSPPWindows.exe",
        ]

    # Known Codex work tree.
    known_base = Path(
        r"LOCAL_PATH"
        r"\c-users-admin-downloads\work\ppsspp"
    )
    candidates += [
        known_base / "PPSSPPWindows64.exe",
        known_base / "PPSSPPDebug64.exe",
    ]

    # Project-local possibilities.
    candidates += [
        ROOT / "PPSSPPWindows64.exe",
        ROOT / "ppsspp" / "PPSSPPWindows64.exe",
    ]

    for p in candidates:
        if p.is_file():
            return p

    # Bounded fallback: Documents\Codex.
    codex = Path.home() / "Documents" / "Codex"
    if codex.is_dir():
        for name in ("PPSSPPWindows64.exe", "PPSSPPDebug64.exe"):
            try:
                hits = list(codex.rglob(name))
            except OSError:
                hits = []
            if hits:
                # Prefer latest modified executable.
                return max(hits, key=lambda p: p.stat().st_mtime_ns)

    raise RuntimeError("PPSSPPWindows64.exe를 찾지 못했습니다.")


def find_iso() -> Path:
    isos = []
    for p in ROOT.glob("*.iso"):
        if not p.is_file():
            continue
        u = p.name.upper()
        # Prefer the untouched source ISO.
        if "STAGE" in u or "TEST" in u:
            continue
        isos.append(p)

    if not isos:
        # Fallback if only a test copy is present.
        isos = [p for p in ROOT.glob("*.iso") if p.is_file()]

    if not isos:
        raise RuntimeError(r"PROJECT_ROOT 에 ISO가 없습니다.")

    named = [
        p for p in isos
        if "BROTHERS" in p.name.upper() or "D-DAY" in p.name.upper()
    ]
    return max(named or isos, key=lambda p: p.stat().st_size)


def write_append_config() -> Path:
    cfg = ANALYSIS_DIR / "stage15_append.ini"
    cfg.write_text(
        "[Debugger]\n"
        "ShowDeveloperMenu = True\n"
        "\n"
        "[Graphics]\n"
        "ReplaceTextures = True\n"
        "SaveNewTextures = False\n",
        encoding="utf-8"
    )
    return cfg


def find_ppsspp_hwnd(timeout=30.0):
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
    if not pid.value:
        raise RuntimeError("PPSSPP PID 조회 실패")

    lo = int(user32.SendMessageW(
        hwnd, WM_USER_GET_BASE_POINTER, 0, 0
    )) & 0xFFFFFFFF
    hi = int(user32.SendMessageW(
        hwnd, WM_USER_GET_BASE_POINTER, 0, 1
    )) & 0xFFFFFFFF
    base = (hi << 32) | lo
    return pid.value, base


def open_process(pid):
    h = kernel32.OpenProcess(
        PROCESS_VM_READ | PROCESS_VM_WRITE |
        PROCESS_VM_OPERATION | PROCESS_QUERY_INFORMATION,
        False, pid
    )
    if not h:
        raise RuntimeError(
            f"OpenProcess 실패: Win32 {ctypes.get_last_error()}. "
            "PPSSPP가 관리자 권한이면 PowerShell도 관리자 권한으로 실행하세요."
        )
    return h


def rpm(h, host_addr, size):
    buf = (ctypes.c_ubyte * size)()
    got = ctypes.c_size_t()
    ok = kernel32.ReadProcessMemory(
        h, ctypes.c_void_p(host_addr), ctypes.byref(buf),
        size, ctypes.byref(got)
    )
    if not ok or got.value != size:
        raise RuntimeError(
            f"ReadProcessMemory 실패: host=0x{host_addr:X}, "
            f"{got.value}/{size}"
        )
    return bytes(buf)


def wpm(h, host_addr, data):
    src = ctypes.create_string_buffer(data, len(data))
    wrote = ctypes.c_size_t()
    ok = kernel32.WriteProcessMemory(
        h, ctypes.c_void_p(host_addr), src,
        len(data), ctypes.byref(wrote)
    )
    if not ok or wrote.value != len(data):
        raise RuntimeError(
            f"WriteProcessMemory 실패: host=0x{host_addr:X}"
        )


def guest_read(h, base, guest, size):
    return rpm(h, base + guest, size)


def guest_write(h, base, guest, data):
    wpm(h, base + guest, data)


def foreground(hwnd):
    user32.ShowWindow(hwnd, SW_RESTORE)
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.3)


def tap_key(hwnd, vk):
    foreground(hwnd)
    user32.PostMessageW(hwnd, WM_KEYDOWN, vk, 0)
    time.sleep(0.05)
    user32.PostMessageW(hwnd, WM_KEYUP, vk, 0)


def wait_for_story(hwnd, timeout=120.0):
    """
    Wait until the proven live title-menu Story slot exists.
    During boot, conservatively tap Start/confirm keys to skip splash/title gates.
    """
    end = time.time() + timeout
    next_input = time.time() + 8.0
    input_count = 0

    while time.time() < end:
        try:
            pid, base = get_pid_base(hwnd)
            if base:
                h = open_process(pid)
                try:
                    cur = guest_read(h, base, STORY_GUEST, 10)
                    if cur == "Story".encode("utf-16le"):
                        return pid, base
                finally:
                    kernel32.CloseHandle(h)
        except Exception:
            pass

        now = time.time()
        if now >= next_input:
            # PPSSPP default Start is Enter; default Cross is Z.
            # Alternate them to skip intro/title screens without menu clicking.
            vk = 0x0D if input_count % 2 == 0 else 0x5A
            tap_key(hwnd, vk)
            input_count += 1
            next_input = now + 5.0

        time.sleep(0.4)

    raise RuntimeError(
        "120초 안에 메인 메뉴의 Story RAM 상태를 찾지 못했습니다."
    )


def capture(hwnd, path: Path, helper: Path):
    foreground(hwnd)
    cmd = [
        "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
        "-File", str(helper),
        "-Hwnd", str(int(hwnd)),
        "-OutFile", str(path),
    ]
    p = subprocess.run(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace"
    )
    if p.returncode != 0 or not path.exists():
        raise RuntimeError(
            "스크린샷 캡처 실패:\n" + (p.stdout or "")
        )
    return p.stdout


def find_dynamic_scratch_blocks(h, base, count=2):
    """
    Find disjoint, page-aligned, currently all-zero PSP RAM blocks.

    We deliberately search a high-RAM window that was mostly unused in prior
    BIA main-menu dumps, but we do NOT trust that historical observation:
    every byte is checked live before selection.

    Candidates are selected top-down. We also snapshot them later and restore
    them byte-for-byte, so even an all-zero block returns to its original state.
    """
    region_size = SCRATCH_SCAN_END - SCRATCH_SCAN_START
    data = guest_read(h, base, SCRATCH_SCAN_START, region_size)

    zero_block = b"\x00" * SCRATCH_BLOCK_SIZE
    candidates = []

    # Top-down, page aligned.
    last = SCRATCH_SCAN_END - SCRATCH_BLOCK_SIZE
    last &= ~(SCRATCH_ALIGN - 1)

    for addr in range(last, SCRATCH_SCAN_START - 1, -SCRATCH_ALIGN):
        off = addr - SCRATCH_SCAN_START
        if data[off:off + SCRATCH_BLOCK_SIZE] == zero_block:
            # Require a guard page of zeros before and after when available.
            guard_ok = True
            pre = off - SCRATCH_ALIGN
            post = off + SCRATCH_BLOCK_SIZE
            if pre >= 0:
                guard_ok &= (
                    data[pre:pre + SCRATCH_ALIGN] ==
                    b"\x00" * SCRATCH_ALIGN
                )
            if post + SCRATCH_ALIGN <= len(data):
                guard_ok &= (
                    data[post:post + SCRATCH_ALIGN] ==
                    b"\x00" * SCRATCH_ALIGN
                )
            if guard_ok:
                candidates.append(addr)

    chosen = []
    for addr in candidates:
        if all(
            addr + SCRATCH_BLOCK_SIZE <= other or
            other + SCRATCH_BLOCK_SIZE <= addr
            for other in chosen
        ):
            # Final live recheck immediately before reserving.
            now = guest_read(h, base, addr, SCRATCH_BLOCK_SIZE)
            if any(now):
                continue
            chosen.append(addr)
            if len(chosen) == count:
                break

    if len(chosen) != count:
        raise RuntimeError(
            f"Could not find {count} safe zero scratch blocks in "
            f"0x{SCRATCH_SCAN_START:08X}-0x{SCRATCH_SCAN_END:08X}; "
            f"found {len(chosen)}"
        )

    return chosen


def patch_stage15(h, base):
    """
    Expand each font atlas vertically through PPSSPP texture replacement,
    relocate all glyph records, rescale V coordinates for the taller texture,
    append a new independent U+D55C glyph record, and install a D5 page.
    """
    restores = []
    evidence = []

    scratch_blocks = find_dynamic_scratch_blocks(h, base, 2)

    layouts = [
        {
            "name": "TMR18",
            "page_table": 0x097238B4,
            "expected_glyph_ptr": 0x09723FD8,
            "scratch": scratch_blocks[0],
            "old_tex_h": 256,
            "new_tex_h": 512,
            "new_u0": 0.5 / 128.0,
            "new_u1": 17.5 / 128.0,
            "new_v0": 256.5 / 512.0,
            "new_v1": 272.5 / 512.0,
        },
        {
            "name": "AB18",
            "page_table": 0x097252A4,
            "expected_glyph_ptr": 0x097256E0,
            "scratch": scratch_blocks[1],
            "old_tex_h": 512,
            "new_tex_h": 1024,
            "new_u0": 0.5 / 128.0,
            "new_u1": 19.5 / 128.0,
            "new_v0": 512.5 / 1024.0,
            "new_v1": 531.5 / 1024.0,
        },
    ]

    OLD_COUNT = 151
    NEW_INDEX = 151
    NEW_COUNT = 152
    REC_SIZE = 24
    PAGE_SIZE = 512
    BLOCK_SIZE = 0x2000

    for f in layouts:
        page_table = f["page_table"]
        obj = page_table - 0x58
        count_addr = obj + 0x50
        glyph_ptr_addr = obj + 0x54

        old_count_raw = guest_read(h, base, count_addr, 2)
        old_count = struct.unpack("<H", old_count_raw)[0]
        old_ptr_raw = guest_read(h, base, glyph_ptr_addr, 4)
        old_ptr = struct.unpack("<I", old_ptr_raw)[0]

        if old_count != OLD_COUNT:
            raise RuntimeError(
                f"{f['name']}: expected glyph count {OLD_COUNT}, got {old_count}"
            )
        if old_ptr != f["expected_glyph_ptr"]:
            raise RuntimeError(
                f"{f['name']}: expected glyph ptr "
                f"0x{f['expected_glyph_ptr']:08X}, got 0x{old_ptr:08X}"
            )

        scratch = f["scratch"]
        new_glyph_ptr = scratch
        new_page = scratch + 0x1000

        old_scratch = guest_read(h, base, scratch, BLOCK_SIZE)
        if any(old_scratch):
            nz = next(i for i, b in enumerate(old_scratch) if b)
            raise RuntimeError(
                f"{f['name']}: dynamic scratch is no longer zero at "
                f"0x{scratch+nz:08X}"
            )
        restores.append((scratch, old_scratch))

        records = bytearray(
            guest_read(h, base, old_ptr, OLD_COUNT * REC_SIZE)
        )

        # Atlas height doubled. Original pixels remain in the top half.
        for idx in range(OLD_COUNT):
            off = idx * REC_SIZE
            v0 = struct.unpack_from("<f", records, off + 12)[0]
            v1 = struct.unpack_from("<f", records, off + 20)[0]
            struct.pack_into("<f", records, off + 12, v0 * 0.5)
            struct.pack_into("<f", records, off + 20, v1 * 0.5)

        guest_write(h, base, new_glyph_ptr, bytes(records))

        # Clone original A metrics and point only its UV to the new Korean cell.
        new_rec = bytearray(
            guest_read(h, base, old_ptr + A_MAP_VALUE * REC_SIZE, REC_SIZE)
        )
        struct.pack_into("<H", new_rec, 0, TEST_CP)
        struct.pack_into("<f", new_rec, 8,  f["new_u0"])
        struct.pack_into("<f", new_rec, 12, f["new_v0"])
        struct.pack_into("<f", new_rec, 16, f["new_u1"])
        struct.pack_into("<f", new_rec, 20, f["new_v1"])

        new_record_addr = new_glyph_ptr + NEW_INDEX * REC_SIZE
        guest_write(h, base, new_record_addr, bytes(new_rec))

        page = bytearray(PAGE_SIZE)
        struct.pack_into("<H", page, TEST_LOW * 2, NEW_INDEX)
        guest_write(h, base, new_page, bytes(page))

        restores.append((count_addr, old_count_raw))
        restores.append((glyph_ptr_addr, old_ptr_raw))
        guest_write(h, base, count_addr, struct.pack("<H", NEW_COUNT))
        guest_write(h, base, glyph_ptr_addr, struct.pack("<I", new_glyph_ptr))

        d5_slot = page_table + TEST_HIGH * 4
        old_d5 = guest_read(h, base, d5_slot, 4)
        restores.append((d5_slot, old_d5))
        guest_write(h, base, d5_slot, struct.pack("<I", new_page))

        rb_count = struct.unpack("<H", guest_read(h, base, count_addr, 2))[0]
        rb_ptr = struct.unpack("<I", guest_read(h, base, glyph_ptr_addr, 4))[0]
        rb_d5 = struct.unpack("<I", guest_read(h, base, d5_slot, 4))[0]
        rb_map = struct.unpack(
            "<H", guest_read(h, base, new_page + TEST_LOW*2, 2)
        )[0]

        if (rb_count, rb_ptr, rb_d5, rb_map) != (
            NEW_COUNT, new_glyph_ptr, new_page, NEW_INDEX
        ):
            raise RuntimeError(f"{f['name']}: read-back verification failed")

        evidence.append({
            "font": f["name"],
            "font_object": f"0x{obj:08X}",
            "page_table": f"0x{page_table:08X}",
            "old_glyph_count": OLD_COUNT,
            "new_glyph_count": NEW_COUNT,
            "old_glyph_ptr": f"0x{old_ptr:08X}",
            "new_glyph_ptr": f"0x{new_glyph_ptr:08X}",
            "new_record_index": NEW_INDEX,
            "new_record_addr": f"0x{new_record_addr:08X}",
            "new_record_codepoint": "U+D55C",
            "old_texture_height": f["old_tex_h"],
            "replacement_texture_height": f["new_tex_h"],
            "existing_record_v_scale": 0.5,
            "new_uv": [
                f["new_u0"], f["new_v0"], f["new_u1"], f["new_v1"]
            ],
            "new_D5_page": f"0x{new_page:08X}",
            "D55C_map_value": NEW_INDEX,
            "scratch": f"0x{scratch:08X}",
        })

    old_story = guest_read(h, base, STORY_GUEST, 10)
    if old_story != "Story".encode("utf-16le"):
        got = old_story.decode("utf-16le", "replace")
        raise RuntimeError(f"Expected Story before patch, got {got!r}")

    restores.append((STORY_GUEST, old_story))
    test = struct.pack("<5H", TEST_CP, TEST_CP, TEST_CP, TEST_CP, TEST_CP)
    guest_write(h, base, STORY_GUEST, test)

    if guest_read(h, base, STORY_GUEST, 10) != test:
        raise RuntimeError("Story U+D55C write verification failed")

    return restores, evidence

def restore(h, base, restores):
    errors = []
    for guest, old in reversed(restores):
        try:
            guest_write(h, base, guest, old)
        except Exception as e:
            errors.append(f"0x{guest:08X}: {e}")
    return errors


def make_zip(zip_path: Path, files):
    with zipfile.ZipFile(
        zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6
    ) as z:
        for src, arc in files:
            if src and Path(src).exists():
                z.write(src, arc)


def main():
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)

    script_dir = Path(__file__).resolve().parent
    helper = script_dir / "capture_ppsspp.ps1"
    texture_game_dir = None
    installed_replacements = []
    texture_game_dir, installed_replacements = install_test_replacements(script_dir)
    def _cleanup_stage15_textures():
        if installed_replacements:
            restore_test_replacements(installed_replacements)
    atexit.register(_cleanup_stage15_textures)
    exe = find_ppsspp_exe()
    iso = find_iso()
    cfg = write_append_config()

    ppsspp_log = ANALYSIS_DIR / "stage15_ppsspp_debug.log"
    before_png = ANALYSIS_DIR / "stage15_before.png"
    after_png = ANALYSIS_DIR / "stage15_after.png"
    report_path = ANALYSIS_DIR / "stage15_report.json"

    report = {
        "stage": 15,
        "purpose": "expanded atlas prototype: append an independent Hangul bitmap without replacing existing Latin glyphs",
        "ppsspp_exe": str(exe),
        "iso": str(iso),
        "append_config": str(cfg),
        "test_codepoint": "U+D55C",
        "expected_visual": "한한한한한 while Skirmish/Options/Profile remain visually normal",
        "renderer_function": "0x08C7F2FC",
        "glyph_lookup_instruction": "0x08C7F35C",
        "confirmed_font_object_layout": {"glyph_count_u16":"+0x50","glyph_pointer_u32":"+0x54","page_table":"+0x58","glyph_record_size":24},
        "stage14_new_glyph_index": 151,
        "stage14_new_glyph_count": 152,
        "stage14_uses_existing_U21_page": False,
        "replacement_texture_dir": str(texture_game_dir),
        "replacement_textures": [TMR_ATLAS, AB_ATLAS],
        "stage15_preserves_original_latin_atlas": True,
        "stage15_appended_bitmap": "U+D55C 한 in bottom half of expanded atlas",
    }

    log("=" * 80)
    log("BIA Stage 15 - expanded atlas + independent Hangul glyph")
    log("=" * 80)
    log(f"PPSSPP : {exe}")
    log(f"ISO    : {iso}")
    log(f"TEXTURE: {texture_game_dir}")
    log()

    # Shut down an existing PPSSPP instance so --appendconfig and the selected ISO
    # are guaranteed to apply to a fresh process.
    old_hwnd = user32.FindWindowW("PPSSPPWnd", None)
    if old_hwnd:
        old_pid, _ = get_pid_base(old_hwnd)
        log(f"[auto] 기존 PPSSPP 종료 요청 (PID {old_pid})")
        # WM_CLOSE
        user32.PostMessageW(old_hwnd, 0x0010, 0, 0)
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
        str(iso),
    ]

    log("[auto] PPSSPP 개발자 설정으로 ISO 실행")
    proc = subprocess.Popen(cmd)

    hwnd = find_ppsspp_hwnd(30.0)
    if not hwnd:
        raise RuntimeError("PPSSPP 창이 30초 안에 나타나지 않았습니다.")

    log("[auto] 메인 메뉴 Story RAM 상태 대기/자동 진행")
    pid, base = wait_for_story(hwnd, 120.0)
    report["pid"] = pid
    report["psp_base"] = f"0x{base:016X}"
    report["menu_detected"] = True

    log("[auto] BEFORE 스크린샷")
    capture(hwnd, before_png, helper)

    h = open_process(pid)
    restores = []
    try:
        restores, evidence = patch_stage15(h, base)
        report["fonts"] = evidence
        report["ram_patch_verified"] = True

        # Allow a few frames to redraw.
        foreground(hwnd)
        time.sleep(1.5)

        log("[auto] expanded atlas UV + 신규 한 glyph + D5 page 적용 완료")
        log("[auto] AFTER 스크린샷")
        capture(hwnd, after_png, helper)

        report["screenshot_before"] = str(before_png)
        report["screenshot_after"] = str(after_png)
        report["completed"] = True

        # Keep the visual patch long enough for screenshot only; then restore.
        errors = restore(h, base, restores)
        report["restore_errors"] = errors
        report["ram_restored"] = not errors
    finally:
        kernel32.CloseHandle(h)

    texture_restore_errors = restore_test_replacements(installed_replacements)
    installed_replacements.clear()
    report["texture_restore_errors"] = texture_restore_errors
    report["texture_replacements_restored"] = not texture_restore_errors

    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    upload = LOG_DIR / "bia_stage15_upload.zip"
    make_zip(upload, [
        (report_path, "stage15_report.json"),
        (before_png, "stage15_before.png"),
        (after_png, "stage15_after.png"),
        (ppsspp_log, "stage15_ppsspp_debug.log"),
        (cfg, "stage15_append.ini"),
    ])

    log()
    log("=" * 80)
    log("Stage 15 complete")
    log(f"Before : {before_png}")
    log(f"After  : {after_png}")
    log(f"Upload : {upload}")
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

        fail_zip = LOG_DIR / "fail_bia_stage15_upload.zip"
        extras = [
            (failure, "FAILURE.txt"),
            (ANALYSIS_DIR / "stage15_before.png", "stage15_before.png"),
            (ANALYSIS_DIR / "stage15_after.png", "stage15_after.png"),
            (ANALYSIS_DIR / "stage15_ppsspp_debug.log", "stage15_ppsspp_debug.log"),
            (ANALYSIS_DIR / "stage15_append.ini", "stage15_append.ini"),
        ]
        try:
            make_zip(fail_zip, extras)
        except Exception:
            pass

        print()
        print("=" * 80)
        print("STAGE 15 FAILED")
        print(f"Failure ZIP: {fail_zip}")
        print("=" * 80)
        traceback.print_exc()
        raise
