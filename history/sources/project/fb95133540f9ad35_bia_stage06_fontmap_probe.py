#!/usr/bin/env python3
from __future__ import annotations

import ctypes
from ctypes import wintypes
import json
import struct
import zipfile
from pathlib import Path

ROOT = Path(r"PROJECT_ROOT")
LOG_DIR = ROOT / "log"
ANALYSIS_DIR = ROOT / "analysis" / "stage06_fontmap_probe"

WM_APP = 0x8000
WM_USER_GET_BASE_POINTER = WM_APP + 0x3118

PROCESS_VM_READ = 0x0010
PROCESS_VM_WRITE = 0x0020
PROCESS_VM_OPERATION = 0x0008
PROCESS_QUERY_INFORMATION = 0x0400

PSP_START = 0x08800000
PSP_END   = 0x0A000000
PSP_SIZE  = PSP_END - PSP_START

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
user32 = ctypes.WinDLL("user32", use_last_error=True)

user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
user32.FindWindowW.restype = wintypes.HWND
user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.SendMessageW.restype = ctypes.c_ssize_t
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD

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

def u16(s: str) -> bytes:
    return s.encode("utf-16le")

def get_ppsspp():
    hwnd = user32.FindWindowW("PPSSPPWnd", None)
    if not hwnd:
        raise RuntimeError("PPSSPP window not found. Boot Brothers in Arms first.")

    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

    low = int(user32.SendMessageW(hwnd, WM_USER_GET_BASE_POINTER, 0, 0)) & 0xFFFFFFFF
    high = int(user32.SendMessageW(hwnd, WM_USER_GET_BASE_POINTER, 0, 1)) & 0xFFFFFFFF
    base = (high << 32) | low

    if not pid.value or not base:
        raise RuntimeError("Could not obtain PPSSPP process/base pointer.")
    return pid.value, base

def open_process(pid: int):
    h = kernel32.OpenProcess(
        PROCESS_VM_READ | PROCESS_VM_WRITE | PROCESS_VM_OPERATION |
        PROCESS_QUERY_INFORMATION,
        False, pid
    )
    if not h:
        e = ctypes.get_last_error()
        raise RuntimeError(
            f"OpenProcess failed ({e}). If PPSSPP is running as Administrator, "
            "run PowerShell as Administrator too."
        )
    return h

def rpm(h, addr: int, size: int) -> bytes:
    buf = (ctypes.c_ubyte * size)()
    got = ctypes.c_size_t()
    ok = kernel32.ReadProcessMemory(
        h, ctypes.c_void_p(addr), ctypes.byref(buf),
        size, ctypes.byref(got)
    )
    if not ok or got.value != size:
        raise RuntimeError(
            f"ReadProcessMemory failed at 0x{addr:X} "
            f"({got.value:#x}/{size:#x})"
        )
    return bytes(buf)

def wpm(h, addr: int, data: bytes):
    buf = ctypes.create_string_buffer(data, len(data))
    wrote = ctypes.c_size_t()
    ok = kernel32.WriteProcessMemory(
        h, ctypes.c_void_p(addr), buf, len(data), ctypes.byref(wrote)
    )
    if not ok or wrote.value != len(data):
        raise RuntimeError(f"WriteProcessMemory failed at 0x{addr:X}")

def find_font_tables(ram: bytes):
    """
    Magma font table discovered from the paired BIA RAM dumps.

    Record size = 24 bytes:
      +00 u16 Unicode codepoint
      +02 glyph metrics
      +08 four floats (UV rectangle)

    Both menu fonts have 150 records. Their unusual beginning is:
      20, 2E, 21, 22 ... 2D, 2F, 30...
    and the final record is U+2122 TRADE MARK SIGN.
    """
    rec = 24
    checks = [
        (0,   0x0020),
        (1,   0x002E),
        (2,   0x0021),
        (14,  0x002D),
        (15,  0x002F),
        (16,  0x0030),
        (25,  0x0039),
        (33,  0x0041),
        (58,  0x005A),
        (65,  0x0061),
        (90,  0x007A),
        (95,  0x00A1),
        (149, 0x2122),
    ]

    found = []
    pos = 0
    while True:
        pos = ram.find(b"\x20\x00", pos)
        if pos < 0:
            break
        if pos + rec * 150 <= len(ram):
            good = True
            for idx, expected in checks:
                cp = struct.unpack_from("<H", ram, pos + idx * rec)[0]
                if cp != expected:
                    good = False
                    break
            if good:
                # Capture representative A glyph metrics for classification/logging.
                a = ram[pos + 33*rec: pos + 34*rec]
                found.append({
                    "offset": pos,
                    "guest": PSP_START + pos,
                    "a_width": a[2],
                    "a_height": a[3],
                    "a_yoff": a[4],
                    "a_cell_height": a[5],
                    "a_advance": a[6],
                })
        pos += 1
    return found

def codepoint_at(ram: bytes, table_off: int, idx: int):
    return struct.unpack_from("<H", ram, table_off + idx*24)[0]

def main():
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 80)
    print("Brothers in Arms: D-Day - Stage 06 live font-map probe")
    print("=" * 80)
    print()
    print("BIA 메인 메뉴에서 STORY가 선택된 상태로 두세요.")
    input("준비되었으면 Enter... ")

    pid, base = get_ppsspp()
    h = open_process(pid)

    restored = []
    log = {
        "pid": pid,
        "psp_base": f"0x{base:016X}",
        "font_tables": [],
        "string_patch": None,
    }

    try:
        ram = rpm(h, base + PSP_START, PSP_SIZE)
        tables = find_font_tables(ram)

        if len(tables) < 2:
            raise RuntimeError(
                f"Expected at least two Magma font tables, found {len(tables)}."
            )

        print()
        print(f"Found {len(tables)} compatible 150-glyph font tables:")
        for n, t in enumerate(tables):
            print(
                f"  #{n}: PSP 0x{t['guest']:08X}  "
                f"A={t['a_width']}x{t['a_height']} "
                f"advance={t['a_advance']}"
            )

        # The two tables found in the user's dump correspond to the menu fonts.
        # The first is the serif TMR18 table used by STORY/SKIRMISH/etc;
        # the second is the AB18 table used elsewhere. Patch BOTH temporarily
        # so this probe is robust if a control switches fonts.
        #
        # Reuse the final five donor slots while retaining sorted codepoints:
        #   old: U+00FA ú, U+00FB û, U+00FC ü, U+00FF ÿ, U+2122 ™
        #   new: U+AE00 글, U+C2A4 스, U+D2B8 트, U+D14C 테, U+D55C 한
        #
        # Their sorted order is important if the renderer binary-searches
        # the glyph table.
        donor_indices = [145, 146, 147, 148, 149]
        expected_old = [0x00FA, 0x00FB, 0x00FC, 0x00FF, 0x2122]
        new_cps = [0xAE00, 0xC2A4, 0xD2B8, 0xD14C, 0xD55C]
        new_chars = ["글", "스", "트", "테", "한"]
        old_chars = ["ú", "û", "ü", "ÿ", "™"]

        for ti, t in enumerate(tables):
            table_log = dict(t)
            table_log["remaps"] = []
            for idx, old_cp, new_cp, old_ch, new_ch in zip(
                donor_indices, expected_old, new_cps, old_chars, new_chars
            ):
                guest = t["guest"] + idx * 24
                host = base + guest
                before = rpm(h, host, 2)
                actual = struct.unpack("<H", before)[0]
                if actual != old_cp:
                    raise RuntimeError(
                        f"Font table #{ti} record {idx}: "
                        f"expected U+{old_cp:04X}, got U+{actual:04X}"
                    )

                after = struct.pack("<H", new_cp)
                restored.append((host, before))
                wpm(h, host, after)
                if rpm(h, host, 2) != after:
                    raise RuntimeError(
                        f"Font map write verification failed at PSP 0x{guest:08X}"
                    )

                table_log["remaps"].append({
                    "record": idx,
                    "psp_address": f"0x{guest:08X}",
                    "old": f"U+{old_cp:04X} {old_ch}",
                    "new": f"U+{new_cp:04X} {new_ch}",
                })

            log["font_tables"].append(table_log)

        # Patch the proven live Story label to the five Hangul codepoints.
        story_guest = 0x08E41620
        story_host = base + story_guest
        old_story = u16("Story")
        new_story = u16("한글테스트")

        current = rpm(h, story_host, len(old_story))
        if current != old_story:
            try:
                got = current.decode("utf-16le", "replace")
            except Exception:
                got = current.hex()
            raise RuntimeError(
                f"Story runtime slot mismatch at 0x{story_guest:08X}: {got!r}. "
                "Return to the main menu and rerun."
            )

        restored.append((story_host, current))
        wpm(h, story_host, new_story)

        log["string_patch"] = {
            "psp_address": f"0x{story_guest:08X}",
            "old": "Story",
            "new": "한글테스트",
        }

        log_path = ANALYSIS_DIR / "stage06_fontmap_probe.json"
        log_path.write_text(
            json.dumps(log, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        print()
        print("=" * 80)
        print("FONT MAP PATCHED.")
        print()
        print("이제 PPSSPP 화면으로 돌아가 STORY 자리를 확인하세요.")
        print()
        print("성공하면 더 이상 □□□□□가 아니라 기존 폰트의 donor 글리프가")
        print("5개 조합으로 표시되어야 합니다.")
        print()
        print("예상 매핑:")
        print("  한 -> 원래 ™ 글리프")
        print("  글 -> 원래 ú 글리프")
        print("  테 -> 원래 ÿ 글리프")
        print("  스 -> 원래 û 글리프")
        print("  트 -> 원래 ü 글리프")
        print()
        print("즉 표시 순서는 대략: ™ ú ÿ û ü")
        print("(폰트 모양에 따라 악센트가 작게 보일 수 있음)")
        print()
        print("스크린샷을 찍은 뒤 이 콘솔에서 Enter를 누르면")
        print("문자열과 두 폰트 테이블을 모두 원래대로 복구합니다.")
        print("=" * 80)
        input()

    finally:
        # Restore in reverse write order.
        for host, original in reversed(restored):
            try:
                wpm(h, host, original)
            except Exception:
                pass
        kernel32.CloseHandle(h)

    upload = LOG_DIR / "bia_stage06_fontmap_upload.zip"
    with zipfile.ZipFile(upload, "w", zipfile.ZIP_DEFLATED) as z:
        log_path = ANALYSIS_DIR / "stage06_fontmap_probe.json"
        if log_path.exists():
            z.write(log_path, "stage06_fontmap_probe.json")

    print()
    print("RAM restored.")
    print(f"Upload log: {upload}")
    return 0

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print()
        print("ERROR:", e)
        input("Enter를 누르면 종료합니다...")
        raise
