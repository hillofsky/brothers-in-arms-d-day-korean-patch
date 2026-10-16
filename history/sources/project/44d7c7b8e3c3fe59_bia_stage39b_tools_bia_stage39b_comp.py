#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import csv
import importlib.util
import json
import re
import struct
import traceback
import zipfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(r"PROJECT_ROOT")
OUT = ROOT / "analysis" / "stage39b_compiled_mdi_text"
LOG_DIR = ROOT / "log"
TEST_ISO = ROOT / "BIA_STAGE39B_COMPILED_MDI_TEXT_TEST.iso"

SUCCESS_ZIP = LOG_DIR / "bia_stage39b_upload.zip"
FAIL_ZIP = LOG_DIR / "fail_bia_stage39b_upload.zip"

SCRIPT_DIR = Path(__file__).resolve().parent

# Import the already-built Stage39A production-font implementation.
spec = importlib.util.spec_from_file_location(
    "stage39a",
    SCRIPT_DIR / "bia_stage39a_source_encoding_proof.py",
)
s39 = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(s39)

b = s39.b

# Redirect imported helpers to this stage.
s39.OUT = OUT
s39.LOG_DIR = LOG_DIR
s39.TEST_ISO = TEST_ISO
s39.TEST_SOURCE_TEXT = "스토리"

b.ANALYSIS_DIR = OUT
b.LOG_DIR = LOG_DIR

# Extract original-style UTF-16 strings built from printable ASCII.
# These are the compiled menu/localization literals we can map safely back to
# Stage38B English translation units.
UTF16_ASCII_STRING_RE = re.compile(
    rb'(?:(?:[\x20-\x7E]\x00)){2,}\x00\x00'
)

# Do not touch these streams: 22 is the production atlas, 23 is production
# glyph records/pages.  All source strings found during analysis lived in
# earlier streams.
SKIP_STREAMS = {22, 23}

# Stage39A proved this target in .INT files does NOT drive the main menu.
# Stage39B expects the compiled MDI literal to produce this exact runtime text.
RUNTIME_EXPECTED = "스토리"


def log(msg: str):
    print(msg, flush=True)


def load_translations():
    rows = list(csv.DictReader(
        (
            SCRIPT_DIR / "stage39a_A_translations.tsv"
        ).open(encoding="utf-8-sig", newline=""),
        delimiter="\t",
    ))

    by_upper = defaultdict(set)
    detail = defaultdict(list)

    for row in rows:
        eng = row["English"]
        ko = row["한국어"]
        if not eng or not ko:
            continue

        # Compiled Magma menu literals commonly use uppercase even when the
        # source .INT value is title case.
        key = eng.upper()
        by_upper[key].add(ko)
        detail[key].append({
            "id": row["id"],
            "english": eng,
            "korean": ko,
            "references": row.get("references", ""),
        })

    mapping = {}
    conflicts = {}

    for key, values in by_upper.items():
        if len(values) == 1:
            mapping[key] = next(iter(values))
        else:
            conflicts[key] = {
                "korean_variants": sorted(values),
                "units": detail[key],
            }

    return rows, mapping, conflicts


def extra_null_capacity(dec: bytes, end_after_terminator: int, limit=64):
    extra = 0
    p = end_after_terminator
    while p + 2 <= len(dec) and extra < limit:
        if dec[p:p+2] != b"\x00\x00":
            break
        extra += 1
        p += 2
    return extra


def patch_compiled_utf16_strings(mdi: bytes, mapping: dict):
    streams = b.parse_mdi(mdi)

    replacements = {}
    patch_rows = []
    skipped_fit = []
    matched_units = set()

    for st in streams:
        si = st["index"]
        if si in SKIP_STREAMS:
            continue

        dec = bytearray(st["decoded"])
        changed = False

        # Work on a stable copy because replacements do not change decoded size.
        original_dec = bytes(dec)

        for m in UTF16_ASCII_STRING_RE.finditer(original_dec):
            raw = m.group()[:-2]
            try:
                text = raw.decode("utf-16le")
            except Exception:
                continue

            key = text.upper()
            korean = mapping.get(key)
            if korean is None:
                continue

            original_chars = len(text)
            extra = extra_null_capacity(
                original_dec, m.end()
            )
            capacity_chars = original_chars + extra

            matched_units.add(key)

            if len(korean) > capacity_chars:
                skipped_fit.append({
                    "stream": si,
                    "decoded_offset": f"0x{m.start():X}",
                    "english_compiled": text,
                    "korean": korean,
                    "original_chars": original_chars,
                    "capacity_chars": capacity_chars,
                    "reason": "Korean text exceeds fixed UTF-16 field capacity",
                })
                continue

            total_bytes = (capacity_chars + 1) * 2
            encoded = (
                korean.encode("utf-16le")
                + b"\x00\x00"
            )
            encoded += b"\x00" * (total_bytes - len(encoded))

            start = m.start()
            end = start + total_bytes

            before = bytes(dec[start:end])
            dec[start:end] = encoded

            if bytes(dec[start:end]) == before:
                continue

            patch_rows.append({
                "stream": si,
                "decoded_offset": f"0x{start:X}",
                "runtime_address":
                    f"0x{b.MDI_SEQ_BASE + si*b.MDI_STREAM_SIZE + start:08X}",
                "english_compiled": text,
                "translation_key": key,
                "korean": korean,
                "original_chars": original_chars,
                "capacity_chars": capacity_chars,
                "encoded_bytes": len(encoded),
            })
            changed = True

        if changed:
            replacements[si] = bytes(dec)

    rebuilt = b.rebuild_mdi(mdi, replacements)

    # Read-back verification of every patched field.
    vs = b.parse_mdi(rebuilt)
    for p in patch_rows:
        si = int(p["stream"])
        off = int(p["decoded_offset"], 16)
        got = vs[si]["decoded"][
            off:off + len(p["korean"].encode("utf-16le"))
        ]
        if got != p["korean"].encode("utf-16le"):
            raise RuntimeError(
                f"MDI text patch read-back failed at "
                f"stream {si} + {p['decoded_offset']}"
            )

    return rebuilt, {
        "patched_occurrences": len(patch_rows),
        "patched_streams": sorted(replacements),
        "matched_translation_keys": len(matched_units),
        "fixed_field_overflow_occurrences": len(skipped_fit),
        "fixed_field_overflows": skipped_fit,
        "patches": patch_rows,
    }


def build_iso():
    plan, atlas = s39.read_plan()
    translations, corpus = s39.read_translation_corpus()

    source_iso = b.find_original_iso()

    # This builds the already-verified 696-syllable production font and the
    # permanent 512x512 descriptor, but leaves localization source files alone.
    font_info, _, _ = s39.build_production_font_iso(
        source_iso, plan, atlas
    )

    _, mdi = b.iso_read_file(TEST_ISO, b.TARGET_MDI)

    _, mapping, conflicts = load_translations()
    patched_mdi, text_info = patch_compiled_utf16_strings(
        mdi, mapping
    )

    # Main-menu proof must be among the actual patches.
    story_patches = [
        p for p in text_info["patches"]
        if p["translation_key"] == "STORY"
    ]
    if not story_patches:
        raise RuntimeError(
            "No compiled UTF-16 STORY literal was patched in the MDI"
        )

    b.append_iso_file_and_repoint(
        TEST_ISO, b.TARGET_MDI, patched_mdi
    )

    _, rb = b.iso_read_file(TEST_ISO, b.TARGET_MDI)
    if rb != patched_mdi:
        raise RuntimeError("Final Stage39B MDI ISO read-back mismatch")

    return plan, {
        "font": font_info,
        "compiled_text": text_info,
        "translation_conflicts_skipped": conflicts,
        "story_patch_count": len(story_patches),
        "iso_readback_verified": True,
    }


def run_runtime(plan):
    exe = b.find_ppsspp_exe()

    cfg = OUT / "stage39b_append.ini"
    cfg.write_text(
        "[Debugger]\n"
        "ShowDeveloperMenu = True\n"
        "\n"
        "[Graphics]\n"
        "ReplaceTextures = False\n"
        "SaveNewTextures = False\n",
        encoding="utf-8",
    )

    # Reuse Stage39A's robust normal-JIT launch, native Start automation,
    # production-font verifier, screenshot-as-diagnostic policy, and
    # automatic PPSSPP shutdown.
    result = s39.run_variant(
        "compiled_mdi",
        exe,
        cfg,
        plan,
        plan["atlas_sha1"],
    )

    return result


def make_zip(path: Path):
    if path.exists():
        path.unlink()

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(OUT.rglob("*")):
            if p.is_file():
                z.write(p, p.relative_to(OUT).as_posix())

        for name in [
            "stage39a_A_translations.tsv",
            "stage39a_font_plan.json",
            "stage39a_tmr18_512x512_preview.png",
        ]:
            p = SCRIPT_DIR / name
            if p.exists():
                z.write(p, name)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    for p in OUT.iterdir():
        if p.is_file():
            p.unlink()

    report = {
        "stage": "39B",
        "purpose":
            "Prove that player-visible PSP menu text is sourced from compiled "
            "UTF-16 literals inside ON_MEMU_O.MDI rather than the loose .INT files",
        "stage39a_conclusion":
            "The production font was fully valid, but modifying loose "
            "LOCALIZE.INT/NEWLOCALIZE.INT never changed the runtime Story text.",
        "runtime_ram_text_patch": False,
        "loose_int_text_patch": False,
        "expected_runtime_story": RUNTIME_EXPECTED,
        "screenshot_failure_is_not_test_failure": True,
    }

    plan, build_info = build_iso()
    report["build"] = build_info
    report["production_font_plan"] = {
        "hangul_glyphs": plan["translated_A_units"] if "translated_A_units" in plan else 696,
        "glyph_count": plan["glyph_count_total"],
        "high_byte_pages": plan["high_byte_page_count"],
        "atlas_sha1": plan["atlas_sha1"],
    }

    runtime = run_runtime(plan)
    report["runtime"] = runtime

    source_ok = runtime.get("advance", {}).get("success", False)
    font_ok = runtime.get(
        "production_font_runtime", {}
    ).get("ok", False)

    report["compiled_mdi_source_proof"] = source_ok
    report["production_font_runtime_ok"] = font_ok
    report["completed"] = source_ok and font_ok

    report_path = OUT / "stage39b_report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # Save a compact patch table for the next stage.
    patch_tsv = OUT / "stage39b_mdi_text_patches.tsv"
    with patch_tsv.open(
        "w", encoding="utf-8-sig", newline=""
    ) as f:
        fields = [
            "stream", "decoded_offset", "runtime_address",
            "english_compiled", "translation_key", "korean",
            "original_chars", "capacity_chars", "encoded_bytes",
        ]
        w = csv.DictWriter(f, fields, delimiter="\t")
        w.writeheader()
        for row in build_info["compiled_text"]["patches"]:
            w.writerow({k: row.get(k, "") for k in fields})

    overflow_path = OUT / "stage39b_fixed_field_overflows.json"
    overflow_path.write_text(
        json.dumps(
            build_info["compiled_text"]["fixed_field_overflows"],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    if not report["completed"]:
        make_zip(FAIL_ZIP)
        raise RuntimeError(
            "Compiled-MDI Story source proof did not pass. "
            f"source_ok={source_ok}, font_ok={font_ok}"
        )

    make_zip(SUCCESS_ZIP)

    log("")
    log("[Stage39B] COMPLETE")
    log(
        "  patched UTF-16 occurrences : "
        f"{build_info['compiled_text']['patched_occurrences']}"
    )
    log(
        "  matched A translation keys : "
        f"{build_info['compiled_text']['matched_translation_keys']}"
    )
    log(
        "  fixed-field overflows       : "
        f"{build_info['compiled_text']['fixed_field_overflow_occurrences']}"
    )
    log(f"  runtime Story               : {RUNTIME_EXPECTED}")
    log(f"  ISO                         : {TEST_ISO}")
    log(f"  upload ZIP                  : {SUCCESS_ZIP}")


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

        try:
            make_zip(FAIL_ZIP)
        except Exception:
            pass

        print(traceback.format_exc(), flush=True)
        print(f"STAGE 39B FAILED: {FAIL_ZIP}", flush=True)
        raise SystemExit(1)
