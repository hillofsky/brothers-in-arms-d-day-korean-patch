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
ANALYSIS_DIR = ROOT / "analysis" / "stage08_direct_charmap_probe"

PSP_START = 0x08800000
PSP_END   = 0x0A000000
PSP_SIZE  = PSP_END - PSP_START

WM_APP = 0x8000
WM_USER_GET_BASE_POINTER = WM_APP + 0x3118

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

def get_ppsspp():
    hwnd = user32.FindWindowW("PPSSPPWnd", None)
    if not hwnd:
        raise RuntimeError("PPSSPP window not found. Boot BIA first.")

    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

    lo = int(user32.SendMessageW(hwnd, WM_USER_GET_BASE_POINTER, 0, 0)) & 0xFFFFFFFF
    hi = int(user32.SendMessageW(hwnd, WM_USER_GET_BASE_POINTER, 0, 1)) & 0xFFFFFFFF
    base = (hi << 32) | lo

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
            f"OpenProcess failed ({e}). If PPSSPP is elevated, "
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
        raise RuntimeError(f"ReadProcessMemory failed at host 0x{addr:X}")
    return bytes(buf)

def wpm(h, addr: int, data: bytes):
    buf = ctypes.create_string_buffer(data, len(data))
    wrote = ctypes.c_size_t()
    ok = kernel32.WriteProcessMemory(
        h, ctypes.c_void_p(addr), buf, len(data), ctypes.byref(wrote)
    )
    if not ok or wrote.value != len(data):
        raise RuntimeError(f"WriteProcessMemory failed at host 0x{addr:X}")

def u16(s: str) -> bytes:
    return s.encode("utf-16le")

def find_font_tables(ram: bytes):
    rec = 24
    common = [
        (0,0x0020),(1,0x002E),(2,0x0021),(14,0x002D),
        (15,0x002F),(16,0x0030),(25,0x0039),
        (33,0x0041),(58,0x005A),(65,0x0061),
        (90,0x007A),(95,0x00A1),
    ]

    found = []
    pos = 0
    while True:
        pos = ram.find(b"\x20\x00", pos)
        if pos < 0:
            break

        if pos + 150*rec <= len(ram):
            if all(struct.unpack_from("<H", ram, pos+i*rec)[0] == cp
                   for i,cp in common):
                final_cp = struct.unpack_from("<H", ram, pos+149*rec)[0]
                if final_cp in (0x2122, 0xD55C):
                    found.append({
                        "ram_off": pos,
                        "guest": PSP_START + pos,
                        "final_cp": final_cp,
                    })
        pos += 1
    return found

def map_matches(buf: bytes, off: int):
    # 256 u16 direct lookup slots. Value = glyph_index + 1, 0 = missing.
    checks = {
        0x20: 1,    # space -> glyph 0 + 1
        0x21: 3,    # !     -> glyph 2 + 1
        0x22: 4,
        0x2D: 15,
        0x2E: 2,    # .     -> glyph 1 + 1
        0x2F: 16,
        0x30: 17,
        0x39: 26,
        0x41: 34,   # A     -> glyph 33 + 1
        0x5A: 59,
        0x61: 66,   # a     -> glyph 65 + 1
        0x7A: 91,
        0xA1: 96,
    }

    if off < 0 or off + 512 > len(buf):
        return False

    for cp, expected in checks.items():
        got = struct.unpack_from("<H", buf, off + cp*2)[0]
        if got != expected:
            return False
    return True

def find_charmap_after_table(ram: bytes, table_off: int):
    rec_end = table_off + 150*24

    # Retail data uses only small alignment/padding between records and map.
    # Search a generous 0x100-byte window and validate the ASCII mapping.
    hits = []
    for off in range(rec_end, min(len(ram)-512, rec_end+0x100), 2):
        if map_matches(ram, off):
            hits.append(off)

    if len(hits) != 1:
        raise RuntimeError(
            f"Expected exactly one 256-entry charmap after table "
            f"0x{PSP_START+table_off:08X}; found {len(hits)}"
        )
    return hits[0]

def main():
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 80)
    print("Brothers in Arms: D-Day - Stage 08 direct charmap probe")
    print("=" * 80)
    print()
    print("원본 ISO든 Stage07 ISO든 상관없습니다.")
    print("메인 메뉴에서 STORY가 선택된 상태로 두세요.")
    input("준비되었으면 Enter... ")

    pid, base = get_ppsspp()
    h = open_process(pid)

    restored = []
    report = {
        "pid": pid,
        "psp_base": f"0x{base:016X}",
        "font_tables": [],
        "test_codepoints": ["U+0080","U+0081","U+0082","U+0083","U+0084"],
        "mapped_to": ["A","B","C","D","E"],
    }

    try:
        ram = rpm(h, base + PSP_START, PSP_SIZE)
        tables = find_font_tables(ram)

        if len(tables) < 2:
            raise RuntimeError(f"Expected at least 2 font tables, found {len(tables)}")

        print()
        print(f"Found {len(tables)} font table(s).")

        charmaps = []
        for i,t in enumerate(tables):
            cmap_off = find_charmap_after_table(ram, t["ram_off"])
            cmap_guest = PSP_START + cmap_off

            info = {
                "font_table": f"0x{t['guest']:08X}",
                "final_record_codepoint": f"U+{t['final_cp']:04X}",
                "direct_charmap": f"0x{cmap_guest:08X}",
            }
            report["font_tables"].append(info)
            charmaps.append(cmap_guest)

            print(
                f"  #{i}: table=0x{t['guest']:08X} "
                f"charmap=0x{cmap_guest:08X} "
                f"final=U+{t['final_cp']:04X}"
            )

        # Map U+0080..U+0084 to A..E.
        # Values are glyph_index + 1:
        # A index=33 => 34, B=>35, C=>36, D=>37, E=>38.
        for cmap_guest in charmaps:
            for cp, value in zip(range(0x80,0x85), range(34,39)):
                guest = cmap_guest + cp*2
                host = base + guest
                old = rpm(h, host, 2)
                oldv = struct.unpack("<H", old)[0]

                # These slots should be unused in the original font.
                if oldv != 0:
                    raise RuntimeError(
                        f"Expected empty U+{cp:04X} map slot at 0x{guest:08X}, "
                        f"found {oldv}"
                    )

                restored.append((host, old))
                wpm(h, host, struct.pack("<H", value))

        # Proven live main-menu Story slot.
        story_guest = 0x08E41620
        story_host = base + story_guest
        old_story = rpm(h, story_host, 10)

        if old_story != u16("Story"):
            got = old_story.decode("utf-16le", "replace")
            raise RuntimeError(
                f"Expected 'Story' at PSP 0x{story_guest:08X}, got {got!r}. "
                "Return to main menu and rerun."
            )

        restored.append((story_host, old_story))

        # Five custom codepoints, not ASCII "ABCDE".
        test_text = b"".join(struct.pack("<H", cp) for cp in range(0x80,0x85))
        wpm(h, story_host, test_text)

        if rpm(h, story_host, len(test_text)) != test_text:
            raise RuntimeError("Story test write verification failed.")

        report_path = ANALYSIS_DIR / "stage08_report.json"
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        print()
        print("=" * 80)
        print("LOOKUP MAP PATCHED")
        print()
        print("Story 문자열에는 실제 A/B/C/D/E가 아니라")
        print("U+0080 U+0081 U+0082 U+0083 U+0084를 넣었습니다.")
        print()
        print("그런데 lookup map에서 각각 A/B/C/D/E 글리프로 연결했습니다.")
        print()
        print("성공하면 화면의 STORY 자리가:")
        print()
        print("    ABCDE")
        print()
        print("로 보여야 합니다.")
        print()
        print("지금 PPSSPP 화면을 확인하고 스크린샷을 찍으세요.")
        print("=" * 80)

        while True:
            ans = input("화면에 ABCDE가 보이나요? [y/n/?] ").strip().lower()
            if ans in ("y","n","?"):
                report["visual_result"] = ans
                break

        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        input("Enter를 누르면 RAM을 원래대로 복구합니다... ")

    finally:
        for host, old in reversed(restored):
            try:
                wpm(h, host, old)
            except Exception:
                pass
        kernel32.CloseHandle(h)

    upload = LOG_DIR / "bia_stage08_upload.zip"
    with zipfile.ZipFile(upload, "w", zipfile.ZIP_DEFLATED) as z:
        report_path = ANALYSIS_DIR / "stage08_report.json"
        if report_path.exists():
            z.write(report_path, report_path.name)

    print()
    print("RAM restored.")
    print(f"Upload ZIP: {upload}")
    return 0

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print()
        print("ERROR:", e)
        input("Enter를 누르면 종료합니다...")
        raise
