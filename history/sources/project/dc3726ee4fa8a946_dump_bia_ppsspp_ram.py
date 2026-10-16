#!/usr/bin/env python3
from __future__ import annotations

import ctypes
from ctypes import wintypes
from pathlib import Path
import sys
import time
import zipfile

ROOT = Path(r"PROJECT_ROOT")
DUMP_DIR = ROOT / "dump"
LOG_DIR = ROOT / "log"

PSP_START = 0x08800000
PSP_END   = 0x0A000000
DUMP_SIZE = PSP_END - PSP_START

WM_APP = 0x8000
WM_USER_GET_BASE_POINTER = WM_APP + 0x3118  # Official PPSSPP window message.

PROCESS_VM_READ = 0x0010
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
    wintypes.HANDLE,
    wintypes.LPCVOID,
    wintypes.LPVOID,
    ctypes.c_size_t,
    ctypes.POINTER(ctypes.c_size_t),
]
kernel32.ReadProcessMemory.restype = wintypes.BOOL

kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL

def get_ppsspp():
    hwnd = user32.FindWindowW("PPSSPPWnd", None)
    if not hwnd:
        raise RuntimeError(
            "PPSSPP window was not found.\n"
            "Start PPSSPPWindows64.exe, boot Brothers in Arms, and leave the game running."
        )

    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if not pid.value:
        raise RuntimeError("Could not get PPSSPP process ID.")

    low = int(user32.SendMessageW(hwnd, WM_USER_GET_BASE_POINTER, 0, 0)) & 0xFFFFFFFF
    high = int(user32.SendMessageW(hwnd, WM_USER_GET_BASE_POINTER, 0, 1)) & 0xFFFFFFFF
    base = (high << 32) | low
    if not base:
        raise RuntimeError(
            "PPSSPP returned a null PSP memory base pointer.\n"
            "Make sure a PSP game is currently running."
        )

    return hwnd, pid.value, base

def read_ram(pid: int, base: int) -> bytes:
    process = kernel32.OpenProcess(PROCESS_VM_READ | PROCESS_QUERY_INFORMATION, False, pid)
    if not process:
        err = ctypes.get_last_error()
        raise RuntimeError(
            f"OpenProcess failed (Win32 error {err}). "
            "If PPSSPP is running as Administrator, run this dumper as Administrator too."
        )

    try:
        host_addr = base + PSP_START
        buf = (ctypes.c_ubyte * DUMP_SIZE)()
        read = ctypes.c_size_t()

        ok = kernel32.ReadProcessMemory(
            process,
            ctypes.c_void_p(host_addr),
            ctypes.byref(buf),
            DUMP_SIZE,
            ctypes.byref(read),
        )
        if not ok or read.value != DUMP_SIZE:
            err = ctypes.get_last_error()
            raise RuntimeError(
                f"ReadProcessMemory failed/short read: "
                f"{read.value:#x}/{DUMP_SIZE:#x} bytes, Win32 error {err}.\n"
                f"PSP base=0x{base:016X}, host read address=0x{host_addr:016X}"
            )
        return bytes(buf)
    finally:
        kernel32.CloseHandle(process)

def capture(label: str, pid: int, base: int) -> Path:
    data = read_ram(pid, base)
    out = DUMP_DIR / f"{label}_08800000_0A000000.bin"
    out.write_bytes(data)
    print(f"[saved] {out}")
    print(f"        {len(data):,} bytes (0x{len(data):X})")
    return out

def main():
    DUMP_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 78)
    print("Brothers in Arms PSP - PPSSPP RAM capture")
    print("=" * 78)

    _, pid, base = get_ppsspp()
    print(f"PPSSPP PID     : {pid}")
    print(f"PSP memory base: 0x{base:016X}")
    print(f"Guest range    : 0x{PSP_START:08X} - 0x{PSP_END:08X}")
    print(f"Dump size      : {DUMP_SIZE:,} bytes ({DUMP_SIZE // 1024 // 1024} MiB)")
    print()

    input(
        "1) PPSSPP에서 BIA 메인 메뉴(STORY/SKIRMISH/OPTIONS/PROFILE)가 보이는 상태로 둔 뒤\n"
        "   여기서 Enter를 누르세요..."
    )
    # Re-query base immediately before capture in case the game was restarted.
    _, pid, base = get_ppsspp()
    main_dump = capture("mainmenu", pid, base)

    print()
    input(
        "2) PPSSPP로 돌아가 OPTIONS 메뉴 안으로 들어간 뒤\n"
        "   다시 여기서 Enter를 누르세요..."
    )
    _, pid, base = get_ppsspp()
    options_dump = capture("options", pid, base)

    zip_path = LOG_DIR / "bia_menu_memory_dumps.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=1) as z:
        z.write(main_dump, main_dump.name)
        z.write(options_dump, options_dump.name)

        info = (
            "Brothers in Arms: D-Day PSP RAM dumps\n"
            f"PSP guest start: 0x{PSP_START:08X}\n"
            f"PSP guest end  : 0x{PSP_END:08X}\n"
            f"Dump size      : 0x{DUMP_SIZE:X} ({DUMP_SIZE} bytes)\n"
            "mainmenu dump  : title/main menu visible\n"
            "options dump   : options menu visible\n"
        )
        z.writestr("dump_info.txt", info)

    print()
    print("=" * 78)
    print("DONE")
    print(f"Upload this ZIP: {zip_path}")
    print("=" * 78)
    return 0

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print()
        print("ERROR:", e)
        input("\nEnter를 누르면 종료합니다...")
        raise
