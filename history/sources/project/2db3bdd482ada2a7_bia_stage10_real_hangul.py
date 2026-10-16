#!/usr/bin/env python3
from __future__ import annotations

import ctypes
from ctypes import wintypes
import hashlib
import json
import os
import shutil
import struct
import zipfile
from pathlib import Path

ROOT = Path(r"PROJECT_ROOT")
LOG_DIR = ROOT / "log"
ANALYSIS_DIR = ROOT / "analysis" / "stage10_real_hangul_glyph"

GAME_ID = "ULUS10193"
ATLAS_NAME = "0857ff40f65c4402a4ab474d.png"
EXPECTED_DUMP_SHA1 = "fef208dca5a6524d77eb7002d45575826d3b6ec0"

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

def sha1_file(p: Path) -> str:
    h = hashlib.sha1()
    with p.open("rb") as f:
        while True:
            b = f.read(1024*1024)
            if not b:
                break
            h.update(b)
    return h.hexdigest()

def running_ppsspp_exe():
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

    snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snap == ctypes.c_void_p(-1).value:
        return None

    pe = PROCESSENTRY32W()
    pe.dwSize = ctypes.sizeof(pe)
    pid = None
    try:
        ok = kernel32.Process32FirstW(snap, ctypes.byref(pe))
        while ok:
            n = pe.szExeFile.lower()
            if n.startswith("ppsspp") and n.endswith(".exe"):
                pid = pe.th32ProcessID
                break
            ok = kernel32.Process32NextW(snap, ctypes.byref(pe))
    finally:
        kernel32.CloseHandle(snap)

    if not pid:
        return None

    h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h:
        return None
    try:
        size = wintypes.DWORD(32768)
        buf = ctypes.create_unicode_buffer(size.value)
        if kernel32.QueryFullProcessImageNameW(h,0,buf,ctypes.byref(size)):
            return Path(buf.value)
    finally:
        kernel32.CloseHandle(h)
    return None

def candidate_roots():
    home = Path.home()
    roots = [
        home / "Documents" / "PPSSPP",
        home / "OneDrive" / "Documents" / "PPSSPP",
        Path(os.environ.get("APPDATA","")) / "PPSSPP",
        Path(os.environ.get("LOCALAPPDATA","")) / "PPSSPP",
    ]
    exe = running_ppsspp_exe()
    if exe:
        roots += [
            exe.parent,
            exe.parent / "memstick",
            exe.parent / "MemStick",
            exe.parent / "PPSSPP",
        ]
    out=[]
    seen=set()
    for p in roots:
        try:
            p=p.resolve()
        except Exception:
            pass
        k=str(p).lower()
        if k not in seen:
            seen.add(k); out.append(p)
    return out

def find_dump_new():
    candidates=[]
    for r in candidate_roots():
        for p in [
            r/"PSP"/"TEXTURES"/GAME_ID/"new",
            r/"TEXTURES"/GAME_ID/"new",
            r/"memstick"/"PSP"/"TEXTURES"/GAME_ID/"new",
        ]:
            if p.is_dir():
                candidates.append(p)

    # bounded fallback
    for r in candidate_roots():
        if not r.is_dir():
            continue
        try:
            for p in r.rglob("new"):
                if not p.is_dir():
                    continue
                parts=[x.upper() for x in p.parts]
                if GAME_ID in parts and "TEXTURES" in parts:
                    candidates.append(p)
        except (PermissionError,OSError):
            pass

    uniq=[]
    seen=set()
    for p in candidates:
        try: k=str(p.resolve()).lower()
        except: k=str(p).lower()
        if k not in seen:
            seen.add(k); uniq.append(p)

    # Prefer directory containing the exact dumped atlas.
    exact=[p for p in uniq if (p/ATLAS_NAME).exists()]
    if exact:
        return exact[0]
    if uniq:
        return uniq[0]
    raise RuntimeError("PPSSPP ULUS10193 texture dump 'new' directory not found.")

def get_ppsspp():
    hwnd=user32.FindWindowW("PPSSPPWnd",None)
    if not hwnd:
        raise RuntimeError("PPSSPP window not found. Boot BIA first.")
    pid=wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd,ctypes.byref(pid))
    lo=int(user32.SendMessageW(hwnd,WM_USER_GET_BASE_POINTER,0,0)) & 0xFFFFFFFF
    hi=int(user32.SendMessageW(hwnd,WM_USER_GET_BASE_POINTER,0,1)) & 0xFFFFFFFF
    base=(hi<<32)|lo
    if not pid.value or not base:
        raise RuntimeError("Could not obtain PPSSPP process/base pointer.")
    return pid.value,base

def open_process(pid):
    h=kernel32.OpenProcess(
        PROCESS_VM_READ|PROCESS_VM_WRITE|PROCESS_VM_OPERATION|PROCESS_QUERY_INFORMATION,
        False,pid
    )
    if not h:
        raise RuntimeError(f"OpenProcess failed ({ctypes.get_last_error()})")
    return h

def rpm(h,addr,size):
    buf=(ctypes.c_ubyte*size)()
    got=ctypes.c_size_t()
    ok=kernel32.ReadProcessMemory(h,ctypes.c_void_p(addr),ctypes.byref(buf),size,ctypes.byref(got))
    if not ok or got.value != size:
        raise RuntimeError(f"ReadProcessMemory failed at 0x{addr:X}")
    return bytes(buf)

def wpm(h,addr,data):
    buf=ctypes.create_string_buffer(data,len(data))
    wrote=ctypes.c_size_t()
    ok=kernel32.WriteProcessMemory(h,ctypes.c_void_p(addr),buf,len(data),ctypes.byref(wrote))
    if not ok or wrote.value != len(data):
        raise RuntimeError(f"WriteProcessMemory failed at 0x{addr:X}")

def find_font_tables(ram):
    rec=24
    checks=[
        (0,0x20),(1,0x2E),(2,0x21),(14,0x2D),(15,0x2F),
        (16,0x30),(25,0x39),(33,0x41),(58,0x5A),
        (65,0x61),(90,0x7A),(95,0xA1),
    ]
    found=[]
    pos=0
    while True:
        pos=ram.find(b"\x20\x00",pos)
        if pos<0: break
        if pos+150*rec<=len(ram):
            if all(struct.unpack_from("<H",ram,pos+i*rec)[0]==cp for i,cp in checks):
                final=struct.unpack_from("<H",ram,pos+149*rec)[0]
                if final in (0x2122,0xD55C):
                    found.append({"ram_off":pos,"guest":PSP_START+pos})
        pos+=1
    return found

def map_matches(buf,off):
    checks={0x20:1,0x21:3,0x2E:2,0x30:17,0x39:26,0x41:34,0x5A:59,0x61:66,0x7A:91,0xA1:96}
    if off<0 or off+512>len(buf): return False
    return all(struct.unpack_from("<H",buf,off+cp*2)[0]==v for cp,v in checks.items())

def find_charmap_after_table(ram,table_off):
    end=table_off+150*24
    hits=[]
    for off in range(end,min(len(ram)-512,end+0x100),2):
        if map_matches(ram,off):
            hits.append(off)
    if len(hits)!=1:
        raise RuntimeError(f"Expected one charmap after font table, got {len(hits)}")
    return PSP_START+hits[0]

def main():
    LOG_DIR.mkdir(parents=True,exist_ok=True)
    ANALYSIS_DIR.mkdir(parents=True,exist_ok=True)

    script_dir=Path(__file__).resolve().parent
    replacement_src=script_dir/ATLAS_NAME
    if not replacement_src.exists():
        raise RuntimeError(f"Bundled replacement atlas missing: {replacement_src}")

    dump_new=find_dump_new()
    dumped=dump_new/ATLAS_NAME
    if dumped.exists():
        got=sha1_file(dumped)
        if got != EXPECTED_DUMP_SHA1:
            raise RuntimeError(
                f"Dumped TMR18 atlas SHA1 mismatch.\n"
                f"Expected {EXPECTED_DUMP_SHA1}\nGot      {got}"
            )

    game_dir=dump_new.parent
    replacement_dst=game_dir/ATLAS_NAME
    backup=game_dir/(ATLAS_NAME+".stage10_backup")

    print("="*80)
    print("BIA Stage 10 - first real Hangul glyph")
    print("="*80)
    print(f"Texture game dir : {game_dir}")
    print(f"Replacement file : {replacement_dst}")
    print()

    # Preserve any user's preexisting replacement.
    had_existing=replacement_dst.exists()
    if had_existing:
        if backup.exists():
            backup.unlink()
        shutil.copy2(replacement_dst,backup)

    shutil.copy2(replacement_src,replacement_dst)

    print("한글 테스트용 TMR18 replacement texture를 설치했습니다.")
    print()
    print("PPSSPP 설정에서 확인:")
    print("  Settings -> Tools -> Developer Tools -> Texture Replacement")
    print("  Replace textures = ON")
    print()
    print("Save new textures는 이제 OFF여도 됩니다.")
    print()
    print("중요: 이미 메인 메뉴가 떠 있었다면 텍스처 캐시 때문에")
    print("게임을 'Restart'하거나 ISO를 다시 부팅한 뒤 메인 메뉴로 오세요.")
    input("Replace textures ON + 게임 재부팅 + 메인 메뉴 준비 후 Enter... ")

    pid,base=get_ppsspp()
    h=open_process(pid)
    restored=[]
    report={
        "texture_dump_dir":str(dump_new),
        "replacement_path":str(replacement_dst),
        "replacement_sha1":sha1_file(replacement_dst),
        "test_mapping":"U+0080 -> glyph A(index33), atlas A cell replaced by 한",
    }

    try:
        ram=rpm(h,base+PSP_START,PSP_SIZE)
        tables=find_font_tables(ram)
        if len(tables)<2:
            raise RuntimeError(f"Expected >=2 font tables, found {len(tables)}")

        charmaps=[]
        for t in tables:
            charmaps.append(find_charmap_after_table(ram,t["ram_off"]))

        report["font_tables"]=[f"0x{x['guest']:08X}" for x in tables]
        report["charmaps"]=[f"0x{x:08X}" for x in charmaps]

        # U+0080 -> A glyph index 33, stored as glyph_index+1 = 34.
        for cmap in charmaps:
            guest=cmap+0x80*2
            host=base+guest
            old=rpm(h,host,2)
            if struct.unpack("<H",old)[0] != 0:
                raise RuntimeError(f"U+0080 charmap slot not empty at 0x{guest:08X}")
            restored.append((host,old))
            wpm(h,host,struct.pack("<H",34))

        story_guest=0x08E41620
        story_host=base+story_guest
        old_story=rpm(h,story_host,10)
        if old_story != "Story".encode("utf-16le"):
            got=old_story.decode("utf-16le","replace")
            raise RuntimeError(f"Expected Story live slot, got {got!r}")
        restored.append((story_host,old_story))

        # Five U+0080 code units.
        test=struct.pack("<5H",0x80,0x80,0x80,0x80,0x80)
        wpm(h,story_host,test)

        print()
        print("="*80)
        print("화면을 확인하세요.")
        print()
        print("Story 자리에는 U+0080을 5번 넣었고,")
        print("각 U+0080은 원래 A 글리프를 사용합니다.")
        print("하지만 PPSSPP replacement texture에서 A의 그림을 '한'으로 바꿨습니다.")
        print()
        print("성공 화면:")
        print()
        print("    한한한한한")
        print()
        print("이게 나오면 실제 한글 폰트 비트맵 출력까지 성공입니다.")
        print("="*80)

        while True:
            ans=input("화면에 실제 '한' 글자가 5개 보이나요? [y/n/?] ").strip().lower()
            if ans in ("y","n","?"):
                report["visual_result"]=ans
                break

        report_path=ANALYSIS_DIR/"stage10_report.json"
        report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")

        input("스크린샷을 찍었으면 Enter를 눌러 RAM을 복구합니다... ")

    finally:
        for host,old in reversed(restored):
            try: wpm(h,host,old)
            except Exception: pass
        kernel32.CloseHandle(h)

        # Restore user's replacement directory to pre-test state.
        try:
            if had_existing:
                shutil.copy2(backup,replacement_dst)
                backup.unlink(missing_ok=True)
            else:
                replacement_dst.unlink(missing_ok=True)
        except Exception as e:
            print(f"WARNING: replacement texture cleanup failed: {e}")

    upload=LOG_DIR/"bia_stage10_upload.zip"
    with zipfile.ZipFile(upload,"w",zipfile.ZIP_DEFLATED) as z:
        rp=ANALYSIS_DIR/"stage10_report.json"
        if rp.exists():
            z.write(rp,rp.name)

    print()
    print("RAM 및 replacement 파일 원복 완료.")
    print("PPSSPP 텍스처 캐시는 게임 재시작 후 완전히 원복됩니다.")
    print(f"Upload ZIP: {upload}")
    return 0

if __name__=="__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print()
        print("ERROR:",e)
        input("Enter를 누르면 종료합니다...")
        raise
