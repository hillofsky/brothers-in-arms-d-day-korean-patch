#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import shutil
import struct
import zipfile
from pathlib import Path

ROOT_DEFAULT = Path(r"PROJECT_ROOT")

PATCHES = {
    "LOCALIZE.INT": [
        (b"MAINMENU_SINGLEPLAYER=Story",       b"MAINMENU_SINGLEPLAYER=LSTRY"),
        (b"MAINMENU_SKIRMISH=Skirmish",        b"MAINMENU_SKIRMISH=L_SKIRM_"),
        (b"MAINMENU_OPTIONS=Options",           b"MAINMENU_OPTIONS=L_OPTNS"),
    ],
    "NEWLOCALIZE.INT": [
        (b"SINGLEPLAYER=Story",                 b"SINGLEPLAYER=NSTRY"),
        (b"MULTIPLAYER=Skirmish",               b"MULTIPLAYER=N_SKIRM_"),
        (b"OPTIONS=Options",                     b"OPTIONS=N_OPTNS"),
        # "한글B" in UTF-8 is exactly 7 bytes, same as "Profile".
        (b"PROFILES=Profile",                    b"PROFILES=" + "한글B".encode("utf-8")),
    ],
}

TARGETS = [
    Path("PSP_GAME") / "USRDIR" / "SYSTEM" / "LOCALIZE.INT",
    Path("PSP_GAME") / "USRDIR" / "SYSTEM" / "NEWLOCALIZE.INT",
]

def sha1_bytes(b: bytes) -> str:
    return hashlib.sha1(b).hexdigest()

def sha1_file(p: Path) -> str:
    h = hashlib.sha1()
    with p.open("rb") as f:
        while True:
            c = f.read(1024 * 1024)
            if not c:
                break
            h.update(c)
    return h.hexdigest()

def find_game_root(root: Path) -> Path:
    for c in [root, root/"extracted", root/"iso_extracted", root/"game"]:
        if (c/"PSP_GAME").is_dir():
            return c
    for p in root.glob("*/PSP_GAME"):
        if p.is_dir():
            return p.parent
    raise RuntimeError("Could not find extracted PSP_GAME tree under PROJECT_ROOT")

def patch_blob(data: bytes, filename: str):
    out = bytearray(data)
    rows = []
    for old, new in PATCHES[filename]:
        if len(old) != len(new):
            raise RuntimeError(
                f"Internal patch length mismatch in {filename}: {old!r} -> {new!r} "
                f"({len(old)} != {len(new)})"
            )
        count = out.count(old)
        if count < 1:
            raise RuntimeError(f"{filename}: pattern not found: {old!r}")
        pos = 0
        patched = 0
        while True:
            i = out.find(old, pos)
            if i < 0:
                break
            out[i:i+len(old)] = new
            rows.append((filename, i, old, new))
            patched += 1
            pos = i + len(new)
        print(f"  {filename}: {old!r} -> {new!r} ({patched} occurrence(s))")
    return bytes(out), rows

def iso_norm_name(raw: bytes) -> str:
    if raw == b"\x00": return "."
    if raw == b"\x01": return ".."
    s = raw.decode("ascii", "replace")
    if ";" in s:
        s = s.split(";", 1)[0]
    return s.upper()

def iso_read_dir_record(f, off: int):
    f.seek(off)
    b = f.read(1)
    if not b:
        return None
    ln = b[0]
    if ln == 0:
        return {"length": 0}
    rec = b + f.read(ln-1)
    if len(rec) != ln or ln < 34:
        return None
    extent = struct.unpack_from("<I", rec, 2)[0]
    size = struct.unpack_from("<I", rec, 10)[0]
    flags = rec[25]
    nlen = rec[32]
    name = iso_norm_name(rec[33:33+nlen])
    return {"length": ln, "extent": extent, "size": size, "flags": flags, "name": name}

def iso_list_dir(f, extent: int, size: int):
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
        rec = iso_read_dir_record(f, pos)
        if not rec:
            raise RuntimeError(f"Bad ISO directory record at 0x{pos:X}")
        yield rec
        pos += rec["length"]

def iso_find(iso_path: Path, parts):
    with iso_path.open("rb") as f:
        f.seek(16*2048)
        pvd = f.read(2048)
        if len(pvd) != 2048 or pvd[0] != 1 or pvd[1:6] != b"CD001":
            raise RuntimeError("ISO9660 PVD not found")
        rlen = pvd[156]
        root = pvd[156:156+rlen]
        extent = struct.unpack_from("<I", root, 2)[0]
        size = struct.unpack_from("<I", root, 10)[0]

        for idx, part in enumerate(parts):
            found = None
            for rec in iso_list_dir(f, extent, size):
                if rec["name"] == part.upper():
                    found = rec
                    break
            if not found:
                raise RuntimeError(f"ISO path component not found: {part}")
            if idx != len(parts)-1 and not (found["flags"] & 0x02):
                raise RuntimeError(f"ISO path component is not a directory: {part}")
            extent, size = found["extent"], found["size"]
        return extent, size

def locate_original_iso(root: Path):
    isos = []
    for p in root.glob("*.iso"):
        u = p.name.upper()
        if "STAGE04" in u or "STAGE04B" in u:
            continue
        if p.is_file():
            isos.append(p)
    if not isos:
        return None
    bia = [p for p in isos if "BROTHERS" in p.name.upper() or "D-DAY" in p.name.upper()]
    return max(bia or isos, key=lambda p: p.stat().st_size)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(ROOT_DEFAULT))
    args = ap.parse_args()

    root = Path(args.root)
    game_root = find_game_root(root)
    patch_dir = root/"patch"/"stage04b"
    backup_dir = root/"backup"/"stage04b"
    log_dir = root/"log"
    patch_dir.mkdir(parents=True, exist_ok=True)
    backup_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)

    print("="*78)
    print("Brothers in Arms: D-Day PSP - Stage 04B localization routing test")
    print("="*78)

    # Undo Stage 04 extracted-tree MDI modification if its backup exists,
    # so this test changes only localization files.
    mdi_backup = root/"backup"/"stage04"/"ON_MEMU_O.MDI"
    mdi_live = game_root/"PSP_GAME"/"USRDIR"/"SYSTEM"/"ON_MEMU_O.MDI"
    if mdi_backup.exists() and mdi_live.exists():
        shutil.copy2(mdi_backup, mdi_live)
        print("[reset] Restored Stage 04 ON_MEMU_O.MDI in extracted tree.")

    patched_files = {}
    report = []
    report.append("Brothers in Arms: D-Day PSP - Stage 04B")
    report.append("="*78)
    report.append("Purpose: identify the live menu localization file and test UTF-8 Korean bytes.")
    report.append("")

    for rel in TARGETS:
        live = game_root / rel
        if not live.exists():
            raise RuntimeError(f"Missing extracted file: {live}")
        original = live.read_bytes()
        backup = backup_dir / rel.name
        if not backup.exists():
            backup.write_bytes(original)

        patched, rows = patch_blob(original, rel.name)
        if len(patched) != len(original):
            raise RuntimeError(f"{rel.name}: size changed unexpectedly")

        outp = patch_dir / rel.name
        outp.write_bytes(patched)
        live.write_bytes(patched)
        patched_files[rel] = (original, patched)

        report.append(f"{rel.name}")
        report.append(f"  original SHA1: {sha1_bytes(original)}")
        report.append(f"  patched  SHA1: {sha1_bytes(patched)}")
        report.append(f"  bytes         : {len(original)} (unchanged)")
        for fn, off, old, new in rows:
            report.append(
                f"  0x{off:08X}: {old.decode('ascii','replace')} -> "
                f"{new.decode('utf-8','replace')}"
            )
        report.append("")

    source_iso = locate_original_iso(root)
    test_iso = root/"BIA_STAGE04B_LOCALIZE_TEST.iso"
    if not source_iso:
        raise RuntimeError("Original ISO not found in PROJECT_ROOT")

    print(f"Source ISO : {source_iso}")
    print(f"Test ISO   : {test_iso}")
    shutil.copy2(source_iso, test_iso)

    for rel in TARGETS:
        original, patched = patched_files[rel]
        extent, size = iso_find(test_iso, list(rel.parts))
        if size != len(original):
            raise RuntimeError(
                f"{rel.name}: ISO size {size} != extracted size {len(original)}"
            )
        off = extent * 2048
        with test_iso.open("r+b") as f:
            f.seek(off)
            iso_old = f.read(size)
            if iso_old != original:
                # Original extracted tree may previously have been modified before backup.
                # Validate against patch patterns instead of silently writing wrong file.
                raise RuntimeError(
                    f"{rel.name}: file inside original ISO differs from extracted source. "
                    "Nothing further patched."
                )
            f.seek(off)
            f.write(patched)
            f.flush()

        with test_iso.open("rb") as f:
            f.seek(off)
            verify = f.read(size)
        if verify != patched:
            raise RuntimeError(f"{rel.name}: ISO verification failed")

        report.append(f"ISO patched: {rel}")
        report.append(f"  LBA        : {extent}")
        report.append(f"  file offset: 0x{off:X}")
        report.append(f"  size       : {size} (unchanged)")
        report.append("")

    report.append("Expected title-menu results:")
    report.append("  If NEWLOCALIZE.INT is live:")
    report.append("    Story    -> NSTRY")
    report.append("    Skirmish -> N_SKIRM_")
    report.append("    Options  -> N_OPTNS")
    report.append("    Profile  -> 한글B, or garbled/missing if UTF-8/Hangul is unsupported")
    report.append("")
    report.append("  If LOCALIZE.INT is live instead:")
    report.append("    Story    -> LSTRY")
    report.append("    Skirmish -> L_SKIRM_")
    report.append("    Options  -> L_OPTNS")
    report.append("    Profile is expected to remain unchanged.")
    report.append("")
    report.append("The original ISO is never modified.")

    report_path = patch_dir/"report.txt"
    report_path.write_text("\n".join(report)+"\n", encoding="utf-8")

    upload_zip = log_dir/"bia_stage04b_upload.zip"
    with zipfile.ZipFile(upload_zip, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(report_path, "report.txt")
        for rel in TARGETS:
            z.write(patch_dir/rel.name, "patched/"+rel.name)
            z.write(backup_dir/rel.name, "original/"+rel.name)

    print("")
    print("="*78)
    print("Stage 04B complete")
    print(f"Launch ISO : {test_iso}")
    print(f"Upload ZIP : {upload_zip}")
    print("")
    print("Expected NEWLOCALIZE menu:")
    print("  NSTRY / N_SKIRM_ / N_OPTNS / [Hangul test in Profile]")
    print("Expected LOCALIZE menu:")
    print("  LSTRY / L_SKIRM_ / L_OPTNS / Profile")
    print("="*78)

if __name__ == "__main__":
    raise SystemExit(main())
