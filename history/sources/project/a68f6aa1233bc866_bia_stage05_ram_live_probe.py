#!/usr/bin/env python3
from __future__ import annotations

import ctypes
from ctypes import wintypes
from pathlib import Path
import hashlib
import json
import time
import zipfile

ROOT = Path(r"PROJECT_ROOT")
LOG_DIR = ROOT / "log"
STAGE_DIR = ROOT / "analysis" / "stage05_ram_live_probe"

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

def u16(s: str) -> bytes:
    return s.encode("utf-16le")

# Addresses proven from the user's paired RAM dumps.
# All replacements preserve UTF-16 code-unit count.
PATCHES = [
    # Static/localized-looking title-menu strings.
    (0x08E41620, "Story",    "한글테스트", "title-case Story candidate"),
    (0x08E41660, "Options",  "RAMOPT!",   "title-case Options candidate"),
    (0x08E41680, "Profile",  "RAMPROF",   "title-case Profile candidate"),

    # Inline UI object observed with geometry/state fields around it.
    (0x08E4E82C, "Skirmish", "RAMSKIRM",  "inline Skirmish UI object"),

    # Uppercase/resource-side candidates.
    (0x08E416C0, "STORY",    "RAM02",     "uppercase STORY candidate"),
    (0x097488AC, "SKIRMISH", "RAMSKIRM",  "runtime SKIRMISH object"),
    (0x09748924, "PROFILES", "RAMPROFL",  "runtime PROFILES object"),

    # This exact address changed Story -> Controls between the two dumps.
    (0x09749A18, "Story",    "LIVE!",     "dynamic current-selection text"),
]

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
        raise RuntimeError("Could not obtain PPSSPP PID/base pointer. Make sure the game is running.")
    return pid.value, base

def open_process(pid):
    h = kernel32.OpenProcess(
        PROCESS_VM_READ | PROCESS_VM_WRITE | PROCESS_VM_OPERATION | PROCESS_QUERY_INFORMATION,
        False, pid
    )
    if not h:
        e = ctypes.get_last_error()
        raise RuntimeError(
            f"OpenProcess failed ({e}). If PPSSPP is elevated, run PowerShell as Administrator."
        )
    return h

def rpm(h, host_addr, size):
    buf = (ctypes.c_ubyte * size)()
    got = ctypes.c_size_t()
    ok = kernel32.ReadProcessMemory(
        h, ctypes.c_void_p(host_addr), ctypes.byref(buf), size, ctypes.byref(got)
    )
    if not ok or got.value != size:
        raise RuntimeError(f"ReadProcessMemory failed at host 0x{host_addr:X}")
    return bytes(buf)

def wpm(h, host_addr, data):
    src = ctypes.create_string_buffer(data, len(data))
    wrote = ctypes.c_size_t()
    ok = kernel32.WriteProcessMemory(
        h, ctypes.c_void_p(host_addr), src, len(data), ctypes.byref(wrote)
    )
    if not ok or wrote.value != len(data):
        raise RuntimeError(f"WriteProcessMemory failed at host 0x{host_addr:X}")
    return wrote.value

def main():
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    STAGE_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 80)
    print("Brothers in Arms: D-Day - Stage 05 live RAM text probe")
    print("=" * 80)
    print()
    print("PPSSPP에서 STORY가 선택된 메인 메뉴를 띄워 둔 상태에서 진행하세요.")
    input("준비되었으면 Enter... ")

    pid, base = get_ppsspp()
    h = open_process(pid)
    rows = []
    originals = []

    try:
        print(f"\nPPSSPP PID      : {pid}")
        print(f"PSP memory base : 0x{base:016X}")
        print()

        for guest, expected, replacement, note in PATCHES:
            old = u16(expected)
            new = u16(replacement)
            if len(old) != len(new):
                raise RuntimeError(f"Internal length mismatch: {expected} -> {replacement}")

            host = base + guest
            current = rpm(h, host, len(old))
            status = "MATCH" if current == old else "SKIP"

            rows.append({
                "guest_address": f"0x{guest:08X}",
                "expected": expected,
                "replacement": replacement,
                "note": note,
                "status": status,
                "before_hex": current.hex(" "),
            })

            if current == old:
                originals.append((guest, old))
                wpm(h, host, new)
                verify = rpm(h, host, len(new))
                if verify != new:
                    raise RuntimeError(f"Verification failed at 0x{guest:08X}")
                print(f"[PATCH] 0x{guest:08X}  {expected!r:12s} -> {replacement!r:12s}  {note}")
            else:
                # Dynamic selection slot may differ if focus isn't STORY.
                try:
                    preview = current.decode("utf-16le", "replace")
                except Exception:
                    preview = repr(current)
                print(f"[SKIP ] 0x{guest:08X} expected {expected!r}, found {preview!r}  {note}")

        report = {
            "pid": pid,
            "psp_base": f"0x{base:016X}",
            "patches": rows,
            "instruction": (
                "Take a screenshot while this tool waits. "
                "Press Enter to restore all patched RAM bytes."
            ),
        }
        (STAGE_DIR / "ram_probe.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        print()
        print("=" * 80)
        print("지금 PPSSPP 화면으로 돌아가서 메인 메뉴를 확인하세요.")
        print()
        print("확인 포인트:")
        print("  Story    후보 중 하나는 '한글테스트' / 'RAM02' / 'LIVE!'")
        print("  Skirmish 후보는 'RAMSKIRM'")
        print("  Options  후보는 'RAMOPT!'")
        print("  Profile  후보는 'RAMPROF' 또는 'RAMPROFL'")
        print()
        print("화면이 바뀐 상태의 스크린샷을 찍어 주세요.")
        print("이 콘솔에서 Enter를 누르면 RAM을 원래대로 복구합니다.")
        print("=" * 80)
        input()

        # Restore only locations that matched and were actually changed.
        for guest, old in reversed(originals):
            wpm(h, base + guest, old)

        print("RAM restored.")

    finally:
        kernel32.CloseHandle(h)

    upload = LOG_DIR / "bia_stage05_ramprobe_upload.zip"
    with zipfile.ZipFile(upload, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(STAGE_DIR / "ram_probe.json", "ram_probe.json")

    print(f"Upload log: {upload}")
    return 0

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print("\nERROR:", e)
        input("Enter to close...")
        raise
