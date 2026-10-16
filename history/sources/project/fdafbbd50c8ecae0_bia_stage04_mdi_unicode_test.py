#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import struct
import zlib
import zipfile
from pathlib import Path

ROOT_DEFAULT = Path(r"PROJECT_ROOT")
EXPECTED_MDI_SHA1 = "22de1f889d1617199a3e21d4a1f63fcaf87b944a"
TARGET_REL = Path("PSP_GAME") / "USRDIR" / "SYSTEM" / "ON_MEMU_O.MDI"

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
    for c in [root, root / "extracted", root / "iso_extracted", root / "game"]:
        if (c / "PSP_GAME").is_dir():
            return c
    for p in root.glob("*/PSP_GAME"):
        if p.is_dir():
            return p.parent
    raise RuntimeError("Extracted PSP_GAME tree was not found under PROJECT_ROOT")

def valid_zlib_header(two: bytes) -> bool:
    if len(two) != 2:
        return False
    cmf, flg = two
    return (cmf & 0x0F) == 8 and ((cmf << 8) + flg) % 31 == 0

def parse_mdi_streams(data: bytes):
    # ON_MEMU_O.MDI layout discovered from Stage 03:
    #   initial 6-byte prefix
    #   repeated: u32 compressed_size + zlib_stream
    #   some regions are separated by an additional 4-byte load-address marker.
    #
    # We do not need to reinterpret every region to patch a same-size stream;
    # this parser simply walks every compressed block safely.
    streams = []
    pos = 6
    index = 0

    while pos + 4 <= len(data):
        csize = struct.unpack_from("<I", data, pos)[0]
        zpos = pos + 4
        if csize <= 0 or zpos + csize > len(data) or not valid_zlib_header(data[zpos:zpos+2]):
            # A four-byte region/load-address marker may precede the next csize.
            if pos + 8 <= len(data):
                marker = struct.unpack_from("<I", data, pos)[0]
                c2 = struct.unpack_from("<I", data, pos + 4)[0]
                z2 = pos + 8
                if c2 > 0 and z2 + c2 <= len(data) and valid_zlib_header(data[z2:z2+2]):
                    pos += 4
                    continue
            raise RuntimeError(f"Could not parse MDI at file offset 0x{pos:X}")

        comp = data[zpos:zpos+csize]
        try:
            dec = zlib.decompress(comp)
        except Exception as e:
            raise RuntimeError(f"zlib failure in MDI stream {index} at 0x{zpos:X}: {e}")

        streams.append({
            "index": index,
            "size_field_pos": pos,
            "zpos": zpos,
            "csize": csize,
            "decoded": dec,
        })
        pos = zpos + csize
        index += 1

    if pos != len(data):
        raise RuntimeError(f"MDI parser stopped at 0x{pos:X}, file size 0x{len(data):X}")
    return streams

def find_all(buf: bytes, needle: bytes):
    out = []
    p = 0
    while True:
        i = buf.find(needle, p)
        if i < 0:
            return out
        out.append(i)
        p = i + 1

def u16(s: str) -> bytes:
    return s.encode("utf-16le")

def find_main_menu_stream(streams):
    labels = ["STORY", "SKIRMISH", "OPTIONS", "PROFILES", "CONTINUE",
              "CHAPTERS", "EASY", "NORMAL", "HARD", "AUTHENTIC"]
    candidates = []

    for st in streams:
        dec = st["decoded"]
        poss = {name: find_all(dec, u16(name)) for name in labels}
        for p_story in poss["STORY"]:
            # Stage 03 showed the main-menu block has these labels in this exact
            # order within ~2.5 KiB. Use that structure instead of hardcoding a
            # stream number or decompressed offset.
            chosen = {"STORY": p_story}
            cur = p_story
            ok = True
            for name in labels[1:]:
                nxt = [x for x in poss[name] if cur < x < p_story + 3000]
                if not nxt:
                    ok = False
                    break
                chosen[name] = nxt[0]
                cur = nxt[0]
            if ok:
                candidates.append((st, chosen))

    if len(candidates) != 1:
        desc = [(x[0]["index"], x[1].get("STORY")) for x in candidates]
        raise RuntimeError(f"Expected exactly one main-menu label cluster, found {len(candidates)}: {desc}")
    return candidates[0]

def patch_mdi(original: bytes):
    streams = parse_mdi_streams(original)
    st, pos = find_main_menu_stream(streams)

    dec = bytearray(st["decoded"])

    # Two immediately visible controls:
    #   STORY    -> 한글테스트  (5 UTF-16 code units, same byte count)
    #   SKIRMISH -> TESTTEST    (8 chars, same byte count)
    #
    # NORMAL/HARD are changed only to keep the zlib block EXACTLY the original
    # compressed size. That lets us patch the ISO in place without rebuilding
    # the ISO9660 filesystem.
    replacements = [
        ("STORY",    "한글테스트"),
        ("SKIRMISH", "TESTTEST"),
        ("NORMAL",   "NNNNNN"),
        ("HARD",     "TEST"),
    ]

    patch_rows = []
    for old, new in replacements:
        if len(old) != len(new):
            raise RuntimeError(f"Internal error: replacement length mismatch {old!r} -> {new!r}")
        p = pos[old]
        oldb = u16(old)
        newb = u16(new)
        if bytes(dec[p:p+len(oldb)]) != oldb:
            raise RuntimeError(f"Expected {old!r} at decoded offset 0x{p:X}")
        dec[p:p+len(oldb)] = newb
        patch_rows.append((old, new, p))

    new_comp = zlib.compress(bytes(dec), 9)
    old_csize = st["csize"]

    if len(new_comp) != old_csize:
        raise RuntimeError(
            "The safety condition failed: patched zlib size changed "
            f"({old_csize} -> {len(new_comp)}). Nothing was installed."
        )

    patched = bytearray(original)
    patched[st["zpos"]:st["zpos"]+old_csize] = new_comp

    # Full validation: every MDI zlib stream must still parse/decompress.
    check = parse_mdi_streams(bytes(patched))
    if len(check) != len(streams):
        raise RuntimeError("Patched MDI stream count changed unexpectedly.")

    st2 = check[st["index"]]["decoded"]
    for old, new, p in patch_rows:
        if st2[p:p+len(u16(new))] != u16(new):
            raise RuntimeError(f"Post-patch verification failed for {new!r}")

    return bytes(patched), st, patch_rows, len(streams)

def iso_read_dir_record(iso, offset: int):
    iso.seek(offset)
    lraw = iso.read(1)
    if not lraw:
        return None
    ln = lraw[0]
    if ln == 0:
        return {"length": 0}
    rest = iso.read(ln - 1)
    rec = lraw + rest
    if len(rec) != ln or ln < 34:
        return None
    extent = struct.unpack_from("<I", rec, 2)[0]
    size = struct.unpack_from("<I", rec, 10)[0]
    flags = rec[25]
    nlen = rec[32]
    name = rec[33:33+nlen]
    return {
        "length": ln,
        "extent": extent,
        "size": size,
        "flags": flags,
        "name_raw": name,
    }

def iso_norm_name(raw: bytes) -> str:
    if raw == b"\x00":
        return "."
    if raw == b"\x01":
        return ".."
    s = raw.decode("ascii", "replace")
    if ";" in s:
        s = s.split(";", 1)[0]
    return s.upper()

def iso_list_dir(iso, extent: int, size: int):
    start = extent * 2048
    end = start + size
    pos = start
    rows = []
    while pos < end:
        iso.seek(pos)
        b = iso.read(1)
        if not b:
            break
        ln = b[0]
        if ln == 0:
            # Directory records never cross a sector boundary.
            pos = ((pos // 2048) + 1) * 2048
            continue
        rec = iso_read_dir_record(iso, pos)
        if not rec:
            raise RuntimeError(f"Bad ISO9660 directory record at 0x{pos:X}")
        rec["name"] = iso_norm_name(rec["name_raw"])
        rows.append(rec)
        pos += rec["length"]
    return rows

def iso_find(iso_path: Path, components):
    with iso_path.open("rb") as f:
        f.seek(16 * 2048)
        pvd = f.read(2048)
        if len(pvd) != 2048 or pvd[0] != 1 or pvd[1:6] != b"CD001":
            raise RuntimeError("ISO9660 Primary Volume Descriptor not found.")

        root_len = pvd[156]
        root = pvd[156:156+root_len]
        root_extent = struct.unpack_from("<I", root, 2)[0]
        root_size = struct.unpack_from("<I", root, 10)[0]

        extent, size = root_extent, root_size
        for idx, part in enumerate(components):
            want = part.upper()
            found = None
            for rec in iso_list_dir(f, extent, size):
                if rec["name"] == want:
                    found = rec
                    break
            if found is None:
                raise RuntimeError(f"ISO path component not found: {part}")
            if idx != len(components) - 1 and not (found["flags"] & 0x02):
                raise RuntimeError(f"ISO path component is not a directory: {part}")
            extent, size = found["extent"], found["size"]
        return extent, size

def locate_source_iso(root: Path):
    isos = [p for p in root.glob("*.iso") if p.is_file() and "STAGE04_TEST" not in p.name.upper()]
    if not isos:
        return None
    # Prefer known BIA name, otherwise largest ISO.
    bia = [p for p in isos if "BROTHERS IN ARMS" in p.name.upper() or "D-DAY" in p.name.upper()]
    pool = bia or isos
    return max(pool, key=lambda p: p.stat().st_size)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(ROOT_DEFAULT))
    args = ap.parse_args()

    root = Path(args.root)
    game_root = find_game_root(root)
    mdi_path = game_root / TARGET_REL
    if not mdi_path.exists():
        raise RuntimeError(f"Missing {mdi_path}")

    original = mdi_path.read_bytes()
    original_sha = sha1_bytes(original)

    print("=" * 78)
    print("Brothers in Arms: D-Day PSP - Stage 04 MDI Unicode smoke test")
    print("=" * 78)
    print(f"Game root     : {game_root}")
    print(f"MDI           : {mdi_path}")
    print(f"MDI SHA1      : {original_sha}")

    if original_sha != EXPECTED_MDI_SHA1:
        raise RuntimeError(
            "ON_MEMU_O.MDI does not match the Stage 03 file. "
            f"Expected {EXPECTED_MDI_SHA1}, got {original_sha}. Nothing changed."
        )

    patched, target_stream, rows, stream_count = patch_mdi(original)
    patched_sha = sha1_bytes(patched)

    patch_dir = root / "patch" / "stage04"
    backup_dir = root / "backup" / "stage04"
    log_dir = root / "log"
    patch_dir.mkdir(parents=True, exist_ok=True)
    backup_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)

    patched_path = patch_dir / "ON_MEMU_O.MDI"
    backup_path = backup_dir / "ON_MEMU_O.MDI"
    patched_path.write_bytes(patched)

    if not backup_path.exists():
        backup_path.write_bytes(original)
    elif sha1_file(backup_path) != original_sha:
        raise RuntimeError(f"Existing backup differs from original: {backup_path}")

    # Install into the extracted tree for inspection/restoration.
    mdi_path.write_bytes(patched)
    if sha1_file(mdi_path) != patched_sha:
        raise RuntimeError("Extracted-tree install verification failed.")

    report = []
    report.append("Brothers in Arms: D-Day PSP - Stage 04 report")
    report.append("=" * 78)
    report.append(f"Original MDI SHA1 : {original_sha}")
    report.append(f"Patched MDI SHA1  : {patched_sha}")
    report.append(f"MDI bytes          : {len(original)} (size preserved)")
    report.append(f"zlib streams       : {stream_count}")
    report.append(f"patched stream     : {target_stream['index']}")
    report.append(f"stream file offset : 0x{target_stream['zpos']:08X}")
    report.append(f"compressed bytes   : {target_stream['csize']} (exactly preserved)")
    report.append("")
    report.append("UTF-16LE replacements:")
    for old, new, p in rows:
        report.append(f"  {old:8s} -> {new}  decoded_offset=0x{p:08X}")
    report.append("")
    report.append(f"Extracted backup   : {backup_path}")
    report.append(f"Extracted installed: {mdi_path}")

    # Make a directly testable ISO copy and patch the MDI extent in-place.
    source_iso = locate_source_iso(root)
    test_iso = root / "BIA_STAGE04_TEST.iso"
    if source_iso:
        print(f"Source ISO    : {source_iso}")
        print(f"Creating test : {test_iso}")
        shutil.copy2(source_iso, test_iso)

        extent, iso_size = iso_find(
            test_iso,
            ["PSP_GAME", "USRDIR", "SYSTEM", "ON_MEMU_O.MDI"]
        )
        file_off = extent * 2048
        if iso_size != len(original):
            raise RuntimeError(
                f"ISO MDI size mismatch: directory says {iso_size}, extracted has {len(original)}"
            )

        with test_iso.open("r+b") as f:
            f.seek(file_off)
            iso_old = f.read(iso_size)
            if sha1_bytes(iso_old) != original_sha:
                raise RuntimeError(
                    "MDI inside source ISO does not match extracted Stage 03 file. "
                    "The test ISO was not patched."
                )
            f.seek(file_off)
            f.write(patched)
            f.flush()

        with test_iso.open("rb") as f:
            f.seek(file_off)
            iso_new = f.read(iso_size)
        if sha1_bytes(iso_new) != patched_sha:
            raise RuntimeError("ISO patch verification failed.")

        report.append("")
        report.append(f"Source ISO          : {source_iso}")
        report.append(f"Test ISO            : {test_iso}")
        report.append(f"ISO MDI extent LBA  : {extent}")
        report.append(f"ISO MDI file offset : 0x{file_off:X}")
        report.append("ISO file size       : unchanged")
    else:
        report.append("")
        report.append("No source .ISO was found in PROJECT_ROOT; test ISO was not created.")

    report_path = patch_dir / "report.txt"
    report_path.write_text("\n".join(report) + "\n", encoding="utf-8")

    restore_ps1 = root / "patch" / "stage04" / "restore_stage04.ps1"
    restore_ps1.write_text(
        '$ErrorActionPreference="Stop"\n'
        f'Copy-Item -LiteralPath "{backup_path}" -Destination "{mdi_path}" -Force\n'
        'Write-Host "Stage 04 extracted MDI restored."\n',
        encoding="utf-8-sig"
    )

    upload_zip = log_dir / "bia_stage04_upload.zip"
    with zipfile.ZipFile(upload_zip, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(report_path, "report.txt")
        z.write(patched_path, "patched/ON_MEMU_O.MDI")
        z.write(restore_ps1, "restore_stage04.ps1")

    print("")
    print("Patch installed into extracted copy.")
    if source_iso:
        print(f"Launch this ISO in PPSSPP: {test_iso}")
    print(f"Upload log ZIP           : {upload_zip}")
    print("")
    print("Expected title-menu evidence:")
    print('  "SKIRMISH" should become "TESTTEST".')
    print('  "STORY" should attempt to render "한글테스트".')
    print("If TESTTEST appears but Korean does not, the MDI/string path is confirmed")
    print("and the remaining task is specifically the Korean glyph/font atlas.")
    print("=" * 78)

if __name__ == "__main__":
    raise SystemExit(main())
