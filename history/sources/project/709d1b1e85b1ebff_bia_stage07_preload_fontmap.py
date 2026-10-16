#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import hashlib
import json
import shutil
import struct
import zlib
import zipfile
from pathlib import Path

ROOT_DEFAULT = Path(r"PROJECT_ROOT")
EXPECTED_MDI_SHA1 = "22de1f889d1617199a3e21d4a1f63fcaf87b944a"
TARGET_REL = Path("PSP_GAME") / "USRDIR" / "SYSTEM" / "ON_MEMU_O.MDI"

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

def sha1_bytes(b: bytes) -> str:
    return hashlib.sha1(b).hexdigest()

def valid_zlib_header(two: bytes) -> bool:
    if len(two) != 2:
        return False
    cmf, flg = two
    return (cmf & 0x0F) == 8 and ((cmf << 8) + flg) % 31 == 0

def parse_mdi(data: bytes):
    streams = []
    pos = 6
    idx = 0
    while pos + 4 <= len(data):
        csize = struct.unpack_from("<I", data, pos)[0]
        zpos = pos + 4
        if csize <= 0 or zpos + csize > len(data) or not valid_zlib_header(data[zpos:zpos+2]):
            if pos + 8 <= len(data):
                c2 = struct.unpack_from("<I", data, pos + 4)[0]
                z2 = pos + 8
                if c2 > 0 and z2 + c2 <= len(data) and valid_zlib_header(data[z2:z2+2]):
                    pos += 4
                    continue
            raise RuntimeError(f"Could not parse MDI at 0x{pos:X}")
        comp = data[zpos:zpos+csize]
        dec = zlib.decompress(comp)
        streams.append({
            "index": idx,
            "size_field_pos": pos,
            "zpos": zpos,
            "csize": csize,
            "decoded": dec,
        })
        pos = zpos + csize
        idx += 1
    if pos != len(data):
        raise RuntimeError(f"MDI parse ended at 0x{pos:X}, file size 0x{len(data):X}")
    return streams

def find_font_tables_in_dec(dec: bytes):
    rec = 24
    checks = [
        (0,0x0020),(1,0x002E),(2,0x0021),(14,0x002D),(15,0x002F),
        (16,0x0030),(25,0x0039),(33,0x0041),(58,0x005A),
        (65,0x0061),(90,0x007A),(95,0x00A1),(149,0x2122),
    ]
    out = []
    pos = 0
    while True:
        pos = dec.find(b"\x20\x00", pos)
        if pos < 0:
            break
        if pos + 150*rec <= len(dec):
            if all(struct.unpack_from("<H", dec, pos+i*rec)[0] == cp for i,cp in checks):
                out.append(pos)
        pos += 1
    return out

def patch_mdi_font_source(original: bytes):
    streams = parse_mdi(original)
    matches = []
    for st in streams:
        tables = find_font_tables_in_dec(st["decoded"])
        if tables:
            matches.append((st, tables))

    if len(matches) != 1:
        raise RuntimeError(f"Expected one MDI stream containing font tables, found {len(matches)}")

    st, tables = matches[0]
    if len(tables) != 2:
        raise RuntimeError(f"Expected two 150-glyph font tables, found {len(tables)}")

    dec = bytearray(st["decoded"])
    rows = []

    # Critical smoke test:
    # Replace ONLY final U+2122 TRADE MARK SIGN mapping with U+D55C HANGUL SYLLABLE HAN.
    # Do it in both menu font tables BEFORE font initialization.
    # This exact modification recompresses to the original zlib byte size.
    for ti, table in enumerate(tables):
        off = table + 149 * 24
        old = struct.unpack_from("<H", dec, off)[0]
        if old != 0x2122:
            raise RuntimeError(f"Table #{ti} final codepoint expected U+2122, got U+{old:04X}")
        struct.pack_into("<H", dec, off, 0xD55C)
        rows.append({
            "table": ti,
            "decoded_table_offset": f"0x{table:X}",
            "decoded_record_offset": f"0x{off:X}",
            "old": "U+2122 ™",
            "new": "U+D55C 한",
        })

    new_comp = zlib.compress(bytes(dec), 9)
    if len(new_comp) != st["csize"]:
        raise RuntimeError(
            f"Safety condition failed: stream compressed size changed "
            f"{st['csize']} -> {len(new_comp)}. Nothing patched."
        )

    patched = bytearray(original)
    patched[st["zpos"]:st["zpos"]+st["csize"]] = new_comp

    # Reparse and verify exact locations.
    verify_streams = parse_mdi(bytes(patched))
    vst = verify_streams[st["index"]]
    vtables = []
    # Modified table now ends in D55C, so use all fixed checks except final.
    rec = 24
    dec2 = vst["decoded"]
    p = 0
    while True:
        p = dec2.find(b"\x20\x00", p)
        if p < 0:
            break
        if p + 150*rec <= len(dec2):
            checks = [(0,0x20),(1,0x2E),(2,0x21),(33,0x41),(65,0x61),(95,0xA1),(149,0xD55C)]
            if all(struct.unpack_from("<H",dec2,p+i*rec)[0] == cp for i,cp in checks):
                vtables.append(p)
        p += 1

    if vtables != tables:
        raise RuntimeError(f"Post-patch table verification mismatch: {vtables} != {tables}")

    return bytes(patched), st, tables, rows

def iso_norm_name(raw: bytes) -> str:
    if raw == b"\x00": return "."
    if raw == b"\x01": return ".."
    s = raw.decode("ascii", "replace")
    if ";" in s:
        s = s.split(";",1)[0]
    return s.upper()

def iso_read_record(f, off):
    f.seek(off)
    b = f.read(1)
    if not b:
        return None
    ln = b[0]
    if ln == 0:
        return {"length":0}
    rec = b + f.read(ln-1)
    if len(rec) != ln or ln < 34:
        return None
    return {
        "length": ln,
        "extent": struct.unpack_from("<I",rec,2)[0],
        "size": struct.unpack_from("<I",rec,10)[0],
        "flags": rec[25],
        "name": iso_norm_name(rec[33:33+rec[32]]),
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
            pos = ((pos//2048)+1)*2048
            continue
        rec = iso_read_record(f,pos)
        if not rec:
            raise RuntimeError(f"Bad ISO9660 directory record at 0x{pos:X}")
        yield rec
        pos += rec["length"]

def iso_find(iso_path: Path, parts):
    with iso_path.open("rb") as f:
        f.seek(16*2048)
        pvd = f.read(2048)
        if len(pvd) != 2048 or pvd[0] != 1 or pvd[1:6] != b"CD001":
            raise RuntimeError("ISO9660 PVD not found")
        rl = pvd[156]
        root = pvd[156:156+rl]
        extent = struct.unpack_from("<I",root,2)[0]
        size = struct.unpack_from("<I",root,10)[0]
        for i,part in enumerate(parts):
            found = None
            for rec in iso_list_dir(f,extent,size):
                if rec["name"] == part.upper():
                    found = rec
                    break
            if not found:
                raise RuntimeError(f"ISO path not found: {part}")
            extent,size = found["extent"],found["size"]
        return extent,size

def locate_original_iso(root: Path):
    isos = []
    for p in root.glob("*.iso"):
        u = p.name.upper()
        if "STAGE" in u or "TEST" in u:
            continue
        if p.is_file():
            isos.append(p)
    if not isos:
        raise RuntimeError("Original ISO not found in PROJECT_ROOT")
    bia = [p for p in isos if "BROTHERS" in p.name.upper() or "D-DAY" in p.name.upper()]
    return max(bia or isos, key=lambda p:p.stat().st_size)

def get_ppsspp():
    hwnd = user32.FindWindowW("PPSSPPWnd", None)
    if not hwnd:
        raise RuntimeError("PPSSPP window not found.")
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    low = int(user32.SendMessageW(hwnd,WM_USER_GET_BASE_POINTER,0,0)) & 0xFFFFFFFF
    high = int(user32.SendMessageW(hwnd,WM_USER_GET_BASE_POINTER,0,1)) & 0xFFFFFFFF
    base = (high<<32)|low
    if not pid.value or not base:
        raise RuntimeError("Could not obtain PPSSPP PSP memory base.")
    return pid.value,base

def open_process(pid):
    h = kernel32.OpenProcess(
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

def find_loaded_modified_tables(ram: bytes):
    rec=24
    checks=[
        (0,0x20),(1,0x2E),(2,0x21),(14,0x2D),(15,0x2F),
        (16,0x30),(25,0x39),(33,0x41),(58,0x5A),
        (65,0x61),(90,0x7A),(95,0xA1),(149,0xD55C),
    ]
    out=[]
    pos=0
    while True:
        pos=ram.find(b"\x20\x00",pos)
        if pos<0: break
        if pos+150*rec<=len(ram):
            if all(struct.unpack_from("<H",ram,pos+i*rec)[0]==cp for i,cp in checks):
                out.append(PSP_START+pos)
        pos+=1
    return out

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--root",default=str(ROOT_DEFAULT))
    args=ap.parse_args()

    root=Path(args.root)
    log_dir=root/"log"
    stage_dir=root/"analysis"/"stage07_preload_fontmap"
    patch_dir=root/"patch"/"stage07"
    log_dir.mkdir(parents=True,exist_ok=True)
    stage_dir.mkdir(parents=True,exist_ok=True)
    patch_dir.mkdir(parents=True,exist_ok=True)

    # Use the original extracted MDI only as a source/validation reference.
    candidates=[
        root/"extracted"/TARGET_REL,
        root/TARGET_REL,
    ]
    mdi_path=next((p for p in candidates if p.exists()),None)
    if mdi_path is None:
        raise RuntimeError("Extracted ON_MEMU_O.MDI not found.")

    original=mdi_path.read_bytes()

    # If extracted tree was modified by an older stage, prefer Stage 04 backup.
    if sha1_bytes(original) != EXPECTED_MDI_SHA1:
        backup=root/"backup"/"stage04"/"ON_MEMU_O.MDI"
        if backup.exists() and sha1_bytes(backup.read_bytes()) == EXPECTED_MDI_SHA1:
            original=backup.read_bytes()
        else:
            raise RuntimeError(
                f"Could not find expected original MDI SHA1 {EXPECTED_MDI_SHA1}"
            )

    patched,st,tables,rows=patch_mdi_font_source(original)
    patched_path=patch_dir/"ON_MEMU_O.MDI"
    patched_path.write_bytes(patched)

    source_iso=locate_original_iso(root)
    test_iso=root/"BIA_STAGE07_FONTLOAD_TEST.iso"
    print("="*80)
    print("BIA Stage 07 - PRELOAD font lookup test")
    print("="*80)
    print(f"Source ISO : {source_iso}")
    print(f"Test ISO   : {test_iso}")
    print(f"MDI stream : {st['index']}")
    print(f"Font tables: {', '.join(hex(x) for x in tables)}")
    print(f"zlib size  : {st['csize']} -> {st['csize']} EXACT")
    print()

    shutil.copy2(source_iso,test_iso)
    extent,size=iso_find(test_iso,list(TARGET_REL.parts))
    if size != len(original):
        raise RuntimeError(f"ISO MDI size {size} != expected {len(original)}")
    iso_off=extent*2048

    with test_iso.open("r+b") as f:
        f.seek(iso_off)
        iso_old=f.read(size)
        if sha1_bytes(iso_old) != EXPECTED_MDI_SHA1:
            raise RuntimeError("Original ISO MDI does not match expected Stage 03 MDI.")
        f.seek(iso_off)
        f.write(patched)

    with test_iso.open("rb") as f:
        f.seek(iso_off)
        if f.read(size) != patched:
            raise RuntimeError("ISO patch verification failed.")

    report={
        "source_iso":str(source_iso),
        "test_iso":str(test_iso),
        "original_mdi_sha1":EXPECTED_MDI_SHA1,
        "patched_mdi_sha1":sha1_bytes(patched),
        "mdi_stream":st["index"],
        "compressed_size":st["csize"],
        "font_tables_decoded_offsets":[hex(x) for x in tables],
        "font_mapping_changes":rows,
        "iso_lba":extent,
        "iso_file_offset":hex(iso_off),
    }

    print("ISO 생성 완료.")
    print()
    print("이제 PPSSPP에서 반드시:")
    print(f"  {test_iso}")
    print("를 새로 부팅하고 메인 메뉴 STORY가 보이는 상태로 두세요.")
    print()
    input("새 테스트 ISO를 부팅한 뒤 Enter... ")

    pid,base=get_ppsspp()
    h=open_process(pid)
    answer="?"
    try:
        ram=rpm(h,base+PSP_START,PSP_SIZE)
        loaded=find_loaded_modified_tables(ram)
        report["runtime_font_tables"]=[hex(x) for x in loaded]

        if len(loaded)<2:
            raise RuntimeError(
                "RAM에서 U+D55C로 수정된 두 폰트 테이블을 찾지 못했습니다.\n"
                "BIA_STAGE07_FONTLOAD_TEST.iso를 완전히 재부팅했는지 확인하세요."
            )

        print()
        print("부팅 전 폰트 패치가 RAM까지 정상 로드됨:")
        for x in loaded:
            print(f"  PSP {x:#010x}: final glyph = U+D55C 한")

        story_guest=0x08E41620
        story_host=base+story_guest
        old_story=rpm(h,story_host,10)
        if old_story != "Story".encode("utf-16le"):
            got=old_story.decode("utf-16le","replace")
            raise RuntimeError(
                f"Story live slot mismatch: {got!r}. 메인 메뉴로 돌아가 다시 실행하세요."
            )

        test="한한한한한".encode("utf-16le")
        wpm(h,story_host,test)
        if rpm(h,story_host,10) != test:
            raise RuntimeError("Live Story test write verification failed.")

        print()
        print("="*80)
        print("화면을 확인하세요.")
        print()
        print("STORY 자리에 '한한한한한'을 넣었습니다.")
        print("성공 조건:")
        print("  □□□□□ 가 아니라 기존 ™ donor 글리프가 5번 보임")
        print()
        print("이게 성공하면:")
        print("  MDI 원본 폰트 테이블 -> 부팅 시 lookup/cache 생성")
        print("경로가 완전히 확정됩니다.")
        print()
        print("지금 스크린샷을 찍으세요.")
        print("="*80)

        while True:
            a=input("□ 대신 donor 글리프가 보이나요? [y/n/?] ").strip().lower()
            if a in ("y","n","?"):
                answer=a
                break

        report["visual_result"]=answer
        input("Enter를 누르면 Story 문자열을 원래대로 복구합니다... ")
        wpm(h,story_host,old_story)

    finally:
        kernel32.CloseHandle(h)

    report_path=stage_dir/"stage07_report.json"
    report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")

    upload=log_dir/"bia_stage07_upload.zip"
    with zipfile.ZipFile(upload,"w",zipfile.ZIP_DEFLATED) as z:
        z.write(report_path,report_path.name)
        z.write(patched_path,"patched/ON_MEMU_O.MDI")

    print()
    print("완료.")
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
