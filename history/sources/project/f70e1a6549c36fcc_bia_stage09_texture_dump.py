#!/usr/bin/env python3
from __future__ import annotations

import ctypes
from ctypes import wintypes
import hashlib
import os
import shutil
import struct
import sys
import time
import zipfile
from pathlib import Path

ROOT = Path(r"PROJECT_ROOT")
LOG = ROOT / "log"
ANALYSIS = ROOT / "analysis" / "stage09_texture_dump"

GAME_ID = "ULUS10193"

def png_size(path: Path):
    try:
        with path.open("rb") as f:
            h = f.read(24)
        if len(h) >= 24 and h[:8] == b"\x89PNG\r\n\x1a\n" and h[12:16] == b"IHDR":
            w, hgt = struct.unpack(">II", h[16:24])
            return w, hgt
    except Exception:
        pass
    return None, None

def sha1_file(p: Path):
    h = hashlib.sha1()
    with p.open("rb") as f:
        while True:
            b = f.read(1024 * 1024)
            if not b:
                break
            h.update(b)
    return h.hexdigest()

def running_ppsspp_exe():
    # Best-effort: locate PPSSPP process and executable path.
    TH32CS_SNAPPROCESS = 0x00000002
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

    class PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.c_size_t),
            ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", wintypes.LONG),
            ("dwFlags", wintypes.DWORD),
            ("szExeFile", wintypes.WCHAR * 260),
        ]

    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snap == ctypes.c_void_p(-1).value:
        return None

    pe = PROCESSENTRY32W()
    pe.dwSize = ctypes.sizeof(pe)

    pid = None
    try:
        ok = k32.Process32FirstW(snap, ctypes.byref(pe))
        while ok:
            name = pe.szExeFile.lower()
            if name.startswith("ppsspp") and name.endswith(".exe"):
                pid = pe.th32ProcessID
                break
            ok = k32.Process32NextW(snap, ctypes.byref(pe))
    finally:
        k32.CloseHandle(snap)

    if not pid:
        return None

    hproc = k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not hproc:
        return None
    try:
        size = wintypes.DWORD(32768)
        buf = ctypes.create_unicode_buffer(size.value)
        if k32.QueryFullProcessImageNameW(hproc, 0, buf, ctypes.byref(size)):
            return Path(buf.value)
    finally:
        k32.CloseHandle(hproc)
    return None

def candidate_roots():
    home = Path.home()
    roots = [
        home / "Documents" / "PPSSPP",
        home / "OneDrive" / "Documents" / "PPSSPP",
        Path(os.environ.get("APPDATA", "")) / "PPSSPP",
        Path(os.environ.get("LOCALAPPDATA", "")) / "PPSSPP",
    ]

    exe = running_ppsspp_exe()
    if exe:
        roots += [
            exe.parent,
            exe.parent / "memstick",
            exe.parent / "MemStick",
            exe.parent / "PPSSPP",
        ]

    # De-dup valid paths.
    out = []
    seen = set()
    for p in roots:
        try:
            p = p.resolve()
        except Exception:
            pass
        key = str(p).lower()
        if key not in seen:
            seen.add(key)
            out.append(p)
    return out

def find_texture_dirs():
    found = []
    seen = set()

    # Direct common layouts first.
    for r in candidate_roots():
        for p in [
            r / "PSP" / "TEXTURES" / GAME_ID / "new",
            r / "TEXTURES" / GAME_ID / "new",
            r / "memstick" / "PSP" / "TEXTURES" / GAME_ID / "new",
        ]:
            if p.is_dir():
                key = str(p.resolve()).lower()
                if key not in seen:
                    seen.add(key)
                    found.append(p)

    # Fallback bounded search under likely PPSSPP roots.
    for r in candidate_roots():
        if not r.is_dir():
            continue
        try:
            # Avoid scanning whole disks. Depth is naturally limited by these roots.
            for p in r.rglob("new"):
                if not p.is_dir():
                    continue
                parts = [x.upper() for x in p.parts]
                if GAME_ID in parts and "TEXTURES" in parts:
                    key = str(p.resolve()).lower()
                    if key not in seen:
                        seen.add(key)
                        found.append(p)
        except (PermissionError, OSError):
            pass

    return found

def snapshot(paths):
    s = {}
    for d in paths:
        for p in d.glob("*.png"):
            try:
                st = p.stat()
                s[str(p.resolve())] = (st.st_size, st.st_mtime_ns)
            except OSError:
                pass
    return s

def main():
    LOG.mkdir(parents=True, exist_ok=True)
    ANALYSIS.mkdir(parents=True, exist_ok=True)

    print("=" * 80)
    print("BIA Stage 09 - PPSSPP live texture dump collector")
    print("=" * 80)
    print()
    print("Stage 08 confirmed the game's direct 256-entry font character map.")
    print("Now we need the actual font atlas texture used by the GPU.")
    print()
    print("PPSSPP에서 다음 메뉴를 여세요:")
    print()
    print("  ESC")
    print("   -> Settings")
    print("   -> Tools")
    print("   -> Developer Tools")
    print("   -> Texture Replacement")
    print()
    print("여기서:")
    print("  1) Create/Open textures.ini file for current game")
    print("  2) Save new textures = ON")
    print()
    print("그 다음 BIA 메인 메뉴(STORY/SKIRMISH/OPTIONS/PROFILE)로 돌아오세요.")
    print()

    input("Save new textures를 켜고 메인 메뉴로 돌아왔으면 Enter... ")

    dirs = find_texture_dirs()
    if not dirs:
        print()
        print("아직 texture dump 폴더를 찾지 못했습니다.")
        print("PPSSPP에서 메인 메뉴를 5~10초 정도 보여준 뒤 Enter를 누르세요.")
        input()
        dirs = find_texture_dirs()

    if not dirs:
        raise RuntimeError(
            "ULUS10193 texture dump 'new' folder를 찾지 못했습니다.\n"
            "PPSSPP의 'Save new textures'가 실제로 ON인지 확인하세요."
        )

    print()
    print("Detected dump folders:")
    for d in dirs:
        print(" ", d)

    before = snapshot(dirs)

    print()
    print("PPSSPP로 돌아가서:")
    print("  - 메인 메뉴에서 위/아래로 몇 번 움직이고")
    print("  - OPTIONS에 한번 들어갔다가")
    print("  - 다시 메인 메뉴로 돌아오세요.")
    print()
    print("이렇게 하면 TMR18/AB18 계열 텍스처가 확실히 사용됩니다.")
    input("완료했으면 Enter... ")

    # Give PPSSPP a moment to flush PNGs.
    time.sleep(2)

    after = snapshot(dirs)

    # Collect all current PNGs, but prioritize those newly created/updated during this run.
    rows = []
    files = []
    for d in dirs:
        for p in sorted(d.glob("*.png")):
            try:
                rp = str(p.resolve())
                st = p.stat()
                w, h = png_size(p)
                is_new = rp not in before or before[rp] != (st.st_size, st.st_mtime_ns)

                # Font candidates based on the UV quantization discovered earlier:
                # TMR18 appears to use 128x256.
                # AB18 appears to use 128x512.
                font_candidate = (w, h) in {
                    (128, 256), (128, 512),
                    # PPSSPP may expose differently sized/padded texture surfaces.
                    (256, 256), (256, 512),
                    (128, 128), (256, 128),
                }

                rows.append({
                    "path": rp,
                    "name": p.name,
                    "width": w,
                    "height": h,
                    "bytes": st.st_size,
                    "new_or_updated": is_new,
                    "font_candidate": font_candidate,
                    "sha1": sha1_file(p),
                })

                # Include new files and any size-compatible font candidates.
                if is_new or font_candidate:
                    files.append(p)
            except OSError:
                pass

    if not rows:
        raise RuntimeError(
            "Texture dump folder exists, but no PNG files were found.\n"
            "Keep 'Save new textures' enabled and revisit the menu."
        )

    import csv, json

    manifest_tsv = ANALYSIS / "texture_manifest.tsv"
    with manifest_tsv.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow([
            "name","width","height","bytes",
            "new_or_updated","font_candidate","sha1","path"
        ])
        for r in rows:
            w.writerow([
                r["name"],r["width"],r["height"],r["bytes"],
                "yes" if r["new_or_updated"] else "no",
                "yes" if r["font_candidate"] else "no",
                r["sha1"],r["path"]
            ])

    summary = {
        "game_id": GAME_ID,
        "dump_dirs": [str(x) for x in dirs],
        "png_count": len(rows),
        "new_or_updated_count": sum(1 for x in rows if x["new_or_updated"]),
        "font_candidate_count": sum(1 for x in rows if x["font_candidate"]),
        "font_candidate_dimensions": ["128x256", "128x512", "256x256", "256x512", "128x128", "256x128"],
    }
    summary_path = ANALYSIS / "summary.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    # De-dup by resolved path.
    uniq = []
    seen = set()
    for p in files:
        k = str(p.resolve()).lower()
        if k not in seen:
            seen.add(k)
            uniq.append(p)

    upload = LOG / "bia_stage09_texture_dump_upload.zip"
    with zipfile.ZipFile(upload, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        z.write(manifest_tsv, "analysis/texture_manifest.tsv")
        z.write(summary_path, "analysis/summary.json")
        for p in uniq:
            # Keep original dumped hash filename.
            z.write(p, "textures/" + p.name)

    print()
    print("=" * 80)
    print("Stage 09 complete")
    print(f"PNG total          : {len(rows)}")
    print(f"new/updated        : {summary['new_or_updated_count']}")
    print(f"font-size candidate: {summary['font_candidate_count']}")
    print()
    print(f"Upload ZIP:")
    print(f"  {upload}")
    print("=" * 80)
    return 0

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print()
        print("ERROR:", e)
        input("Enter를 누르면 종료합니다...")
        raise
