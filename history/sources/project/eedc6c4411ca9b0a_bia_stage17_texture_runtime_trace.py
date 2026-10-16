#!/usr/bin/env python3
from __future__ import annotations

import ctypes
from ctypes import wintypes
import hashlib
import json
import re
import struct
import subprocess
import time
import traceback
import zipfile
from pathlib import Path

ROOT = Path(r"PROJECT_ROOT")
LOG_DIR = ROOT / "log"
ANALYSIS_DIR = ROOT / "analysis" / "stage17_texture_runtime_trace"

GAME_ID = "ULUS10193"

TARGET_DSL = ["PSP_GAME", "USRDIR", "SYSTEM", "ON_MEMU.DSL"]

TMR_RAW_OFF = 0x15D964
TMR_RAW_SIZE = 0x4000
AB_RAW_OFF = 0x1619A4
AB_RAW_SIZE = 0x8000
PALETTE_SIZE = 0x40

EXPECTED_DSL_SHA1 = "e009f2e259861f60d0aeeb03f46422d5473b88aa"
EXPECTED_TMR_SHA1 = "b64ac2e19f620bcc6049f60315ed3352276fc9af"
EXPECTED_AB_SHA1  = "97fd85e308121bf749970e70706b43bec67bd203"

STORY_GUEST = 0x08E41620

MAIN_START = 0x08800000
MAIN_END   = 0x0A000000
VRAM_START = 0x04000000
VRAM_END   = 0x04200000

WM_APP = 0x8000
WM_USER_GET_BASE_POINTER = WM_APP + 0x3118
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
SW_RESTORE = 9

PROCESS_VM_READ = 0x0010
PROCESS_QUERY_INFORMATION = 0x0400

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
user32 = ctypes.WinDLL("user32", use_last_error=True)

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
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL


def log(s=""):
    print(s, flush=True)


def sha1_bytes(b):
    return hashlib.sha1(b).hexdigest()


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
            raise RuntimeError(f"Bad ISO record at 0x{pos:X}")
        yield rec
        pos += rec["length"]


def iso_find(iso: Path, parts):
    with iso.open("rb") as f:
        f.seek(16 * 2048)
        pvd = f.read(2048)
        if pvd[0] != 1 or pvd[1:6] != b"CD001":
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
        raise RuntimeError("Short ISO read")
    return extent, data


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


def find_stage09_memstick():
    summary = ROOT / "analysis" / "stage09_texture_dump" / "summary.json"
    if summary.exists():
        try:
            data = json.loads(summary.read_text(encoding="utf-8"))
            for s in data.get("dump_dirs", []):
                q = Path(s)
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


def write_append_config():
    cfg = ANALYSIS_DIR / "stage17_append.ini"
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
        raise RuntimeError("Could not obtain PPSSPP PID/base pointer")

    return pid.value, base


def open_process(pid):
    h = kernel32.OpenProcess(
        PROCESS_VM_READ | PROCESS_QUERY_INFORMATION,
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
        raise RuntimeError(
            f"ReadProcessMemory failed at host 0x{addr:X}: "
            f"{got.value}/{size}"
        )
    return bytes(buf)


def guest_read(h, base, guest, size):
    return rpm(h, base + guest, size)


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
                cur = guest_read(h, base, STORY_GUEST, 10)
                if cur == "Story".encode("utf-16le"):
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

    raise RuntimeError("Main menu Story state not detected")


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


def find_all(hay: bytes, needle: bytes, max_hits=256):
    hits = []
    if not needle:
        return hits
    pos = 0
    while len(hits) < max_hits:
        pos = hay.find(needle, pos)
        if pos < 0:
            break
        hits.append(pos)
        pos += 1
    return hits


def safe_window(buf, center_off, before=0x100, after=0x100):
    s = max(0, center_off - before)
    e = min(len(buf), center_off + after)
    return s, e, buf[s:e]


def scan_ge_refs(main: bytes, guest_tex_addr: int):
    """
    PSP GE texture commands encode the low 24 bits of texture-related values.
    Collect aligned command words in the A0-BF opcode region whose data matches
    the texture address low24, then retain neighboring GPU-looking commands.
    This is intentionally broad; Stage17 is a discovery bundle.
    """
    low24 = guest_tex_addr & 0x00FFFFFF
    exact_cmds = []
    nearby = []

    for off in range(0, len(main) - 4, 4):
        w = struct.unpack_from("<I", main, off)[0]
        op = (w >> 24) & 0xFF
        dat = w & 0x00FFFFFF
        if 0xA0 <= op <= 0xBF and dat == low24:
            exact_cmds.append({
                "guest": f"0x{MAIN_START + off:08X}",
                "word": f"0x{w:08X}",
                "opcode": f"0x{op:02X}",
            })

            s = max(0, off - 0x80)
            e = min(len(main), off + 0x84)
            cmds = []
            for q in range(s - (s % 4), e - 3, 4):
                x = struct.unpack_from("<I", main, q)[0]
                xo = (x >> 24) & 0xFF
                if 0x90 <= xo <= 0xCF:
                    cmds.append({
                        "guest": f"0x{MAIN_START + q:08X}",
                        "word": f"0x{x:08X}",
                        "opcode": f"0x{xo:02X}",
                        "data24": f"0x{x & 0x00FFFFFF:06X}",
                    })
            nearby.append({
                "center_guest": f"0x{MAIN_START + off:08X}",
                "gpu_commands": cmds,
            })

    return exact_cmds[:64], nearby[:32]


def search_u32_pointer_refs(main: bytes, values):
    results = {}
    for label, val in values.items():
        pat = struct.pack("<I", val & 0xFFFFFFFF)
        hits = find_all(main, pat, 256)
        results[label] = [
            f"0x{MAIN_START + off:08X}" for off in hits
        ]
    return results


def dimensional_context(main: bytes, guest_addrs):
    """
    Around ordinary pointer refs, inventory 16/32-bit values that look like
    128/256/512/1024 dimensions. This helps identify texture descriptors.
    """
    targets = {128, 256, 512, 1024, 64, 32, 16, 8, 4}
    out = []
    for addr in guest_addrs[:64]:
        off = addr - MAIN_START
        s = max(0, off - 0x100)
        e = min(len(main), off + 0x104)
        hits16 = []
        hits32 = []

        for q in range(s, e - 1, 2):
            v = struct.unpack_from("<H", main, q)[0]
            if v in targets:
                hits16.append({
                    "guest": f"0x{MAIN_START + q:08X}",
                    "value": v,
                })

        for q in range(s - (s % 4), e - 3, 4):
            v = struct.unpack_from("<I", main, q)[0]
            if v in targets:
                hits32.append({
                    "guest": f"0x{MAIN_START + q:08X}",
                    "value": v,
                })

        out.append({
            "pointer_ref": f"0x{addr:08X}",
            "u16_dimension_like": hits16[:64],
            "u32_dimension_like": hits32[:64],
        })
    return out


def parse_texture_log(log_path: Path):
    if not log_path.exists():
        return []
    text = log_path.read_text(encoding="utf-8", errors="replace")
    vals = re.findall(
        r"Texture different or overwritten, reloading at ([0-9A-Fa-f]{8})",
        text
    )
    counts = {}
    for s in vals:
        a = int(s, 16)
        counts[a] = counts.get(a, 0) + 1
    return [
        {"address": f"0x{a:08X}", "count": c}
        for a, c in sorted(counts.items(), key=lambda x: (-x[1], x[0]))
    ]


def write_window(path: Path, base_guest: int, data: bytes):
    path.write_bytes(data)
    meta = path.with_suffix(path.suffix + ".txt")
    meta.write_text(
        f"guest_start=0x{base_guest:08X}\n"
        f"size=0x{len(data):X}\n",
        encoding="utf-8"
    )


def make_zip(path: Path, entries):
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for src, arc in entries:
            p = Path(src)
            if p.exists():
                z.write(p, arc)


def main():
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)

    helper = Path(__file__).resolve().parent / "capture_ppsspp.ps1"
    iso = find_original_iso()
    exe = find_ppsspp_exe()
    cfg = write_append_config()

    _, dsl = iso_read_file(iso, TARGET_DSL)
    if sha1_bytes(dsl) != EXPECTED_DSL_SHA1:
        raise RuntimeError("ON_MEMU.DSL SHA1 mismatch")

    tmr = dsl[TMR_RAW_OFF:TMR_RAW_OFF+TMR_RAW_SIZE]
    ab  = dsl[AB_RAW_OFF:AB_RAW_OFF+AB_RAW_SIZE]
    tmr_pal = dsl[TMR_RAW_OFF-PALETTE_SIZE:TMR_RAW_OFF]
    ab_pal  = dsl[AB_RAW_OFF-PALETTE_SIZE:AB_RAW_OFF]

    if sha1_bytes(tmr) != EXPECTED_TMR_SHA1:
        raise RuntimeError(
            f"TMR raw SHA1 mismatch: {sha1_bytes(tmr)}"
        )

    # AB hash is informative rather than fatal; it was not needed in Stage16.
    ab_hash = sha1_bytes(ab)

    report = {
        "stage": 17,
        "purpose": "locate live TMR18/AB18 textures in PSP VRAM and trace address/GE references",
        "iso": str(iso),
        "ppsspp_exe": str(exe),
        "tmr_source": {
            "dsl_offset": f"0x{TMR_RAW_OFF:X}",
            "size": TMR_RAW_SIZE,
            "sha1": sha1_bytes(tmr),
            "dimensions": [128, 256],
            "format": "PSP 4bpp swizzled",
        },
        "ab_source": {
            "dsl_offset": f"0x{AB_RAW_OFF:X}",
            "size": AB_RAW_SIZE,
            "sha1": ab_hash,
            "expected_sha1_note": EXPECTED_AB_SHA1,
            "dimensions": [128, 512],
            "format": "PSP 4bpp swizzled",
        },
    }

    screen = ANALYSIS_DIR / "stage17_menu.png"
    ppsspp_log = ANALYSIS_DIR / "stage17_ppsspp_debug.log"
    report_path = ANALYSIS_DIR / "stage17_report.json"

    # Fresh PPSSPP.
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
        str(iso),
    ]
    log("[auto] PPSSPP original ISO boot")
    subprocess.Popen(cmd)

    hwnd = find_ppsspp_hwnd(30)
    if not hwnd:
        raise RuntimeError("PPSSPP window did not appear")

    pid, base = wait_for_story(hwnd, 120)
    report["pid"] = pid
    report["psp_base"] = f"0x{base:016X}"

    capture(hwnd, screen, helper)

    h = open_process(pid)
    artifact_entries = []
    try:
        log("[auto] Reading 24 MiB main RAM")
        main = guest_read(h, base, MAIN_START, MAIN_END - MAIN_START)

        log("[auto] Reading 2 MiB VRAM")
        vram = guest_read(h, base, VRAM_START, VRAM_END - VRAM_START)

        texture_results = {}

        for name, raw, pal, expected_wh in [
            ("TMR18", tmr, tmr_pal, (128, 256)),
            ("AB18",  ab,  ab_pal,  (128, 512)),
        ]:
            full_hits_v = find_all(vram, raw, 32)
            sig_hits_v = find_all(vram, raw[:0x400], 64)
            full_hits_m = find_all(main, raw, 32)
            pal_hits_v = find_all(vram, pal, 64)
            pal_hits_m = find_all(main, pal, 64)

            vram_guest_hits = [
                VRAM_START + x for x in full_hits_v
            ]
            main_guest_hits = [
                MAIN_START + x for x in full_hits_m
            ]

            result = {
                "exact_full_vram_hits": [
                    f"0x{x:08X}" for x in vram_guest_hits
                ],
                "first_0x400_vram_hits": [
                    f"0x{VRAM_START+x:08X}" for x in sig_hits_v
                ],
                "exact_full_mainram_hits": [
                    f"0x{x:08X}" for x in main_guest_hits
                ],
                "palette_vram_hits": [
                    f"0x{VRAM_START+x:08X}" for x in pal_hits_v
                ],
                "palette_mainram_hits": [
                    f"0x{MAIN_START+x:08X}" for x in pal_hits_m
                ],
            }

            # Trace exact VRAM addresses back into main RAM.
            refs = {}
            dims = []
            ge = []
            ge_near = []

            for addr in vram_guest_hits[:8]:
                variants = {
                    f"full_0x{addr:08X}": addr,
                    f"low24_0x{addr & 0x00FFFFFF:06X}":
                        addr & 0x00FFFFFF,
                    f"vram_offset_0x{addr - VRAM_START:06X}":
                        addr - VRAM_START,
                }
                r = search_u32_pointer_refs(main, variants)
                refs[f"0x{addr:08X}"] = r

                ordinary = []
                for arr in r.values():
                    for s in arr:
                        a = int(s, 16)
                        if a not in ordinary:
                            ordinary.append(a)
                dims.extend(dimensional_context(main, ordinary))

                c, n = scan_ge_refs(main, addr)
                ge.extend(c)
                ge_near.extend(n)

                # Save a VRAM window around the exact texture.
                off = addr - VRAM_START
                s = max(0, off - 0x100)
                e = min(len(vram), off + len(raw) + 0x100)
                fn = ANALYSIS_DIR / (
                    f"{name.lower()}_vram_0x{addr:08X}.bin"
                )
                write_window(fn, VRAM_START + s, vram[s:e])
                artifact_entries.append(
                    (fn, f"windows/{fn.name}")
                )
                artifact_entries.append(
                    (
                        fn.with_suffix(fn.suffix + ".txt"),
                        f"windows/{fn.name}.txt"
                    )
                )

            result["mainram_pointer_refs_to_vram"] = refs
            result["dimension_like_values_near_pointer_refs"] = dims[:128]
            result["ge_exact_address_commands"] = ge[:128]
            result["ge_command_neighborhoods"] = ge_near[:64]

            texture_results[name] = result

        report["runtime_textures"] = texture_results

        # Save compact main-RAM windows around every ordinary pointer ref.
        saved_centers = set()
        for name, res in texture_results.items():
            for per_addr in res["mainram_pointer_refs_to_vram"].values():
                for hit_list in per_addr.values():
                    for saddr in hit_list[:32]:
                        addr = int(saddr, 16)
                        if addr in saved_centers:
                            continue
                        saved_centers.add(addr)
                        off = addr - MAIN_START
                        s, e, blob = safe_window(
                            main, off, 0x200, 0x200
                        )
                        fn = ANALYSIS_DIR / (
                            f"mainref_0x{addr:08X}.bin"
                        )
                        write_window(fn, MAIN_START + s, blob)
                        artifact_entries.append(
                            (fn, f"windows/{fn.name}")
                        )
                        artifact_entries.append(
                            (
                                fn.with_suffix(fn.suffix + ".txt"),
                                f"windows/{fn.name}.txt"
                            )
                        )

        # Also inventory source palette/raw hashes.
        sources = ANALYSIS_DIR / "source_texture_hashes.txt"
        sources.write_text(
            f"TMR18 raw SHA1 {sha1_bytes(tmr)}\n"
            f"TMR18 palette SHA1 {sha1_bytes(tmr_pal)}\n"
            f"AB18 raw SHA1 {sha1_bytes(ab)}\n"
            f"AB18 palette SHA1 {sha1_bytes(ab_pal)}\n",
            encoding="utf-8"
        )
        artifact_entries.append(
            (sources, "source_texture_hashes.txt")
        )

    finally:
        kernel32.CloseHandle(h)

    # Let log flush then parse runtime texture-cache addresses.
    time.sleep(1)
    report["ppsspp_texture_reload_addresses"] = parse_texture_log(
        ppsspp_log
    )
    report["completed"] = True

    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    upload = LOG_DIR / "bia_stage17_upload.zip"
    entries = [
        (report_path, "stage17_report.json"),
        (screen, "stage17_menu.png"),
        (ppsspp_log, "stage17_ppsspp_debug.log"),
        (cfg, "stage17_append.ini"),
    ] + artifact_entries
    make_zip(upload, entries)

    log()
    log("=" * 80)
    log("Stage 17 complete")
    log(f"Upload: {upload}")
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

        fail_zip = LOG_DIR / "fail_bia_stage17_upload.zip"
        try:
            make_zip(fail_zip, [
                (failure, "FAILURE.txt"),
                (
                    ANALYSIS_DIR / "stage17_report.json",
                    "stage17_report.json"
                ),
                (
                    ANALYSIS_DIR / "stage17_menu.png",
                    "stage17_menu.png"
                ),
                (
                    ANALYSIS_DIR / "stage17_ppsspp_debug.log",
                    "stage17_ppsspp_debug.log"
                ),
                (
                    ANALYSIS_DIR / "stage17_append.ini",
                    "stage17_append.ini"
                ),
            ])
        except Exception:
            pass

        print()
        print("=" * 80)
        print("STAGE 17 FAILED")
        print(f"Failure ZIP: {fail_zip}")
        print("=" * 80)
        traceback.print_exc()
        raise
