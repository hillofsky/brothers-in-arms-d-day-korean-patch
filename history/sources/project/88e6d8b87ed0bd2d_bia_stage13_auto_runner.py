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
import zipfile
from pathlib import Path

ROOT = Path(r"PROJECT_ROOT")
LOG_DIR = ROOT / "log"
ANALYSIS_DIR = ROOT / "analysis" / "stage13_auto_runner"

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
    cfg = ANALYSIS_DIR / "stage13_append.ini"
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


def patch_stage12(h, base):
    restores = []
    evidence = []

    # Borrow each font's already allocated U+21xx page as scratch.
    for f in FONT_LAYOUTS:
        page_table = f["page_table"]

        page21_slot = page_table + 0x21 * 4
        page21 = struct.unpack(
            "<I", guest_read(h, base, page21_slot, 4)
        )[0]
        if page21 == 0:
            raise RuntimeError(
                f"{f['name']}: page_table[0x21] is NULL"
            )

        d5_slot = page_table + TEST_HIGH * 4
        old_d5 = guest_read(h, base, d5_slot, 4)
        restores.append((d5_slot, old_d5))
        guest_write(h, base, d5_slot, struct.pack("<I", page21))

        entry = page21 + TEST_LOW * 2
        old_entry = guest_read(h, base, entry, 2)
        restores.append((entry, old_entry))
        guest_write(h, base, entry, struct.pack("<H", A_MAP_VALUE))

        evidence.append({
            "font": f["name"],
            "page_table": f"0x{page_table:08X}",
            "borrowed_page_21": f"0x{page21:08X}",
            "patched_page_D5_slot": f"0x{d5_slot:08X}",
            "patched_D55C_entry": f"0x{entry:08X}",
        })

    old_story = guest_read(h, base, STORY_GUEST, 10)
    if old_story != "Story".encode("utf-16le"):
        got = old_story.decode("utf-16le", "replace")
        raise RuntimeError(
            f"Story slot mismatch immediately before patch: {got!r}"
        )

    restores.append((STORY_GUEST, old_story))
    guest_write(
        h, base, STORY_GUEST,
        struct.pack("<5H", TEST_CP, TEST_CP, TEST_CP, TEST_CP, TEST_CP)
    )

    # Verify RAM-side result.
    if guest_read(h, base, STORY_GUEST, 10) != struct.pack(
        "<5H", TEST_CP, TEST_CP, TEST_CP, TEST_CP, TEST_CP
    ):
        raise RuntimeError("Story U+D55C patch verification failed")

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

    helper = Path(__file__).resolve().parent / "capture_ppsspp.ps1"
    exe = find_ppsspp_exe()
    iso = find_iso()
    cfg = write_append_config()

    ppsspp_log = ANALYSIS_DIR / "ppsspp_debug.log"
    before_png = ANALYSIS_DIR / "stage13_before.png"
    after_png = ANALYSIS_DIR / "stage13_after.png"
    report_path = ANALYSIS_DIR / "stage13_report.json"

    report = {
        "stage": "13B",
        "purpose": "fully automated PPSSPP launch + Stage12 Unicode page-table test + screenshots",
        "ppsspp_exe": str(exe),
        "iso": str(iso),
        "append_config": str(cfg),
        "test_codepoint": "U+D55C",
        "expected_visual": "AAAAA, or 한한한한한 if a replacement A glyph is active",
        "renderer_function": "0x08C7F2FC",
        "glyph_lookup_instruction": "0x08C7F35C",
    }

    log("=" * 80)
    log("BIA Stage 13B - fully automated PPSSPP test runner")
    log("=" * 80)
    log(f"PPSSPP : {exe}")
    log(f"ISO    : {iso}")
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
        restores, evidence = patch_stage12(h, base)
        report["fonts"] = evidence
        report["ram_patch_verified"] = True

        # Allow a few frames to redraw.
        foreground(hwnd)
        time.sleep(1.5)

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

    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    upload = LOG_DIR / "bia_stage13b_upload.zip"
    make_zip(upload, [
        (report_path, "stage13_report.json"),
        (before_png, "stage13_before.png"),
        (after_png, "stage13_after.png"),
        (ppsspp_log, "ppsspp_debug.log"),
        (cfg, "stage13_append.ini"),
    ])

    log()
    log("=" * 80)
    log("Stage 13B complete")
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

        fail_zip = LOG_DIR / "fail_bia_stage13b_upload.zip"
        extras = [
            (failure, "FAILURE.txt"),
            (ANALYSIS_DIR / "stage13_before.png", "stage13_before.png"),
            (ANALYSIS_DIR / "stage13_after.png", "stage13_after.png"),
            (ANALYSIS_DIR / "ppsspp_debug.log", "ppsspp_debug.log"),
            (ANALYSIS_DIR / "stage13_append.ini", "stage13_append.ini"),
        ]
        try:
            make_zip(fail_zip, extras)
        except Exception:
            pass

        print()
        print("=" * 80)
        print("STAGE 13 FAILED")
        print(f"Failure ZIP: {fail_zip}")
        print("=" * 80)
        traceback.print_exc()
        raise
