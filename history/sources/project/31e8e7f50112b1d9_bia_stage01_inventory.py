#!/usr/bin/env python3
# Brothers in Arms: D-Day PSP - Stage 01 inventory / text-resource reconnaissance
# Safe by design:
#   - Never modifies the original ISO/CSO or extracted game files.
#   - Writes only under <root>\analysis\stage01_inventory and, if needed,
#     extracts an ISO/CSO to <root>\extracted using 7-Zip.

from __future__ import annotations

import argparse
import csv
import hashlib
import os
import re
import shutil
import struct
import subprocess
import sys
import time
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

DEFAULT_ROOT = Path(r"PROJECT_ROOT")
STAGE_NAME = "stage01_inventory"

KEY_NAMES = {
    "EBOOT.BIN", "BOOT.BIN", "BIAOFF.PRX", "BIAON.PRX", "PARAM.SFO",
    "UMD_DATA.BIN"
}

TEXTISH_EXTS = {
    ".txt", ".ini", ".cfg", ".csv", ".tsv", ".xml", ".json", ".lua",
    ".scr", ".str", ".lng", ".lang", ".loc", ".res", ".dat", ".bin",
    ".pak", ".arc", ".big", ".db", ".tbl", ".msg", ".sub", ".prx", ".elf"
}

SKIP_MEDIA_EXTS = {
    ".pmf", ".at3", ".wav", ".mp3", ".ogg", ".aac", ".m4a",
    ".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tga", ".dds", ".gim",
    ".vag", ".adx", ".mp4", ".avi"
}

LANG_HINTS = (
    "english", "french", "german", "italian", "spanish",
    "eng", "fre", "fra", "ger", "deu", "ita", "spa",
    "local", "lang", "text", "dialog", "subtitle", "caption",
    "string", "message", "menu", "ui", "mission", "brief"
)

KEYWORDS = (
    "mission", "objective", "checkpoint", "loading", "save", "profile",
    "brothers", "squad", "fire", "move", "attack", "enemy", "weapon",
    "press", "button", "difficulty", "campaign", "skirmish", "settings",
    "options", "continue", "new game", "quit", "subtitle", "captions",
    "english", "french", "german", "italian", "spanish"
)

ASCII_RE = re.compile(rb"[\x20-\x7e]{4,}")
UTF16LE_RE = re.compile(rb"(?:[\x20-\x7e]\x00){4,}")

def log(msg: str):
    print(msg, flush=True)

def sha1_file(path: Path, chunk=1024 * 1024) -> str:
    h = hashlib.sha1()
    with path.open("rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()

def find_7z() -> str | None:
    candidates = [
        shutil.which("7z"),
        shutil.which("7z.exe"),
        r"LOCAL_PATH Files\7-Zip\7z.exe",
        r"LOCAL_PATH Files (x86)\7-Zip\7z.exe",
    ]
    for c in candidates:
        if c and Path(c).exists():
            return str(c)
    return None

def find_existing_game_root(root: Path) -> Path | None:
    # root itself might be an extracted PSP disc
    if (root / "PSP_GAME").is_dir():
        return root
    # common extraction folder
    for p in [root / "extracted", root / "iso_extracted", root / "game"]:
        if (p / "PSP_GAME").is_dir():
            return p
    # shallow recursive search first
    try:
        for p in root.glob("*/PSP_GAME"):
            if p.is_dir():
                return p.parent
    except OSError:
        pass
    return None

def extract_if_needed(root: Path, no_extract: bool) -> tuple[Path, str]:
    game_root = find_existing_game_root(root)
    if game_root:
        return game_root, f"Using existing extracted game: {game_root}"

    images = sorted(
        [p for p in root.iterdir() if p.is_file() and p.suffix.lower() in {".iso", ".cso"}],
        key=lambda p: p.stat().st_size,
        reverse=True,
    )
    if not images:
        return root, "No ISO/CSO and no PSP_GAME directory found; scanning PROJECT_ROOT as-is."

    image = images[0]
    if no_extract:
        return root, f"Found image {image.name}, but --no-extract was specified."

    seven = find_7z()
    if not seven:
        return root, (
            f"Found image {image.name}, but 7-Zip was not found. "
            "Install 7-Zip or manually extract the image to PROJECT_ROOT\\extracted."
        )

    dest = root / "extracted"
    dest.mkdir(parents=True, exist_ok=True)
    log(f"[extract] {image}")
    log(f"       -> {dest}")
    cmd = [seven, "x", str(image), f"-o{dest}", "-y"]
    p = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if p.returncode != 0:
        return root, f"7-Zip extraction failed (exit {p.returncode}). See extraction_7z.log."
    (root / "analysis").mkdir(exist_ok=True)
    (root / "analysis" / "extraction_7z.log").write_text(p.stdout, encoding="utf-8", errors="replace")
    found = find_existing_game_root(root)
    if found:
        return found, f"Extracted {image.name} with 7-Zip to {found}"
    return dest, f"7-Zip completed, but PSP_GAME was not detected under {dest}"

def magic_type(path: Path) -> str:
    try:
        with path.open("rb") as f:
            head = f.read(0x9000)
    except OSError:
        return "unreadable"
    if head.startswith(b"\x7fELF"):
        return "ELF"
    if head.startswith(b"~PSP"):
        return "PSP encrypted executable"
    if head.startswith(b"\x00PBP"):
        return "PBP"
    if head.startswith(b"\x00PSF"):
        return "PARAM.SFO/PSF"
    if head.startswith(b"RIFF"):
        return "RIFF"
    if head.startswith(b"OggS"):
        return "Ogg"
    if head.startswith(b"PK\x03\x04"):
        return "ZIP"
    if head.startswith(b"\x89PNG"):
        return "PNG"
    if head.startswith(b"DDS "):
        return "DDS"
    if len(head) > 0x8006 and head[0x8001:0x8006] == b"CD001":
        return "ISO9660"
    return ""

def parse_sfo(path: Path) -> dict[str, str]:
    # Standard PARAM.SFO parser.
    try:
        data = path.read_bytes()
        if len(data) < 20 or data[:4] != b"\x00PSF":
            return {}
        _, version, key_off, data_off, count = struct.unpack_from("<4sIIII", data, 0)
        out = {}
        ent = 20
        for i in range(count):
            ko, fmt, ln, maxln, do = struct.unpack_from("<HHIII", data, ent + i * 16)
            ks = key_off + ko
            ke = data.find(b"\0", ks)
            if ke < 0:
                continue
            key = data[ks:ke].decode("utf-8", "replace")
            raw = data[data_off + do:data_off + do + ln]
            if fmt in (0x0204, 0x0004):
                val = raw.rstrip(b"\0").decode("utf-8", "replace")
            elif fmt == 0x0404 and len(raw) >= 4:
                val = str(struct.unpack_from("<I", raw, 0)[0])
            else:
                val = raw.rstrip(b"\0").decode("utf-8", "replace")
            out[key] = val
        return out
    except Exception:
        return {}

def iter_files(base: Path, output_dir: Path):
    out_abs = output_dir.resolve()
    for p in base.rglob("*"):
        if not p.is_file():
            continue
        try:
            rp = p.resolve()
        except OSError:
            rp = p
        # avoid scanning our own generated reports
        try:
            if out_abs in rp.parents:
                continue
        except Exception:
            pass
        yield p

def readable_ascii_candidate(s: str) -> bool:
    if len(s) < 4:
        return False
    letters = sum(ch.isalpha() for ch in s)
    printable = sum(ch.isprintable() for ch in s)
    if printable < len(s) * 0.98:
        return False
    # keep short UI labels and longer human-readable strings
    words = re.findall(r"[A-Za-z]{2,}", s)
    if not words:
        return False
    if len(s) <= 40:
        return letters >= 3
    return letters / max(1, len(s)) >= 0.35 and len(words) >= 2

def should_scan_strings(path: Path, size: int, game_root: Path) -> bool:
    ext = path.suffix.lower()
    name_low = path.name.lower()
    whole_low = str(path).lower()
    if path.name.upper() in KEY_NAMES:
        return True
    if any(h in whole_low for h in LANG_HINTS):
        return True
    if ext in SKIP_MEDIA_EXTS:
        return False
    if ext in TEXTISH_EXTS:
        return True
    # Unknown files can be containers; scan up to 192 MiB.
    return size <= 192 * 1024 * 1024

def scan_strings(path: Path, rel: str, ascii_writer, utf16_writer, hit_writer) -> tuple[int, int, int]:
    try:
        data = path.read_bytes()
    except Exception:
        return 0, 0, 0

    ascii_count = 0
    utf_count = 0
    keyword_hits = Counter()
    key_lower = [(k, k.encode("ascii")) for k in KEYWORDS]

    # ASCII candidates
    for idx, m in enumerate(ASCII_RE.finditer(data)):
        if idx >= 100000:
            break
        raw = m.group(0)
        if len(raw) > 4096:
            raw = raw[:4096]
        try:
            s = raw.decode("ascii", "replace")
        except Exception:
            continue
        if readable_ascii_candidate(s):
            ascii_writer.writerow([rel, f"0x{m.start():08X}", len(raw), s.replace("\r", "\\r").replace("\n", "\\n")])
            ascii_count += 1
            sl = s.lower()
            for k in KEYWORDS:
                if k in sl:
                    keyword_hits[k] += 1

    # UTF-16LE ASCII-range candidates
    for idx, m in enumerate(UTF16LE_RE.finditer(data)):
        if idx >= 50000:
            break
        raw = m.group(0)
        if len(raw) > 8192:
            raw = raw[:8192]
        try:
            s = raw.decode("utf-16le", "replace")
        except Exception:
            continue
        if readable_ascii_candidate(s):
            utf16_writer.writerow([rel, f"0x{m.start():08X}", len(raw), s.replace("\r", "\\r").replace("\n", "\\n")])
            utf_count += 1
            sl = s.lower()
            for k in KEYWORDS:
                if k in sl:
                    keyword_hits[k] += 1

    for k, n in keyword_hits.items():
        hit_writer.writerow([rel, k, n])

    return ascii_count, utf_count, sum(keyword_hits.values())

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(DEFAULT_ROOT), help=r'Project root (default: PROJECT_ROOT)')
    ap.add_argument("--no-extract", action="store_true", help="Do not auto-extract ISO/CSO with 7-Zip.")
    args = ap.parse_args()

    root = Path(args.root)
    if not root.exists():
        print(f"ERROR: project root does not exist: {root}")
        return 2

    analysis = root / "analysis" / STAGE_NAME
    analysis.mkdir(parents=True, exist_ok=True)

    game_root, extraction_note = extract_if_needed(root, args.no_extract)
    log(extraction_note)
    log(f"[scan] game root: {game_root}")
    log(f"[out ] {analysis}")

    files = list(iter_files(game_root, analysis))
    ext_count = Counter()
    ext_bytes = Counter()

    inv_path = analysis / "files.tsv"
    ascii_path = analysis / "ascii_strings.tsv"
    utf16_path = analysis / "utf16le_strings.tsv"
    hits_path = analysis / "keyword_hits.tsv"
    key_path = analysis / "key_files.tsv"
    ext_path = analysis / "extensions.tsv"
    report_path = analysis / "report.txt"

    key_rows = []
    sfo_info = {}
    total_ascii = total_utf = total_hits = 0

    with inv_path.open("w", encoding="utf-8-sig", newline="") as fi, \
         ascii_path.open("w", encoding="utf-8-sig", newline="") as fa, \
         utf16_path.open("w", encoding="utf-8-sig", newline="") as fu, \
         hits_path.open("w", encoding="utf-8-sig", newline="") as fh:
        inv = csv.writer(fi, delimiter="\t")
        aw = csv.writer(fa, delimiter="\t")
        uw = csv.writer(fu, delimiter="\t")
        hw = csv.writer(fh, delimiter="\t")
        inv.writerow(["path", "size", "ext", "magic", "string_scanned"])
        aw.writerow(["path", "offset", "byte_len", "text"])
        uw.writerow(["path", "offset", "byte_len", "text"])
        hw.writerow(["path", "keyword", "count"])

        for i, p in enumerate(files, 1):
            try:
                rel = str(p.relative_to(game_root))
            except Exception:
                rel = str(p)
            try:
                size = p.stat().st_size
            except OSError:
                continue
            ext = p.suffix.lower() or "<none>"
            ext_count[ext] += 1
            ext_bytes[ext] += size
            magic = magic_type(p)
            scan = should_scan_strings(p, size, game_root)
            inv.writerow([rel, size, ext, magic, "yes" if scan else "no"])

            if p.name.upper() in KEY_NAMES or p.name.upper() in {"BIAOFF.PRX", "BIAON.PRX"}:
                digest = sha1_file(p) if size <= 128 * 1024 * 1024 else ""
                key_rows.append((rel, size, magic, digest))
                if p.name.upper() == "PARAM.SFO":
                    sfo_info = parse_sfo(p)

            if scan:
                a, u, h = scan_strings(p, rel, aw, uw, hw)
                total_ascii += a
                total_utf += u
                total_hits += h

            if i % 100 == 0 or i == len(files):
                log(f"  {i}/{len(files)} files")

    with ext_path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["ext", "file_count", "total_bytes"])
        for ext in sorted(ext_count, key=lambda x: (-ext_bytes[x], x)):
            w.writerow([ext, ext_count[ext], ext_bytes[ext]])

    with key_path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["path", "size", "magic", "sha1"])
        w.writerows(key_rows)

    # Rank likely localization/resource files.
    scores = []
    hit_per_file = Counter()
    if hits_path.exists():
        with hits_path.open("r", encoding="utf-8-sig", newline="") as f:
            r = csv.DictReader(f, delimiter="\t")
            for row in r:
                try:
                    hit_per_file[row["path"]] += int(row["count"])
                except Exception:
                    pass
    for p in files:
        try:
            rel = str(p.relative_to(game_root))
            size = p.stat().st_size
        except Exception:
            continue
        low = rel.lower()
        score = hit_per_file[rel] * 10
        score += sum(6 for h in LANG_HINTS if h in low)
        if p.name.upper() in {"BIAOFF.PRX", "BIAON.PRX", "EBOOT.BIN", "BOOT.BIN"}:
            score += 25
        if p.suffix.lower() in TEXTISH_EXTS:
            score += 3
        if score:
            scores.append((score, rel, size, hit_per_file[rel]))
    scores.sort(reverse=True)

    cand_path = analysis / "resource_candidates.tsv"
    with cand_path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["score", "path", "size", "keyword_hits"])
        w.writerows(scores[:500])

    lines = []
    lines.append("Brothers in Arms: D-Day PSP - Stage 01 report")
    lines.append("=" * 72)
    lines.append(f"Project root : {root}")
    lines.append(f"Game root    : {game_root}")
    lines.append(f"Extraction   : {extraction_note}")
    lines.append(f"Files        : {len(files)}")
    lines.append(f"ASCII strings: {total_ascii}")
    lines.append(f"UTF16 strings: {total_utf}")
    lines.append(f"Keyword hits : {total_hits}")
    lines.append("")
    if sfo_info:
        lines.append("PARAM.SFO")
        lines.append("-" * 72)
        for k in sorted(sfo_info):
            lines.append(f"{k:16s}: {sfo_info[k]}")
        lines.append("")
    lines.append("Key executables/files")
    lines.append("-" * 72)
    for rel, size, magic, digest in key_rows:
        lines.append(f"{size:10d}  {magic:24s}  {rel}")
    lines.append("")
    lines.append("Top resource candidates")
    lines.append("-" * 72)
    for score, rel, size, hits in scores[:40]:
        lines.append(f"{score:5d}  hits={hits:4d}  {size:10d}  {rel}")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Build upload bundle: reports + key executables/resources small enough to inspect.
    bundle = analysis / "bia_stage01_upload.zip"
    with zipfile.ZipFile(bundle, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for rp in [report_path, inv_path, ext_path, key_path, cand_path, hits_path, ascii_path, utf16_path]:
            if rp.exists():
                z.write(rp, rp.name)
        # Include selected key binaries up to 64 MiB each so the next stage can inspect them directly.
        for p in files:
            if p.name.upper() in KEY_NAMES or p.name.upper() in {"BIAOFF.PRX", "BIAON.PRX"}:
                try:
                    if p.stat().st_size <= 64 * 1024 * 1024:
                        rel = str(p.relative_to(game_root)).replace("\\", "/")
                        z.write(p, "key_files/" + rel)
                except Exception:
                    pass

    log("")
    log("=" * 72)
    log("Stage 01 complete")
    log(f"Report : {report_path}")
    log(f"Upload : {bundle}")
    log("=" * 72)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
