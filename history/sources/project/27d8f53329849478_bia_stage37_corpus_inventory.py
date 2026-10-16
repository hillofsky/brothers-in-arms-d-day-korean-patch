#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import sys
import traceback
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(r"PROJECT_ROOT")
OUT = ROOT / "analysis" / "stage37_corpus_inventory"
LOG_DIR = ROOT / "log"

SUCCESS_ZIP = LOG_DIR / "bia_stage37_upload.zip"
FAIL_ZIP = LOG_DIR / "fail_bia_stage37_upload.zip"

HANGUL_MIN = 0xAC00
HANGUL_MAX = 0xD7A3

# Proven Stage36 font architecture.
MDI_SEQ_BASE = 0x08E2D020
MDI_STREAM_SIZE = 0x78000
STREAM23_INDEX = 23
STREAM23_RAM_BASE = MDI_SEQ_BASE + STREAM23_INDEX * MDI_STREAM_SIZE

OLD_GLYPH_COUNT = 151
GLYPH_REC_SIZE = 24
UNICODE_PAGE_SIZE = 512

ATLAS_W = 512
ATLAS_H = 512
RENDER_PAGE_W = 128
LOGICAL_H = 256
CELL_W = 17
CELL_H = 16

# Keep the five Stage36-proven positions/indices untouched in the next build.
PROVEN = [
    ("한", 0xD55C, 151, 128, 256),
    ("글", 0xAE00, 152, 256, 256),
    ("테", 0xD14C, 153, 384, 256),
    ("스", 0xC2A4, 154, 128, 384),
    ("트", 0xD2B8, 155, 384, 384),
]

TEXT_EXTS = {
    ".int", ".txt", ".tsv", ".csv", ".json", ".jsonl",
    ".xml", ".yaml", ".yml", ".po", ".pot", ".ini", ".cfg",
}
SCRIPT_EXTS = {".py"}

TRANSLATION_HINTS = (
    "translat", "korean", "kor", "localiz", "dialog",
    "story", "menu", "mission", "string", "subtitle",
    "text", "patch", "ui",
)

EXCLUDED_DIR_NAMES = {
    "log", "logs", "analysis", "generated_macros",
    "memstick", "ppsspp", "__pycache__", ".git",
}

STAGE_TOOL_RE = re.compile(r"bia_stage\d+[a-z]?_tools", re.I)
STAGE_FILE_RE = re.compile(
    r"^(?:fail_)?bia_stage\d+|^stage\d+_", re.I
)


def log(msg: str):
    print(msg, flush=True)


def safe_rel(p: Path) -> str:
    try:
        return str(p.relative_to(ROOT))
    except Exception:
        return str(p)


def is_hangul_syllable(ch: str) -> bool:
    o = ord(ch)
    return HANGUL_MIN <= o <= HANGUL_MAX


def decode_best(data: bytes):
    """
    Decode Korean text robustly without external packages.

    Returns (text, encoding, score).  Score strongly favors Hangul, then
    printable text.  UTF-16 is tried early when NUL placement suggests it.
    """
    candidates = []

    if data.startswith(b"\xff\xfe"):
        order = ["utf-16le", "utf-8-sig", "cp949", "utf-16be"]
    elif data.startswith(b"\xfe\xff"):
        order = ["utf-16be", "utf-8-sig", "cp949", "utf-16le"]
    else:
        sample = data[:8192]
        even_null = sample[0::2].count(0)
        odd_null = sample[1::2].count(0)
        half = max(1, len(sample) // 2)
        if odd_null / half > 0.20:
            order = ["utf-16le", "utf-8-sig", "cp949", "utf-16be"]
        elif even_null / half > 0.20:
            order = ["utf-16be", "utf-8-sig", "cp949", "utf-16le"]
        else:
            order = ["utf-8-sig", "cp949", "utf-16le", "utf-16be"]

    for enc in order:
        try:
            text = data.decode(enc)
        except Exception:
            continue

        hangul = sum(is_hangul_syllable(ch) for ch in text)
        printable = sum(
            ch.isprintable() or ch in "\r\n\t"
            for ch in text
        )
        control = len(text) - printable
        score = hangul * 10000 + printable - control * 5
        candidates.append((score, hangul, text, enc))

    if not candidates:
        return "", None, -1

    candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
    score, hangul, text, enc = candidates[0]
    return text, enc, score


def path_excluded(path: Path) -> tuple[bool, str]:
    rel = safe_rel(path)
    parts = [x.lower() for x in path.parts]

    for part in parts:
        if part in EXCLUDED_DIR_NAMES:
            return True, f"excluded directory: {part}"
        if STAGE_TOOL_RE.search(part):
            return True, f"stage tool directory: {part}"

    name = path.name.lower()
    if STAGE_FILE_RE.search(name):
        return True, "stage diagnostic/tool file"
    if name in {"readme.txt", "readme.md", "failure.txt"}:
        return True, "documentation/diagnostic file"

    return False, ""


def source_class(path: Path) -> tuple[bool, str]:
    ext = path.suffix.lower()
    low = str(path).lower()

    if ext == ".int":
        return True, "INT localization file"

    if ext in TEXT_EXTS:
        return True, f"text/table {ext}"

    if ext in SCRIPT_EXTS and any(k in low for k in TRANSLATION_HINTS):
        return True, "translation-like Python mapping"

    return False, "unsupported/non-translation source"


def extract_hangul(text: str):
    freq = Counter(ch for ch in text if is_hangul_syllable(ch))
    lines = []
    seen = set()

    for raw in text.splitlines():
        if not any(is_hangul_syllable(ch) for ch in raw):
            continue
        s = raw.strip()
        if not s or s in seen:
            continue
        seen.add(s)
        lines.append(s)

    return freq, lines


def scan_file(path: Path):
    try:
        data = path.read_bytes()
    except Exception as e:
        return {
            "path": safe_rel(path),
            "included": False,
            "reason": f"read error: {e}",
        }

    # Avoid accidentally slurping giant binaries with misleading extensions.
    if len(data) > 64 * 1024 * 1024:
        return {
            "path": safe_rel(path),
            "included": False,
            "reason": f"too large: {len(data)} bytes",
        }

    text, enc, score = decode_best(data)
    freq, lines = extract_hangul(text)

    return {
        "path": safe_rel(path),
        "absolute_path": str(path),
        "size": len(data),
        "encoding": enc,
        "hangul_total": sum(freq.values()),
        "hangul_unique": len(freq),
        "freq": freq,
        "lines": lines,
        "sha1": hashlib.sha1(data).hexdigest(),
    }


def scan_zip(path: Path):
    """
    Translation archives are optional secondary sources.  Stage tool/log ZIPs
    are excluded by path_excluded(), so this mainly catches translation packs.
    """
    results = []
    low = path.name.lower()
    if not any(k in low for k in TRANSLATION_HINTS):
        return results

    try:
        with zipfile.ZipFile(path, "r") as z:
            for zi in z.infolist():
                if zi.is_dir() or zi.file_size > 32 * 1024 * 1024:
                    continue

                member = Path(zi.filename)
                ext = member.suffix.lower()
                include, why = source_class(member)
                if not include:
                    continue

                try:
                    data = z.read(zi)
                except Exception:
                    continue

                text, enc, score = decode_best(data)
                freq, lines = extract_hangul(text)
                if not freq:
                    continue

                results.append({
                    "path": safe_rel(path) + "::" + zi.filename,
                    "absolute_path": str(path),
                    "size": len(data),
                    "encoding": enc,
                    "hangul_total": sum(freq.values()),
                    "hangul_unique": len(freq),
                    "freq": freq,
                    "lines": lines,
                    "sha1": hashlib.sha1(data).hexdigest(),
                    "source_type": "zip member",
                    "classification": why,
                })
    except Exception:
        pass

    return results


def find_sources():
    included = []
    candidates = []

    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue

        excluded, reason = path_excluded(path)
        if excluded:
            continue

        if path.suffix.lower() == ".zip":
            for r in scan_zip(path):
                included.append(r)
            continue

        include_kind, classification = source_class(path)
        if not include_kind:
            continue

        result = scan_file(path)
        result["classification"] = classification

        if result.get("hangul_total", 0) <= 0:
            continue

        # For normal text/INT/table sources, include directly.
        # Python mapping files are also included only when their path looks
        # translation-related (source_class already enforces that).
        result["source_type"] = "file"
        included.append(result)

    # Deterministic ordering.
    included.sort(key=lambda r: r["path"].lower())
    return included, candidates


def build_safe_slots():
    """
    Conservative 512x512 packing.

    The proven record uses half-pixel UV endpoints.  We therefore leave the
    last 16px row unused so V1 never goes beyond 512.0.

    Page 0 upper 256px is preserved for the original Latin atlas.
    """
    slots = []

    # Page 0: only lower half. y = 256..480 -> 15 rows.
    for row in range(15):
        y = 256 + row * CELL_H
        for col in range(7):
            x = col * CELL_W
            slots.append((0, x, y))

    # Pages 1..3: full safe height. y = 0..480 -> 31 rows.
    for page in range(1, 4):
        base_x = page * RENDER_PAGE_W
        for row in range(31):
            y = row * CELL_H
            for col in range(7):
                x = base_x + col * CELL_W
                slots.append((page, x, y))

    return slots


def align(v: int, a: int) -> int:
    return (v + a - 1) // a * a


def make_plan(freq: Counter):
    chars = sorted(freq.keys(), key=ord)

    # Keep Stage36-proven glyphs even if a particular translation corpus does
    # not happen to contain them.
    proven_chars = {ch for ch, *_ in PROVEN}
    all_chars = sorted(set(chars) | proven_chars, key=ord)

    reserved_by_char = {}
    reserved_positions = set()
    for ch, cp, gi, x, y in PROVEN:
        reserved_by_char[ch] = {
            "char": ch,
            "codepoint": cp,
            "glyph_index": gi,
            "atlas_x": x,
            "atlas_y": y,
            "renderer_page": x // RENDER_PAGE_W,
            "proven_stage36": True,
        }
        reserved_positions.add((x // RENDER_PAGE_W, x, y))

    slots = [
        s for s in build_safe_slots()
        if s not in reserved_positions
    ]

    layout = []
    next_index = 156

    # Proven entries first to preserve known indices.
    for ch, cp, gi, x, y in PROVEN:
        layout.append({
            "char": ch,
            "codepoint": f"U+{cp:04X}",
            "glyph_index": gi,
            "frequency": int(freq.get(ch, 0)),
            "atlas_x": x,
            "atlas_y": y,
            "renderer_page": x // RENDER_PAGE_W,
            "u0": (x + 0.5) / 128.0,
            "v0": (y + 0.5) / 256.0,
            "u1": (x + 17.5) / 128.0,
            "v1": (y + 16.5) / 256.0,
            "proven_stage36": True,
        })

    overflow = []
    for ch in chars:
        if ch in proven_chars:
            continue

        if not slots:
            overflow.append(ch)
            continue

        page, x, y = slots.pop(0)
        cp = ord(ch)
        layout.append({
            "char": ch,
            "codepoint": f"U+{cp:04X}",
            "glyph_index": next_index,
            "frequency": int(freq[ch]),
            "atlas_x": x,
            "atlas_y": y,
            "renderer_page": page,
            "u0": (x + 0.5) / 128.0,
            "v0": (y + 0.5) / 256.0,
            "u1": (x + 17.5) / 128.0,
            "v1": (y + 16.5) / 256.0,
            "proven_stage36": False,
        })
        next_index += 1

    # Actual high-byte pages required by the resulting Hangul glyph set.
    planned_chars = [x["char"] for x in layout]
    high_pages = sorted({ord(ch) >> 8 for ch in planned_chars})

    glyph_count_total = OLD_GLYPH_COUNT + len(planned_chars)

    # Final scalable build should move glyph records/pages out of stream19's
    # tiny hole and into known-zero stream23.
    glyph_array_off = 0x0000
    glyph_records_bytes = glyph_count_total * GLYPH_REC_SIZE
    unicode_pages_off = align(glyph_records_bytes, 0x100)
    unicode_pages_bytes = len(high_pages) * UNICODE_PAGE_SIZE
    aux_off = align(unicode_pages_off + unicode_pages_bytes, 0x100)
    # widths[4] + heights[4] + texptrs[4], generously reserve 0x100.
    used_bytes = aux_off + 0x100

    plan = {
        "corpus_unique_hangul": len(chars),
        "stage36_proven_extra": len(proven_chars - set(chars)),
        "planned_hangul_glyphs": len(planned_chars),
        "original_glyphs_preserved": OLD_GLYPH_COUNT,
        "glyph_count_total": glyph_count_total,
        "single_512_atlas": {
            "safe_slots_total": len(build_safe_slots()),
            "proven_slots_reserved": len(PROVEN),
            "available_after_proven": len(build_safe_slots()) - len(PROVEN),
            "fits": len(overflow) == 0,
            "overflow_count": len(overflow),
            "overflow_chars": "".join(overflow),
            "note":
                "Conservative packing leaves the final 16px row unused "
                "because proven UVs use +0.5 pixel endpoints.",
        },
        "storage_stream23": {
            "stream_index": STREAM23_INDEX,
            "runtime_base": f"0x{STREAM23_RAM_BASE:08X}",
            "capacity_bytes": MDI_STREAM_SIZE,
            "glyph_array_offset": f"0x{glyph_array_off:X}",
            "glyph_array_runtime":
                f"0x{STREAM23_RAM_BASE + glyph_array_off:08X}",
            "glyph_records_bytes": glyph_records_bytes,
            "unicode_pages_offset": f"0x{unicode_pages_off:X}",
            "unicode_pages_runtime":
                f"0x{STREAM23_RAM_BASE + unicode_pages_off:08X}",
            "unicode_page_count": len(high_pages),
            "unicode_pages_bytes": unicode_pages_bytes,
            "aux_arrays_offset": f"0x{aux_off:X}",
            "estimated_used_bytes": used_bytes,
            "fits": used_bytes <= MDI_STREAM_SIZE,
        },
        "required_high_byte_pages": [
            {
                "high_byte": f"0x{x:02X}",
                "range":
                    f"U+{x<<8:04X}..U+{(x<<8)|0xFF:04X}",
            }
            for x in high_pages
        ],
        "layout": layout,
    }
    return plan


def write_tsv(path: Path, header, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(header)
        w.writerows(rows)


def zip_outputs(zip_path: Path, files):
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for p in files:
            if p.exists() and p.is_file():
                z.write(p, p.name)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    log("[Stage37] Scanning PROJECT_ROOT for Korean translation corpus...")
    sources, candidates = find_sources()

    if not sources:
        raise RuntimeError(
            "No Hangul-containing translation sources were found under PROJECT_ROOT. "
            "Put translated .INT / TSV / CSV / JSON / text or translation mapping "
            "files under PROJECT_ROOT and rerun Stage37."
        )

    total_freq = Counter()
    source_lines = []
    merged_lines = []
    merged_seen = set()

    for r in sources:
        total_freq.update(r["freq"])

        source_lines.append([
            r["path"],
            r.get("classification", ""),
            r.get("source_type", ""),
            r.get("encoding", ""),
            r.get("size", 0),
            r.get("hangul_total", 0),
            r.get("hangul_unique", 0),
            r.get("sha1", ""),
        ])

        for line in r.get("lines", []):
            if line in merged_seen:
                continue
            merged_seen.add(line)
            merged_lines.append(line)

    if not total_freq:
        raise RuntimeError(
            "Sources were found, but no U+AC00..U+D7A3 Hangul syllables "
            "were extracted."
        )

    # High-byte report from ACTUAL corpus only.
    by_high_unique = defaultdict(set)
    by_high_freq = Counter()
    for ch, n in total_freq.items():
        hb = ord(ch) >> 8
        by_high_unique[hb].add(ch)
        by_high_freq[hb] += n

    plan = make_plan(total_freq)

    source_tsv = OUT / "stage37_sources.tsv"
    write_tsv(
        source_tsv,
        [
            "path", "classification", "source_type", "encoding",
            "size_bytes", "hangul_total", "hangul_unique", "sha1",
        ],
        source_lines,
    )

    glyph_tsv = OUT / "stage37_hangul_glyphs.tsv"
    glyph_rows = []
    for ch in sorted(total_freq, key=ord):
        cp = ord(ch)
        glyph_rows.append([
            ch,
            f"U+{cp:04X}",
            f"0x{cp>>8:02X}",
            f"0x{cp&0xFF:02X}",
            total_freq[ch],
        ])
    write_tsv(
        glyph_tsv,
        ["char", "codepoint", "high_byte", "low_byte", "frequency"],
        glyph_rows,
    )

    pages_tsv = OUT / "stage37_high_byte_pages.tsv"
    page_rows = []
    for hb in sorted(by_high_unique):
        chars = "".join(sorted(by_high_unique[hb], key=ord))
        page_rows.append([
            f"0x{hb:02X}",
            f"U+{hb<<8:04X}..U+{(hb<<8)|0xFF:04X}",
            len(by_high_unique[hb]),
            by_high_freq[hb],
            chars,
        ])
    write_tsv(
        pages_tsv,
        [
            "high_byte", "unicode_range",
            "unique_syllables", "total_occurrences", "characters",
        ],
        page_rows,
    )

    merged_path = OUT / "stage37_merged_korean_lines.txt"
    merged_path.write_text(
        "\n".join(merged_lines) + "\n",
        encoding="utf-8",
    )

    chars_path = OUT / "stage37_unique_hangul.txt"
    chars_path.write_text(
        "".join(sorted(total_freq, key=ord)) + "\n",
        encoding="utf-8",
    )

    plan_path = OUT / "stage37_atlas_plan.json"
    plan_path.write_text(
        json.dumps(plan, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    layout_tsv = OUT / "stage37_atlas_layout.tsv"
    layout_rows = []
    for x in plan["layout"]:
        layout_rows.append([
            x["char"], x["codepoint"], x["glyph_index"],
            x["frequency"], x["renderer_page"],
            x["atlas_x"], x["atlas_y"],
            f'{x["u0"]:.9f}', f'{x["v0"]:.9f}',
            f'{x["u1"]:.9f}', f'{x["v1"]:.9f}',
            int(bool(x["proven_stage36"])),
        ])
    write_tsv(
        layout_tsv,
        [
            "char", "codepoint", "glyph_index", "frequency",
            "renderer_page", "atlas_x", "atlas_y",
            "u0", "v0", "u1", "v1", "proven_stage36",
        ],
        layout_rows,
    )

    summary = {
        "stage": 37,
        "source_root": str(ROOT),
        "included_source_count": len(sources),
        "merged_unique_text_lines": len(merged_lines),
        "hangul_total_occurrences": sum(total_freq.values()),
        "hangul_unique_syllables": len(total_freq),
        "actual_high_byte_page_count": len(by_high_unique),
        "actual_high_bytes": [
            f"0x{x:02X}" for x in sorted(by_high_unique)
        ],
        "atlas_safe_capacity": plan["single_512_atlas"]["safe_slots_total"],
        "planned_hangul_glyphs_including_stage36_proven":
            plan["planned_hangul_glyphs"],
        "fits_single_512_atlas":
            plan["single_512_atlas"]["fits"],
        "overflow_count":
            plan["single_512_atlas"]["overflow_count"],
        "stream23_storage_fits":
            plan["storage_stream23"]["fits"],
        "next_step":
            (
                "Build Stage38 production atlas/font from this exact plan."
                if plan["single_512_atlas"]["fits"]
                else
                "Corpus exceeds conservative one-atlas capacity; design "
                "additional texture pages/atlas before Stage38."
            ),
    }

    summary_path = OUT / "stage37_summary.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    files = [
        summary_path,
        source_tsv,
        glyph_tsv,
        pages_tsv,
        merged_path,
        chars_path,
        plan_path,
        layout_tsv,
    ]
    zip_outputs(SUCCESS_ZIP, files)

    log("")
    log("[Stage37] COMPLETE")
    log(f"  sources              : {len(sources)}")
    log(f"  unique Hangul        : {len(total_freq)}")
    log(f"  Unicode high pages   : {len(by_high_unique)}")
    log(
        "  safe atlas capacity  : "
        f'{plan["single_512_atlas"]["safe_slots_total"]}'
    )
    log(
        "  planned glyphs       : "
        f'{plan["planned_hangul_glyphs"]}'
    )
    log(
        "  fits 512x512 atlas   : "
        f'{plan["single_512_atlas"]["fits"]}'
    )
    log(
        "  stream23 storage fit : "
        f'{plan["storage_stream23"]["fits"]}'
    )
    log(f"  upload ZIP           : {SUCCESS_ZIP}")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        OUT.mkdir(parents=True, exist_ok=True)
        LOG_DIR.mkdir(parents=True, exist_ok=True)

        failure = OUT / "FAILURE.txt"
        failure.write_text(
            traceback.format_exc(),
            encoding="utf-8",
        )

        zip_outputs(
            FAIL_ZIP,
            [failure],
        )

        print(traceback.format_exc(), flush=True)
        print(f"STAGE 37 FAILED: {FAIL_ZIP}", flush=True)
        raise SystemExit(1)
