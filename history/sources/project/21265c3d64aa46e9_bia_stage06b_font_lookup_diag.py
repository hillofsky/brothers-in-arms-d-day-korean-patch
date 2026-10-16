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
ANALYSIS_DIR = ROOT / "analysis" / "stage06b_font_lookup_diag"

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
        raise RuntimeError("PPSSPP window not found. Boot BIA first.")
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    low = int(user32.SendMessageW(hwnd, WM_USER_GET_BASE_POINTER, 0, 0)) & 0xFFFFFFFF
    high = int(user32.SendMessageW(hwnd, WM_USER_GET_BASE_POINTER, 0, 1)) & 0xFFFFFFFF
    base = (high << 32) | low
    if not pid.value or not base:
        raise RuntimeError("Could not obtain PPSSPP PID/base pointer.")
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
            f"OpenProcess failed ({e}). Run PowerShell elevated if PPSSPP is elevated."
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
        raise RuntimeError(f"ReadProcessMemory failed at 0x{addr:X}")
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
    rec = 24
    checks = [
        (0,0x0020),(1,0x002E),(2,0x0021),(14,0x002D),(15,0x002F),
        (16,0x0030),(25,0x0039),(33,0x0041),(58,0x005A),
        (65,0x0061),(90,0x007A),(95,0x00A1),(149,0x2122)
    ]
    out = []
    pos = 0
    while True:
        pos = ram.find(b"\x20\x00", pos)
        if pos < 0:
            break
        if pos + rec*150 <= len(ram):
            if all(struct.unpack_from("<H",ram,pos+i*rec)[0] == cp for i,cp in checks):
                out.append(PSP_START + pos)
        pos += 1
    return out

def set_story(h, base, text: str):
    guest = 0x08E41620
    data = u16(text)
    if len(data) != 10:
        raise RuntimeError(f"Story test string must be 5 UTF-16 units: {text!r}")
    wpm(h, base + guest, data)

def patch_tail_codepoints(h, base, tables, cps):
    if len(cps) != 5:
        raise RuntimeError("Need 5 codepoints.")
    # Last 5 records are indices 145..149.
    for table in tables:
        for idx, cp in zip(range(145,150), cps):
            wpm(h, base + table + idx*24, struct.pack("<H",cp))

def restore_table_tail(h, base, tables):
    originals = [0x00FA,0x00FB,0x00FC,0x00FF,0x2122]
    patch_tail_codepoints(h, base, tables, originals)

def answer(prompt):
    while True:
        s = input(prompt + " [y/n/?] ").strip().lower()
        if s in ("y","n","?"):
            return s

def main():
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)

    print("="*80)
    print("BIA Stage 06B - font lookup diagnostic")
    print("="*80)
    print("메인 메뉴에서 STORY가 선택된 상태로 두세요.")
    input("준비되었으면 Enter... ")

    pid, base = get_ppsspp()
    h = open_process(pid)

    results = {
        "pid": pid,
        "psp_base": f"0x{base:016X}",
        "phases": {}
    }

    try:
        ram = rpm(h, base + PSP_START, PSP_SIZE)
        tables = find_font_tables(ram)
        if len(tables) < 2:
            raise RuntimeError(f"Expected >=2 font tables, found {len(tables)}")
        print("font tables:", ", ".join(f"0x{x:08X}" for x in tables))

        # Save original live Story bytes.
        story_host = base + 0x08E41620
        original_story = rpm(h, story_host, 10)
        if original_story != u16("Story"):
            got = original_story.decode("utf-16le","replace")
            raise RuntimeError(f"Expected Story at 0x08E41620, got {got!r}")

        # PHASE A: supported original donor chars.
        restore_table_tail(h, base, tables)
        set_story(h, base, "úûüÿ™")
        print("\n" + "="*80)
        print("PHASE A")
        print("STORY 자리가 기존 확장문자 5개로 보여야 합니다: ú û ü ÿ ™")
        print("PPSSPP 화면을 확인하세요.")
        a = answer("실제 글리프로 보이나요? (□가 아니라 글자)")
        results["phases"]["A_original_donors"] = a

        # PHASE B: NEW low-range codepoints, still below U+2122.
        low_cps = [0x0100,0x0101,0x0102,0x0103,0x0104]
        patch_tail_codepoints(h, base, tables, low_cps)
        set_story(h, base, "ĀāĂăĄ")
        print("\n" + "="*80)
        print("PHASE B")
        print("원래 폰트에 없던 U+0100~U+0104로 donor 레코드를 재매핑했습니다.")
        print("화면에서 □ 대신 donor 글리프(ú û ü ÿ ™ 모양)가 나오면")
        print("24바이트 테이블의 코드포인트 lookup이 실시간으로 작동한다는 뜻입니다.")
        b = answer("□가 아니라 donor 글리프로 보이나요?")
        results["phases"]["B_low_new_codepoints"] = b

        # PHASE C: sorted Korean codepoints in table; word order in string is natural Korean.
        # Keep table codepoints strictly ascending.
        hangul_sorted = [0xAE00,0xC2A4,0xD14C,0xD2B8,0xD55C]  # 글 스 테 트 한
        patch_tail_codepoints(h, base, tables, hangul_sorted)
        set_story(h, base, "한글테스트")
        print("\n" + "="*80)
        print("PHASE C")
        print("이번에는 donor 레코드를 한글 코드포인트로 '정렬된 순서'로 넣었습니다:")
        print("  글(U+AE00), 스(U+C2A4), 테(U+D14C), 트(U+D2B8), 한(U+D55C)")
        print("Story 문자열은 '한글테스트'입니다.")
        c = answer("□가 아니라 donor 글리프로 보이나요?")
        results["phases"]["C_sorted_hangul"] = c

        # Diagnostic scan for likely cached max=U+2122 values near each font table.
        ram_after = rpm(h, base + PSP_START, PSP_SIZE)
        nearby = []
        for table in tables:
            off = table - PSP_START
            lo = max(0, off - 0x400)
            hi = min(len(ram_after), off + 150*24 + 0x400)
            region = ram_after[lo:hi]
            p = 0
            while True:
                q = region.find(b"\x22\x21\x00\x00", p)
                if q < 0:
                    break
                guest = PSP_START + lo + q
                # Exclude the codepoint field inside the final glyph record itself.
                if guest != table + 149*24:
                    nearby.append({
                        "table": f"0x{table:08X}",
                        "candidate_u32_2122": f"0x{guest:08X}",
                        "delta_from_table": guest - table,
                    })
                p = q + 1
        results["nearby_cached_max_candidates"] = nearby

        log_path = ANALYSIS_DIR / "stage06b_results.json"
        log_path.write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding="utf-8")

        print("\n결과 기록 완료.")
        print("A/B/C 중 어떤 단계가 y였는지가 다음 패치를 결정합니다.")
        input("Enter를 누르면 RAM을 원상복구합니다... ")

        restore_table_tail(h, base, tables)
        wpm(h, story_host, original_story)

    finally:
        kernel32.CloseHandle(h)

    upload = LOG_DIR / "bia_stage06b_upload.zip"
    with zipfile.ZipFile(upload,"w",zipfile.ZIP_DEFLATED) as z:
        p = ANALYSIS_DIR / "stage06b_results.json"
        if p.exists():
            z.write(p,p.name)

    print(f"Upload ZIP: {upload}")
    return 0

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print("\nERROR:",e)
        input("Enter를 누르면 종료합니다...")
        raise
