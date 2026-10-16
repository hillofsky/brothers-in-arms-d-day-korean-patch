#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import os
import re
import shutil
import struct
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

DEFAULT_ROOT = Path(r"PROJECT_ROOT")
STAGE = "stage02_localization_font"

TEXT_EXTS = {".int", ".fra", ".deu", ".ita", ".esp", ".ini"}
LANG_EXT_TO_CODE = {
    ".int": "INT",
    ".fra": "FRA",
    ".deu": "DEU",
    ".ita": "ITA",
    ".esp": "ESP",
}

FONT_NEEDLES = [
    b"WargameFont",
    b"WargameFont2",
    b"t_gbxfonts",
    b"Magma Font",
    b"UnicodeStringConst",
    b"DrawText",
    b"TextSize",
    b"GetConsoleFont",
    b"UFont",
    b"FontArrayNames",
    b"AB18",
    b"TMR18",
    b".mft",
    b"libfont",
]

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
    candidates = [
        root,
        root / "extracted",
        root / "iso_extracted",
        root / "game",
    ]
    for c in candidates:
        if (c / "PSP_GAME").is_dir():
            return c
    for p in root.glob("*/PSP_GAME"):
        if p.is_dir():
            return p.parent
    raise SystemExit(
        "Could not find an extracted PSP_GAME tree. "
        r"Expected PROJECT_ROOT\extracted\PSP_GAME or similar."
    )

def detect_encoding(data: bytes) -> tuple[str, str]:
    if data.startswith(b"\xff\xfe"):
        return "utf-16le-bom", data.decode("utf-16le", "replace")
    if data.startswith(b"\xfe\xff"):
        return "utf-16be-bom", data.decode("utf-16be", "replace")
    if data.startswith(b"\xef\xbb\xbf"):
        return "utf-8-bom", data.decode("utf-8-sig", "replace")

    # UTF-16 without BOM: localization files are mostly text, so NUL density is useful.
    sample = data[:65536]
    if sample:
        odd_nuls = sum(1 for i in range(1, len(sample), 2) if sample[i] == 0)
        even_nuls = sum(1 for i in range(0, len(sample), 2) if sample[i] == 0)
        slots = max(1, len(sample) // 2)
        if odd_nuls / slots > 0.35:
            return "utf-16le-no-bom", data.decode("utf-16le", "replace")
        if even_nuls / slots > 0.35:
            return "utf-16be-no-bom", data.decode("utf-16be", "replace")

    try:
        return "utf-8", data.decode("utf-8")
    except UnicodeDecodeError:
        pass

    # Western retail localization files are commonly Windows-1252.
    return "cp1252", data.decode("cp1252", "replace")

def safe_rel(p: Path, base: Path) -> str:
    return str(p.relative_to(base)).replace("/", "\\")

def classify_language(path: Path, system_dir: Path) -> str:
    ext = path.suffix.lower()
    if ext in LANG_EXT_TO_CODE:
        return LANG_EXT_TO_CODE[ext]
    parts = [x.upper() for x in path.relative_to(system_dir).parts]
    for code in ("FRA", "DEU", "ITA", "ESP", "INT"):
        if code in parts:
            return code
    return ""

def iter_localization_files(system_dir: Path):
    for p in system_dir.rglob("*"):
        if p.is_file() and p.suffix.lower() in TEXT_EXTS:
            yield p

def parse_ini_like(text: str):
    section = ""
    for lineno, rawline in enumerate(text.splitlines(), 1):
        line = rawline.strip()
        if not line or line.startswith(";") or line.startswith("#"):
            continue
        if line.startswith("[") and "]" in line:
            section = line[1:line.find("]")].strip()
            continue
        if "=" not in rawline:
            continue
        key, value = rawline.split("=", 1)
        key = key.strip()
        value = value.strip()
        yield lineno, section, key, value

def printable_context(data: bytes, start: int, end: int) -> str:
    chunk = data[max(0, start):min(len(data), end)]
    # Binary refs are mostly ASCII; render controls compactly.
    s = "".join(chr(b) if 32 <= b <= 126 else "." for b in chunk)
    return s

def scan_binary_refs(path: Path, rel: str):
    data = path.read_bytes()
    found = []
    seen = set()
    lower = data.lower()
    for needle in FONT_NEEDLES:
        n = needle.lower()
        pos = 0
        while True:
            off = lower.find(n, pos)
            if off < 0:
                break
            key = (off, needle.lower())
            if key not in seen:
                seen.add(key)
                found.append((
                    rel,
                    f"0x{off:08X}",
                    needle.decode("ascii", "replace"),
                    printable_context(data, off - 96, off + len(needle) + 160),
                ))
            pos = off + 1
    found.sort(key=lambda x: int(x[1], 16))
    return found

def xmlish_font_extract(path: Path) -> str:
    data = path.read_bytes()
    # MGM files visibly contain XML-like textual descriptors.
    text = data.decode("latin1", "replace")
    blocks = []
    for tag_start, tag_end in [
        ("<FONTS>", "</FONTS>"),
        ("<FONTFAMILIES>", "</FONTFAMILIES>"),
    ]:
        pos = 0
        while True:
            a = text.find(tag_start, pos)
            if a < 0:
                break
            b = text.find(tag_end, a)
            if b < 0:
                b = min(len(text), a + 8192)
            else:
                b += len(tag_end)
            block = text[a:b]
            # Replace nonprintable binary bytes while retaining line structure.
            cleaned = "".join(ch if ch in "\r\n\t" or 32 <= ord(ch) <= 126 else "." for ch in block)
            blocks.append(f"--- {path.name} @ 0x{a:08X} ---\n{cleaned}\n")
            pos = b
    return "\n".join(blocks)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(DEFAULT_ROOT))
    args = ap.parse_args()

    root = Path(args.root)
    game_root = find_game_root(root)
    system_dir = game_root / "PSP_GAME" / "USRDIR" / "SYSTEM"
    analysis = root / "analysis" / STAGE
    log_dir = root / "log"
    analysis.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 78)
    print("Brothers in Arms: D-Day PSP - Stage 02 localization/font collection")
    print("=" * 78)
    print(f"Root      : {root}")
    print(f"Game root : {game_root}")
    print(f"System    : {system_dir}")
    print(f"Analysis  : {analysis}")

    if not system_dir.is_dir():
        raise SystemExit(f"Missing SYSTEM directory: {system_dir}")

    loc_files = sorted(iter_localization_files(system_dir))
    mgm_files = sorted(system_dir.rglob("*.MGM")) + sorted(system_dir.rglob("*.mgm"))
    mgm_files = sorted(set(mgm_files))

    explicit = [
        game_root / "PSP_GAME" / "SYSDIR" / "BOOT.BIN",
        system_dir / "BIAOFF.PRX",
        system_dir / "BIAON.PRX",
        system_dir / "MANIFEST.INI",
        system_dir / "MISSIONLIN.INI",
        system_dir / "STORYLINE.INI",
        system_dir / "PSP_MODULES" / "LIBFONT.PRX",
        game_root / "PSP_GAME" / "PARAM.SFO",
    ]

    # Small PSP modules can matter when determining whether Sony's font library is used.
    module_prx = sorted((system_dir / "PSP_MODULES").glob("*.PRX")) if (system_dir / "PSP_MODULES").is_dir() else []
    module_prx += sorted((system_dir / "PSP_MODULES").glob("*.prx")) if (system_dir / "PSP_MODULES").is_dir() else []

    selected = []
    seen = set()
    for p in list(loc_files) + list(mgm_files) + explicit + module_prx:
        if p.exists() and p.is_file():
            rp = p.resolve()
            if rp not in seen:
                seen.add(rp)
                selected.append(p)

    # 1) Localization inventory and parsed key/value catalog.
    inv_path = analysis / "localization_inventory.tsv"
    entries_path = analysis / "localization_entries.tsv"
    nonascii_path = analysis / "encoding_nonascii_samples.tsv"

    file_stats = []
    entries = []
    nonascii_samples = []

    for p in loc_files:
        raw = p.read_bytes()
        enc, text = detect_encoding(raw)
        rel = safe_rel(p, game_root)
        parsed = list(parse_ini_like(text))
        sections = {sec for _, sec, _, _ in parsed}
        quoted = sum(1 for _, _, _, v in parsed if len(v) >= 2 and v[0] == '"' and v[-1] == '"')
        high = sum(1 for b in raw if b >= 0x80)
        file_stats.append([
            rel, classify_language(p, system_dir), len(raw), enc,
            len(sections), len(parsed), quoted, high, sha1_file(p)
        ])
        for lineno, sec, key, value in parsed:
            entries.append([rel, classify_language(p, system_dir), lineno, sec, key, value])
        if high:
            # Save compact byte windows around the first few high-byte regions.
            spots = [i for i, b in enumerate(raw) if b >= 0x80][:12]
            used = []
            for off in spots:
                if any(abs(off-u) < 16 for u in used):
                    continue
                used.append(off)
                chunk = raw[max(0, off-24):min(len(raw), off+48)]
                nonascii_samples.append([
                    rel, enc, f"0x{off:08X}",
                    chunk.hex(" "),
                    chunk.decode("cp1252", "replace").replace("\r","\\r").replace("\n","\\n")
                ])
                if len(used) >= 5:
                    break

    with inv_path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["path","language","bytes","encoding_guess","sections","assignments","quoted_values","high_bytes","sha1"])
        w.writerows(file_stats)

    with entries_path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["path","language","line","section","key","value"])
        w.writerows(entries)

    with nonascii_path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["path","encoding_guess","offset","bytes_hex","cp1252_preview"])
        w.writerows(nonascii_samples)

    # 2) Compare base .INT files to FRA/DEU/ITA/ESP siblings by stem.
    base_by_stem = {}
    trans_by_stem = defaultdict(dict)
    for p in loc_files:
        stem = p.stem.upper()
        ext = p.suffix.lower()
        if ext == ".int" and p.parent == system_dir:
            base_by_stem[stem] = p
        elif ext in (".fra",".deu",".ita",".esp"):
            trans_by_stem[stem][LANG_EXT_TO_CODE[ext]] = p

    matrix_path = analysis / "localization_language_matrix.tsv"
    with matrix_path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["stem","INT","FRA","DEU","ITA","ESP"])
        stems = sorted(set(base_by_stem) | set(trans_by_stem))
        for stem in stems:
            w.writerow([
                stem,
                safe_rel(base_by_stem[stem], game_root) if stem in base_by_stem else "",
                safe_rel(trans_by_stem[stem].get("FRA"), game_root) if trans_by_stem[stem].get("FRA") else "",
                safe_rel(trans_by_stem[stem].get("DEU"), game_root) if trans_by_stem[stem].get("DEU") else "",
                safe_rel(trans_by_stem[stem].get("ITA"), game_root) if trans_by_stem[stem].get("ITA") else "",
                safe_rel(trans_by_stem[stem].get("ESP"), game_root) if trans_by_stem[stem].get("ESP") else "",
            ])

    # 3) MGM font blocks.
    font_blocks_path = analysis / "magma_font_blocks.txt"
    font_blocks = []
    for p in mgm_files:
        blocks = xmlish_font_extract(p)
        if blocks:
            font_blocks.append(blocks)
    font_blocks_path.write_text("\n".join(font_blocks), encoding="utf-8")

    # 4) Search executables/modules for font and Unicode references.
    binary_candidates = [
        game_root / "PSP_GAME" / "SYSDIR" / "BOOT.BIN",
        system_dir / "BIAOFF.PRX",
        system_dir / "BIAON.PRX",
    ] + module_prx

    refs = []
    for p in binary_candidates:
        if p.exists() and p.is_file():
            refs.extend(scan_binary_refs(p, safe_rel(p, game_root)))

    refs_path = analysis / "binary_font_unicode_refs.tsv"
    with refs_path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["path","offset","needle","context"])
        w.writerows(refs)

    # 5) Manifest evidence about source font package.
    manifest_refs_path = analysis / "manifest_font_refs.txt"
    manifest = system_dir / "MANIFEST.INI"
    manifest_lines = []
    if manifest.exists():
        enc, txt = detect_encoding(manifest.read_bytes())
        for i, line in enumerate(txt.splitlines(), 1):
            if re.search(r"font|mft|gbxfonts|localize|magma", line, re.I):
                manifest_lines.append(f"{i}: {line}")
    manifest_refs_path.write_text("\n".join(manifest_lines) + "\n", encoding="utf-8")

    # 6) Selected file manifest.
    selected_manifest = analysis / "selected_files.tsv"
    with selected_manifest.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["path","bytes","sha1"])
        for p in selected:
            w.writerow([safe_rel(p, game_root), p.stat().st_size, sha1_file(p)])

    # 7) Human-readable summary.
    enc_counts = Counter(row[3] for row in file_stats)
    lang_counts = Counter(row[1] for row in file_stats)
    report = []
    report.append("Brothers in Arms: D-Day PSP - Stage 02 report")
    report.append("=" * 78)
    report.append(f"Game root: {game_root}")
    report.append(f"Localization/config files: {len(loc_files)}")
    report.append(f"Parsed assignments: {len(entries)}")
    report.append(f"MGM files: {len(mgm_files)}")
    report.append(f"Selected raw files for upload: {len(selected)}")
    report.append("")
    report.append("Language file counts:")
    for k,v in sorted(lang_counts.items()):
        report.append(f"  {k or '(config)'}: {v}")
    report.append("")
    report.append("Encoding guesses:")
    for k,v in sorted(enc_counts.items()):
        report.append(f"  {k}: {v}")
    report.append("")
    report.append("Key font evidence:")
    report.append(r"  Magma UI references \Fonts\AB18.mft and \Fonts\TMR18.mft.")
    report.append(r"  Unreal GUI localization references t_gbxfonts.WargameFont / WargameFont2.")
    report.append(r"  MANIFEST.INI references source Texture\t_gbxfonts.utx.")
    report.append("  The source .mft/.utx files are not expected to exist as standalone retail-disc files;")
    report.append("  Stage 02 bundles MGM and executable/module data to determine their compiled representation.")
    report.append("")
    report.append("Important raw files included:")
    for p in selected:
        rel = safe_rel(p, game_root)
        if p.name.upper() in {"BOOT.BIN","BIAOFF.PRX","BIAON.PRX","LIBFONT.PRX","BIA_MENU.MGM","BIA_INGAME.MGM","LOCALIZE.INT","NEWLOCALIZE.INT","GUI.INT"}:
            report.append(f"  {rel} ({p.stat().st_size} bytes)")
    report_path = analysis / "report.txt"
    report_path.write_text("\n".join(report) + "\n", encoding="utf-8")

    # 8) Upload ZIP in PROJECT_ROOT\log, as requested.
    zip_path = log_dir / "bia_stage02_upload.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for rp in [
            report_path, inv_path, entries_path, nonascii_path, matrix_path,
            font_blocks_path, refs_path, manifest_refs_path, selected_manifest
        ]:
            z.write(rp, "analysis/" + rp.name)

        for p in selected:
            rel = safe_rel(p, game_root).replace("\\", "/")
            z.write(p, "raw/" + rel)

    print("")
    print(f"Localization files : {len(loc_files)}")
    print(f"Parsed assignments : {len(entries)}")
    print(f"MGM files          : {len(mgm_files)}")
    print(f"Binary refs         : {len(refs)}")
    print(f"Selected raw files : {len(selected)}")
    print("")
    print("=" * 78)
    print("Stage 02 complete")
    print(f"Upload ZIP: {zip_path}")
    print("=" * 78)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
