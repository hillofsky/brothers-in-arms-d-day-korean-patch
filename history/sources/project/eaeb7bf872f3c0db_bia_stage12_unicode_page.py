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
ANALYSIS_DIR = ROOT / "analysis" / "stage12_unicode_page"

PSP_START = 0x08800000
PSP_END = 0x0A000000
PSP_SIZE = PSP_END - PSP_START

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
    ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t),
]
kernel32.ReadProcessMemory.restype = wintypes.BOOL
kernel32.WriteProcessMemory.argtypes = [
    wintypes.HANDLE, wintypes.LPVOID, wintypes.LPCVOID,
    ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t),
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
        raise RuntimeError("Could not obtain PPSSPP PID/base pointer.")
    return pid.value, base


def open_process(pid):
    handle = kernel32.OpenProcess(
        PROCESS_VM_READ | PROCESS_VM_WRITE | PROCESS_VM_OPERATION | PROCESS_QUERY_INFORMATION,
        False,
        pid,
    )
    if not handle:
        raise RuntimeError(f"OpenProcess failed ({ctypes.get_last_error()}).")
    return handle


def rpm(handle, address, size):
    buf = (ctypes.c_ubyte * size)()
    got = ctypes.c_size_t()
    ok = kernel32.ReadProcessMemory(
        handle, ctypes.c_void_p(address), ctypes.byref(buf), size, ctypes.byref(got)
    )
    if not ok or got.value != size:
        raise RuntimeError(f"ReadProcessMemory failed at 0x{address:X}")
    return bytes(buf)


def wpm(handle, address, data):
    buf = ctypes.create_string_buffer(data, len(data))
    wrote = ctypes.c_size_t()
    ok = kernel32.WriteProcessMemory(
        handle, ctypes.c_void_p(address), buf, len(data), ctypes.byref(wrote)
    )
    if not ok or wrote.value != len(data):
        raise RuntimeError(f"WriteProcessMemory failed at 0x{address:X}")


def find_font_tables(ram):
    rec = 24
    checks = [
        (0, 0x20), (1, 0x2E), (2, 0x21), (14, 0x2D), (15, 0x2F),
        (16, 0x30), (25, 0x39), (33, 0x41), (58, 0x5A),
        (65, 0x61), (90, 0x7A), (95, 0xA1),
    ]
    found = []
    pos = 0
    while True:
        pos = ram.find(b"\x20\x00", pos)
        if pos < 0:
            break
        if pos + 150 * rec <= len(ram) and all(
            struct.unpack_from("<H", ram, pos + i * rec)[0] == cp for i, cp in checks
        ):
            found.append({"ram_off": pos, "guest": PSP_START + pos})
        pos += 1
    return found


def map_matches(buf, off):
    checks = {
        0x20: 1, 0x21: 3, 0x2E: 2, 0x30: 17, 0x39: 26,
        0x41: 34, 0x5A: 59, 0x61: 66, 0x7A: 91, 0xA1: 96,
    }
    return off >= 0 and off + 512 <= len(buf) and all(
        struct.unpack_from("<H", buf, off + cp * 2)[0] == value
        for cp, value in checks.items()
    )


def find_charmap_after_table(ram, table_off):
    end = table_off + 150 * 24
    hits = [
        off for off in range(end, min(len(ram) - 512, end + 0x100), 2)
        if map_matches(ram, off)
    ]
    if len(hits) != 1:
        raise RuntimeError(
            f"Expected one charmap after 0x{PSP_START + table_off:08X}, got {len(hits)}"
        )
    return PSP_START + hits[0]


def find_page_table(ram, charmap):
    pattern = struct.pack("<I", charmap)
    hits = []
    pos = 0
    while True:
        pos = ram.find(pattern, pos)
        if pos < 0:
            break
        guest = PSP_START + pos
        # The font page table is 256 aligned pointer slots.  The known U+21xx
        # page at slot 0x21 is a useful structural check.
        if pos + 0x88 <= len(ram):
            page21 = struct.unpack_from("<I", ram, pos + 0x84)[0]
            if PSP_START <= page21 < PSP_END:
                hits.append((guest, page21))
        pos += 1
    if len(hits) != 1:
        raise RuntimeError(f"Expected one Unicode page table for 0x{charmap:08X}, got {hits}")
    return hits[0]


def main():
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 80)
    print("BIA Stage 12 - native Unicode page-table probe")
    print("=" * 80)
    print()
    print("메인 메뉴에서 STORY가 보이는 상태로 두세요.")
    input("준비되었으면 Enter... ")

    pid, base = get_ppsspp()
    handle = open_process(pid)
    restored = []
    report = {
        "pid": pid,
        "psp_base": f"0x{base:016X}",
        "renderer_function": "0x08C7F2FC",
        "page_lookup_instruction": "0x08C7F31C lw a0,0(a0)",
        "glyph_lookup_instruction": "0x08C7F35C lhu v0,0(v0)",
        "test_codepoint": "U+D55C",
        "target_glyph": "A (glyph index 33, map value 34)",
        "fonts": [],
    }

    try:
        ram = rpm(handle, base + PSP_START, PSP_SIZE)
        tables = find_font_tables(ram)
        if len(tables) < 2:
            raise RuntimeError(f"Expected at least two font tables, found {len(tables)}")

        for table in tables:
            charmap = find_charmap_after_table(ram, table["ram_off"])
            page_table, scratch_page = find_page_table(ram, charmap)

            d5_slot_guest = page_table + 0xD5 * 4
            d55c_entry_guest = scratch_page + 0x5C * 2
            d5_slot_host = base + d5_slot_guest
            d55c_entry_host = base + d55c_entry_guest

            old_slot = rpm(handle, d5_slot_host, 4)
            old_entry = rpm(handle, d55c_entry_host, 2)
            restored.extend([(d5_slot_host, old_slot), (d55c_entry_host, old_entry)])

            wpm(handle, d55c_entry_host, struct.pack("<H", 34))
            wpm(handle, d5_slot_host, struct.pack("<I", scratch_page))

            if rpm(handle, d5_slot_host, 4) != struct.pack("<I", scratch_page):
                raise RuntimeError(f"U+D5xx page pointer write failed at 0x{d5_slot_guest:08X}")
            if rpm(handle, d55c_entry_host, 2) != struct.pack("<H", 34):
                raise RuntimeError(f"U+D55C entry write failed at 0x{d55c_entry_guest:08X}")

            report["fonts"].append({
                "font_table": f"0x{table['guest']:08X}",
                "page_table": f"0x{page_table:08X}",
                "page_00": f"0x{charmap:08X}",
                "borrowed_page_21": f"0x{scratch_page:08X}",
                "patched_page_D5_slot": f"0x{d5_slot_guest:08X}",
                "patched_D55C_entry": f"0x{d55c_entry_guest:08X}",
            })

        story_guest = 0x08E41620
        story_host = base + story_guest
        old_story = rpm(handle, story_host, 10)
        if old_story != "Story".encode("utf-16le"):
            got = old_story.decode("utf-16le", "replace")
            raise RuntimeError(
                f"Expected Story at 0x{story_guest:08X}, got {got!r}. Return to main menu and rerun."
            )
        restored.append((story_host, old_story))
        wpm(handle, story_host, struct.pack("<5H", *([0xD55C] * 5)))

        print()
        print("U+D55C의 상위 바이트 D5를 실제 Unicode page table에 연결했습니다.")
        print("그 페이지의 0x5C 엔트리는 A glyph를 가리킵니다.")
        print()
        print("성공하면 화면의 Story 위치가 AAAAA로 보입니다.")
        print("A 텍스처를 한 글리프로 교체해 둔 상태라면 한한한한한으로 보일 수 있습니다.")
        print()
        while True:
            answer = input("정상 글리프가 보이나요? [y/n/?] ").strip().lower()
            if answer in ("y", "n", "?"):
                report["visual_result"] = answer
                break

        report_path = ANALYSIS_DIR / "stage12_report.json"
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        input("스크린샷을 찍었으면 Enter를 눌러 RAM을 복구합니다... ")

    finally:
        for host_address, old_data in reversed(restored):
            try:
                wpm(handle, host_address, old_data)
            except Exception:
                pass
        kernel32.CloseHandle(handle)

    upload = LOG_DIR / "bia_stage12_upload.zip"
    with zipfile.ZipFile(upload, "w", zipfile.ZIP_DEFLATED) as archive:
        report_path = ANALYSIS_DIR / "stage12_report.json"
        if report_path.exists():
            archive.write(report_path, report_path.name)

    print()
    print("RAM restored.")
    print(f"Upload ZIP: {upload}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print()
        print("ERROR:", exc)
        input("Enter를 누르면 종료합니다...")
        raise
