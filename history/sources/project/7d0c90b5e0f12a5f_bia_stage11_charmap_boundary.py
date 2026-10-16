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
ANALYSIS_DIR = ROOT / "analysis" / "stage11_charmap_boundary"

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
user32.SendMessageW.argtypes = [
    wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM
]
user32.SendMessageW.restype = ctypes.c_ssize_t
user32.GetWindowThreadProcessId.argtypes = [
    wintypes.HWND, ctypes.POINTER(wintypes.DWORD)
]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD

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


def get_ppsspp():
    hwnd = user32.FindWindowW("PPSSPPWnd", None)
    if not hwnd:
        raise RuntimeError("PPSSPP window not found. Boot BIA first.")

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
        raise RuntimeError("Could not obtain PPSSPP PID/base pointer.")

    return pid.value, base


def open_process(pid):
    h = kernel32.OpenProcess(
        PROCESS_VM_READ | PROCESS_VM_WRITE |
        PROCESS_VM_OPERATION | PROCESS_QUERY_INFORMATION,
        False, pid
    )
    if not h:
        raise RuntimeError(
            f"OpenProcess failed ({ctypes.get_last_error()}). "
            "Run PowerShell as Administrator if PPSSPP is elevated."
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


def find_font_tables(ram):
    rec = 24
    checks = [
        (0,0x20),(1,0x2E),(2,0x21),(14,0x2D),(15,0x2F),
        (16,0x30),(25,0x39),(33,0x41),(58,0x5A),
        (65,0x61),(90,0x7A),(95,0xA1),
    ]

    found = []
    pos = 0
    while True:
        pos = ram.find(b"\x20\x00", pos)
        if pos < 0:
            break

        if pos + 150 * rec <= len(ram):
            if all(
                struct.unpack_from("<H", ram, pos + i*rec)[0] == cp
                for i, cp in checks
            ):
                found.append({
                    "ram_off": pos,
                    "guest": PSP_START + pos,
                })
        pos += 1

    return found


def map_matches(buf, off):
    # Known Stage 08 direct charmap semantics:
    # value = glyph_index + 1, zero = missing.
    checks = {
        0x20: 1,
        0x21: 3,
        0x2E: 2,
        0x30: 17,
        0x39: 26,
        0x41: 34,  # A
        0x5A: 59,
        0x61: 66,
        0x7A: 91,
        0xA1: 96,
    }

    if off < 0 or off + 512 > len(buf):
        return False

    return all(
        struct.unpack_from("<H", buf, off + cp*2)[0] == val
        for cp, val in checks.items()
    )


def find_charmap_after_table(ram, table_off):
    end = table_off + 150 * 24
    hits = []

    for off in range(end, min(len(ram) - 512, end + 0x100), 2):
        if map_matches(ram, off):
            hits.append(off)

    if len(hits) != 1:
        raise RuntimeError(
            f"Expected exactly one charmap after table "
            f"0x{PSP_START + table_off:08X}, got {len(hits)}"
        )

    return PSP_START + hits[0]


def main():
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 80)
    print("BIA Stage 11 - charmap boundary probe")
    print("=" * 80)
    print()
    print("메인 메뉴에서 STORY가 선택된 상태로 두세요.")
    print("Texture Replacement 설정은 이번 테스트와 관계없습니다.")
    input("준비되었으면 Enter... ")

    pid, base = get_ppsspp()
    h = open_process(pid)

    restored = []
    report = {
        "pid": pid,
        "psp_base": f"0x{base:016X}",
        "test_codepoint": "U+0100",
        "target_glyph": "A (glyph index 33, map value 34)",
        "font_tables": [],
    }

    try:
        ram = rpm(h, base + PSP_START, PSP_SIZE)
        tables = find_font_tables(ram)

        if len(tables) < 2:
            raise RuntimeError(
                f"Expected at least two font tables, found {len(tables)}"
            )

        charmaps = []
        for t in tables:
            cmap = find_charmap_after_table(ram, t["ram_off"])
            charmaps.append(cmap)

            # Inspect a small area just beyond the nominal 256 entries.
            after = rpm(h, base + cmap + 0x200, 0x20)
            report["font_tables"].append({
                "font_table": f"0x{t['guest']:08X}",
                "charmap": f"0x{cmap:08X}",
                "bytes_after_nominal_map": after.hex(" "),
            })

        print()
        print("Charmaps:")
        for c in charmaps:
            print(f"  0x{c:08X}")

        # U+0100 is exactly one entry past a 256-entry u16 table.
        # Patch that word in both font maps to A glyph (33+1 = 34).
        for cmap in charmaps:
            guest = cmap + 0x0100 * 2
            host = base + guest

            old = rpm(h, host, 2)
            restored.append((host, old))

            wpm(h, host, struct.pack("<H", 34))

            if rpm(h, host, 2) != struct.pack("<H", 34):
                raise RuntimeError(
                    f"Boundary map write verification failed at 0x{guest:08X}"
                )

        # Proven live Story slot, 5 UTF-16 code units.
        story_guest = 0x08E41620
        story_host = base + story_guest
        old_story = rpm(h, story_host, 10)

        if old_story != "Story".encode("utf-16le"):
            got = old_story.decode("utf-16le", "replace")
            raise RuntimeError(
                f"Expected Story at 0x{story_guest:08X}, got {got!r}. "
                "Return to main menu and rerun."
            )

        restored.append((story_host, old_story))

        # Five U+0100 code units.
        test = struct.pack("<5H", 0x0100, 0x0100, 0x0100, 0x0100, 0x0100)
        wpm(h, story_host, test)

        print()
        print("=" * 80)
        print("화면을 확인하세요.")
        print()
        print("Story 문자열은 실제 ASCII A가 아니라 U+0100을 5개 넣었습니다.")
        print("그리고 nominal 256-entry charmap 바로 다음 word를")
        print("A glyph(index 33)로 설정했습니다.")
        print()
        print("성공하면:")
        print()
        print("    AAAAA")
        print()
        print("가 보여야 합니다.")
        print()
        print("AAAAA가 나오면 렌더러에 0xFF 범위 체크가 없다는 뜻이고,")
        print("다음 단계에서 charmap을 큰 RAM 영역으로 relocate해서")
        print("U+D55C 같은 실제 한글 codepoint를 직접 매핑할 수 있습니다.")
        print()
        print("□□□□□가 나오면 0xFF 범위 체크가 따로 존재하는 것입니다.")
        print("=" * 80)

        while True:
            ans = input("화면에 AAAAA가 보이나요? [y/n/?] ").strip().lower()
            if ans in ("y", "n", "?"):
                report["visual_result"] = ans
                break

        report_path = ANALYSIS_DIR / "stage11_report.json"
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        input("스크린샷을 찍었으면 Enter를 눌러 RAM을 복구합니다... ")

    finally:
        for host, old in reversed(restored):
            try:
                wpm(h, host, old)
            except Exception:
                pass
        kernel32.CloseHandle(h)

    upload = LOG_DIR / "bia_stage11_upload.zip"
    with zipfile.ZipFile(upload, "w", zipfile.ZIP_DEFLATED) as z:
        rp = ANALYSIS_DIR / "stage11_report.json"
        if rp.exists():
            z.write(rp, rp.name)

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
