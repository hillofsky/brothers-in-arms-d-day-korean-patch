#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import math
import os
import re
import zipfile
from pathlib import Path

DEFAULT_ROOT = Path(r"PROJECT_ROOT")
STAGE = "stage03_font_asset_locator"

NEEDLES = [
    b"WargameFont",
    b"WargameFont_PageA",
    b"t_gbxfonts",
    b"AB18",
    b"TMR18",
    b".mft",
    b"MFT",
    b"FontArrayNames",
    b"DefaultFont",
]

SCAN_EXTS = {
    ".mdi", ".dsl", ".dsx", ".raw", ".mgm", ".prx", ".bin",
    ".int", ".ini"
}

def sha1_file(path: Path) -> str:
    h = hashlib.sha1()
    with path.open("rb") as f:
        while True:
            b = f.read(1024 * 1024)
            if not b:
                break
            h.update(b)
    return h.hexdigest()

def find_game_root(root: Path) -> Path:
    for c in [root, root/"extracted", root/"iso_extracted", root/"game"]:
        if (c/"PSP_GAME").is_dir():
            return c
    for p in root.glob("*/PSP_GAME"):
        if p.is_dir():
            return p.parent
    raise SystemExit("Could not locate extracted PSP_GAME tree under PROJECT_ROOT")

def rel(p: Path, base: Path) -> str:
    return str(p.relative_to(base)).replace("/", "\\")

def ascii_context(data: bytes, off: int, n: int, radius=96) -> str:
    chunk = data[max(0, off-radius):min(len(data), off+n+radius)]
    return "".join(chr(b) if 32 <= b <= 126 else "." for b in chunk)

def scan_file(path: Path, game_root: Path):
    try:
        data = path.read_bytes()
    except Exception:
        return []
    low = data.lower()
    rows = []
    seen = set()
    for needle in NEEDLES:
        n = needle.lower()
        pos = 0
        while True:
            off = low.find(n, pos)
            if off < 0:
                break
            key = (off, n)
            if key not in seen:
                seen.add(key)
                rows.append([
                    rel(path, game_root),
                    path.stat().st_size,
                    f"0x{off:08X}",
                    needle.decode("ascii", "replace"),
                    ascii_context(data, off, len(needle)),
                ])
            pos = off + 1
    return rows

def compare_bytes(a: bytes, b: bytes):
    n = min(len(a), len(b))
    diffs = [i for i in range(n) if a[i] != b[i]]
    extra = abs(len(a)-len(b))
    if not diffs and not extra:
        return 0, "", "", 1.0
    first = diffs[0] if diffs else n
    last = diffs[-1] if diffs else n
    count = len(diffs) + extra
    denom = max(len(a), len(b), 1)
    return count, f"0x{first:08X}", f"0x{last:08X}", 1.0 - count/denom

def write_pgm(path: Path, pixels: bytes, width: int):
    if width <= 0:
        return
    height = (len(pixels) + width - 1) // width
    padded = pixels + b"\x00" * (width * height - len(pixels))
    with path.open("wb") as f:
        f.write(f"P5\n{width} {height}\n255\n".encode("ascii"))
        f.write(padded)

def write_raw_block_contact_pgm(path: Path, data: bytes):
    # MENU*.RAW size is exactly 17 * 0x4000. Interpret each 0x4000 block
    # as 128x128 8bpp and arrange them in a 5x4 contact sheet.
    block_size = 0x4000
    blocks = [data[i:i+block_size] for i in range(0, len(data), block_size)]
    blocks = [b for b in blocks if len(b) == block_size]
    if not blocks:
        return
    bw = bh = 128
    cols = 5
    rows = (len(blocks) + cols - 1) // cols
    canvas = bytearray(cols*bw * rows*bh)
    W = cols*bw
    for idx, block in enumerate(blocks):
        bx = (idx % cols) * bw
        by = (idx // cols) * bh
        for y in range(bh):
            src = block[y*bw:(y+1)*bw]
            dst = (by+y)*W + bx
            canvas[dst:dst+bw] = src
    with path.open("wb") as f:
        f.write(f"P5\n{W} {rows*bh}\n255\n".encode("ascii"))
        f.write(canvas)

def write_xor_contact_pgm(path: Path, a: bytes, b: bytes):
    n = min(len(a), len(b))
    x = bytes((a[i] ^ b[i]) for i in range(n))
    write_raw_block_contact_pgm(path, x)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(DEFAULT_ROOT))
    args = ap.parse_args()

    root = Path(args.root)
    game_root = find_game_root(root)
    system = game_root/"PSP_GAME"/"USRDIR"/"SYSTEM"
    rawdir = system/"RAWFILES"
    analysis = root/"analysis"/STAGE
    logdir = root/"log"
    analysis.mkdir(parents=True, exist_ok=True)
    logdir.mkdir(parents=True, exist_ok=True)

    print("="*78)
    print("Brothers in Arms: D-Day PSP - Stage 03 font asset locator")
    print("="*78)
    print(f"Game root : {game_root}")
    print(f"Analysis  : {analysis}")

    # Scan relevant converted assets for font identifiers.
    hits = []
    scanned = 0
    for p in system.rglob("*"):
        if not p.is_file() or p.suffix.lower() not in SCAN_EXTS:
            continue
        # Skip audio/video-like giants by extension already; converted level files are useful.
        scanned += 1
        rows = scan_file(p, game_root)
        hits.extend(rows)
        if scanned % 50 == 0:
            print(f"  scanned {scanned} files, hits={len(hits)}")

    hits_path = analysis/"font_asset_hits.tsv"
    with hits_path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["path","bytes","offset","needle","context"])
        w.writerows(hits)

    # Menu and first-level assets most likely to contain common font/texture data.
    wanted_names = {
        "ON_MEMU.DSL", "ON_MEMU.DSX", "ON_MEMU_O.MDI",
        "D0_0130_.DSL", "D0_0130_.DSX", "D0_0130_.MDI",
        "BIA.RAW",
    }
    selected = []
    for p in system.rglob("*"):
        if p.is_file() and p.name.upper() in wanted_names:
            selected.append(p)

    # All menu RAW files, including language variants.
    menu_raws = []
    if rawdir.is_dir():
        menu_raws = sorted([p for p in rawdir.glob("MENU*.RAW") if p.is_file()])
        selected.extend(menu_raws)

    # Any converted asset with a direct font-name hit is also included if reasonably sized.
    hit_paths = {row[0] for row in hits}
    for hp in hit_paths:
        p = game_root / Path(hp.replace("\\", os.sep))
        if p.exists() and p.is_file() and p.stat().st_size <= 32*1024*1024:
            selected.append(p)

    # Deduplicate.
    uniq = []
    seen = set()
    for p in selected:
        rp = p.resolve()
        if rp not in seen:
            seen.add(rp)
            uniq.append(p)
    selected = uniq

    # Compare menu language raw files byte-for-byte.
    raw_cmp_path = analysis/"menu_raw_compare.tsv"
    base = rawdir/"MENUINT0.RAW"
    base_data = base.read_bytes() if base.exists() else None
    with raw_cmp_path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["file","bytes","sha1","diff_bytes_vs_MENUINT0","first_diff","last_diff","similarity"])
        for p in menu_raws:
            data = p.read_bytes()
            if base_data is not None:
                count, first, last, sim = compare_bytes(base_data, data)
            else:
                count, first, last, sim = "", "", "", ""
            w.writerow([
                p.name, len(data), sha1_file(p), count, first, last,
                f"{sim:.8f}" if isinstance(sim, float) else sim
            ])

    # Per-0x4000 block comparison to identify language-sensitive texture blocks.
    block_cmp_path = analysis/"menu_raw_block_compare.tsv"
    with block_cmp_path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["file","block_index","offset","diff_bytes_vs_MENUINT0","block_size"])
        if base_data is not None:
            for p in menu_raws:
                data = p.read_bytes()
                nblocks = max(len(base_data), len(data)) // 0x4000
                for bi in range(nblocks):
                    a = base_data[bi*0x4000:(bi+1)*0x4000]
                    b = data[bi*0x4000:(bi+1)*0x4000]
                    n = min(len(a),len(b))
                    diff = sum(1 for i in range(n) if a[i] != b[i]) + abs(len(a)-len(b))
                    w.writerow([p.name, bi, f"0x{bi*0x4000:08X}", diff, max(len(a),len(b))])

    # Generate visual aids in portable PGM format (no Pillow dependency).
    visdir = analysis/"raw_visuals"
    visdir.mkdir(exist_ok=True)
    for p in menu_raws:
        data = p.read_bytes()
        write_pgm(visdir/(p.stem+"_linear512.pgm"), data, 512)
        write_raw_block_contact_pgm(visdir/(p.stem+"_blocks128.pgm"), data)
        if base_data is not None and p.name.upper() != "MENUINT0.RAW":
            write_xor_contact_pgm(visdir/(p.stem+"_xor_vs_INT_blocks128.pgm"), base_data, data)

    # Selected file manifest.
    sel_path = analysis/"selected_assets.tsv"
    with sel_path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["path","bytes","sha1"])
        for p in selected:
            w.writerow([rel(p, game_root), p.stat().st_size, sha1_file(p)])

    report = []
    report.append("Brothers in Arms: D-Day PSP - Stage 03 report")
    report.append("="*78)
    report.append(f"Scanned converted/resource files: {scanned}")
    report.append(f"Direct font-name hits: {len(hits)}")
    report.append(f"Selected raw assets: {len(selected)}")
    report.append(f"Menu RAW files: {len(menu_raws)}")
    report.append("")
    if base_data is not None:
        report.append(f"MENUINT0.RAW size: {len(base_data)} bytes = 0x{len(base_data):X}")
        if len(base_data) % 0x4000 == 0:
            report.append(f"0x4000 blocks: {len(base_data)//0x4000}")
    report.append("")
    report.append("This stage intentionally does not patch the game yet.")
    report.append("It locates the converted PSP font/texture asset before changing glyph data.")
    report_path = analysis/"report.txt"
    report_path.write_text("\n".join(report)+"\n", encoding="utf-8")

    zip_path = logdir/"bia_stage03_upload.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for p in [report_path, hits_path, raw_cmp_path, block_cmp_path, sel_path]:
            z.write(p, "analysis/"+p.name)
        for p in visdir.glob("*.pgm"):
            z.write(p, "analysis/raw_visuals/"+p.name)
        for p in selected:
            z.write(p, "raw/"+rel(p, game_root).replace("\\","/"))

    print("")
    print(f"Scanned files       : {scanned}")
    print(f"Font identifier hits: {len(hits)}")
    print(f"Selected assets     : {len(selected)}")
    print(f"Menu RAWs           : {len(menu_raws)}")
    print("")
    print("="*78)
    print("Stage 03 complete")
    print(f"Upload ZIP: {zip_path}")
    print("="*78)

if __name__ == "__main__":
    raise SystemExit(main())
