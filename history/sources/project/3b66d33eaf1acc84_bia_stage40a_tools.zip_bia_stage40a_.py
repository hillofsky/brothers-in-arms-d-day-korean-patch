#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
import shutil
import sys
import traceback
import zipfile
from pathlib import Path

ROOT = Path(r"PROJECT_ROOT")
OUT = ROOT / "analysis" / "stage40a_asset_inventory"
LOG_DIR = ROOT / "log"

SUCCESS_ZIP = LOG_DIR / "bia_stage40a_upload.zip"
FAIL_ZIP = LOG_DIR / "fail_bia_stage40a_upload.zip"

REPORT_PATH = OUT / "stage40a_asset_inventory.json"
CANDIDATES_TSV = OUT / "stage40a_candidates.tsv"
TREE_TXT = OUT / "stage40a_tree.txt"
COLLECTED = OUT / "collected"

MAX_FILES = 20000
MAX_TEXT_BYTES = 32 * 1024 * 1024
MAX_MEMBER_BYTES = 16 * 1024 * 1024
MAX_COLLECT_TOTAL = 80 * 1024 * 1024
MAX_COLLECT_ONE = 12 * 1024 * 1024

TEXT_EXTS = {
    ".json", ".tsv", ".csv", ".txt", ".md",
    ".py", ".ps1", ".yaml", ".yml", ".ini",
    ".log",
}

SKIP_EXTS = {
    ".iso", ".cso", ".chd", ".img", ".bin",
    ".ppdmp", ".wav", ".mp3", ".at3", ".pmf",
    ".png", ".jpg", ".jpeg", ".webp",
}

# Exact markers from the established BIA translation pipeline.
MARKERS = [
    "1082",
    "696",
    "A-priority",
    "priority A",
    "clean A",
    "translation",
    "korean",
    "수정 한국어",
    "Carentan",
    "카랑탕",
    "Cherbourg",
    "셰르부르",
    "Hartsock",
    "하트삭",
    "MenuStory",
    "SINGLEPLAYER",
    "NEWGAME",
    "Start New Game",
    "glyph_count",
    "glyph_ptr",
    "098F5020",
    "stage39a",
    "stage38b",
    "stage39f",
]

# Known compiled narrow table signature.
MENU_SIGS = [
    b"SINGLEPLAYER\x00Story\x00MULTIPLAYER\x00Skirmish\x00",
    b"MenuStory\x00",
    b"NEWGAME\x00Start New Game\x00",
]

HANGUL_RE = re.compile(r"[\uAC00-\uD7A3]")
FIELD_HINT_RE = re.compile(
    r"(source|english|original|translation|korean|ko|priority|"
    r"translated|value|text|current|revised|수정|한국어)",
    re.I,
)


def log(msg):
    print(msg, flush=True)


def sha1_bytes(data):
    return hashlib.sha1(data).hexdigest()


def safe_rel(path):
    try:
        return path.relative_to(ROOT).as_posix()
    except Exception:
        return str(path)


def decode_text(data):
    # Strong BOM handling first.
    if data.startswith(b"\xef\xbb\xbf"):
        return data.decode("utf-8-sig"), "utf-8-sig"
    if data.startswith(b"\xff\xfe"):
        return data.decode("utf-16le"), "utf-16le"
    if data.startswith(b"\xfe\xff"):
        return data.decode("utf-16be"), "utf-16be"

    for enc in ("utf-8", "cp949", "cp1252"):
        try:
            return data.decode(enc), enc
        except Exception:
            pass

    return None, None


def json_shape(text):
    try:
        obj = json.loads(text)
    except Exception:
        return None

    info = {
        "type": type(obj).__name__,
    }

    if isinstance(obj, list):
        info["length"] = len(obj)
        if obj and isinstance(obj[0], dict):
            keys = set()
            for x in obj[:50]:
                if isinstance(x, dict):
                    keys.update(str(k) for k in x.keys())
            info["sample_keys"] = sorted(keys)[:80]

    elif isinstance(obj, dict):
        info["key_count"] = len(obj)
        info["sample_keys"] = list(obj.keys())[:80]

        # Common corpus containers.
        for k, v in obj.items():
            if isinstance(v, list):
                if len(v) in (1082, 1138, 1624, 2631, 3624):
                    info.setdefault("notable_lists", []).append(
                        {"key": str(k), "length": len(v)}
                    )

    return info


def delimited_shape(text, delimiter):
    try:
        rows = list(csv.reader(io.StringIO(text), delimiter=delimiter))
    except Exception:
        return None

    if not rows:
        return {"rows": 0}

    header = rows[0]
    return {
        "rows_including_header": len(rows),
        "data_rows": max(0, len(rows)-1),
        "columns": len(header),
        "header": header[:80],
    }


def score_text(name, text, size):
    lower = text.lower()
    score = 0
    reasons = []

    hangul = len(HANGUL_RE.findall(text))
    if hangul:
        score += min(30, hangul // 20 + 5)
        reasons.append(f"hangul={hangul}")

    for marker in MARKERS:
        c = lower.count(marker.lower())
        if c:
            add = min(18, 3 + c)
            score += add
            reasons.append(f"{marker}={c}")

    # Strongly prefer explicit corpus-sized data.
    line_count = text.count("\n") + 1
    for target in (1082, 1083, 1138, 1624, 2631, 3624):
        if abs(line_count - target) <= 2:
            score += 25
            reasons.append(f"lines~{target}")

    # Header hints.
    first = "\n".join(text.splitlines()[:5])
    if FIELD_HINT_RE.search(first):
        score += 10
        reasons.append("translation-like header")

    lname = name.lower()
    for tok in (
        "translation", "korean", "stage39a", "stage38b",
        "priority", "clean", "corpus", "localiz", "mdi",
        "font", "glyph", "menu",
    ):
        if tok in lname:
            score += 4
            reasons.append(f"name:{tok}")

    if size > 0 and size <= MAX_COLLECT_ONE:
        score += 1

    return score, reasons, hangul, line_count


def inspect_blob(display_name, data, source_type, container=None):
    rec = {
        "name": display_name,
        "source_type": source_type,
        "container": container,
        "size": len(data),
        "sha1": sha1_bytes(data),
        "menu_signature_hits": [],
    }

    for sig in MENU_SIGS:
        pos = data.find(sig)
        if pos >= 0:
            rec["menu_signature_hits"].append({
                "signature": sig[:48].decode(
                    "latin1", errors="replace"
                ),
                "offset": pos,
                "offset_hex": f"0x{pos:X}",
            })

    text, enc = decode_text(data)
    if text is None:
        # Binary menu signature files remain interesting.
        if rec["menu_signature_hits"]:
            rec["score"] = 60 + 20 * len(rec["menu_signature_hits"])
            rec["reasons"] = ["compiled menu signature"]
        else:
            rec["score"] = 0
            rec["reasons"] = []
        return rec

    rec["encoding"] = enc
    score, reasons, hangul, lines = score_text(
        display_name, text, len(data)
    )
    rec["score"] = score
    rec["reasons"] = reasons
    rec["hangul_chars"] = hangul
    rec["line_count"] = lines
    rec["preview"] = text[:3000]

    lname = display_name.lower()

    if lname.endswith(".json"):
        rec["json_shape"] = json_shape(text)

        js = rec["json_shape"]
        if js:
            if js.get("length") == 1082:
                rec["score"] += 80
                rec["reasons"].append("JSON length=1082")
            for item in js.get("notable_lists", []) if isinstance(js, dict) else []:
                if item["length"] == 1082:
                    rec["score"] += 80
                    rec["reasons"].append(
                        f"JSON {item['key']} length=1082"
                    )

    elif lname.endswith(".tsv"):
        rec["table_shape"] = delimited_shape(text, "\t")
        sh = rec["table_shape"]
        if sh and sh.get("data_rows") == 1082:
            rec["score"] += 80
            rec["reasons"].append("TSV data_rows=1082")

    elif lname.endswith(".csv"):
        rec["table_shape"] = delimited_shape(text, ",")
        sh = rec["table_shape"]
        if sh and sh.get("data_rows") == 1082:
            rec["score"] += 80
            rec["reasons"].append("CSV data_rows=1082")

    if rec["menu_signature_hits"]:
        rec["score"] += 60 + 20 * len(rec["menu_signature_hits"])
        rec["reasons"].append("compiled menu signature")

    return rec


def iter_files():
    count = 0

    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue

        # Don't scan this stage's own output while building it.
        try:
            path.relative_to(OUT)
            continue
        except Exception:
            pass

        count += 1
        if count > MAX_FILES:
            break

        yield path


def collect_copy(src_data, logical_name, used_names, collect_state):
    if len(src_data) > MAX_COLLECT_ONE:
        return None
    if collect_state["bytes"] + len(src_data) > MAX_COLLECT_TOTAL:
        return None

    clean = re.sub(r"[^A-Za-z0-9._-]+", "_", logical_name)
    clean = clean[-180:]
    if not clean:
        clean = "asset.bin"

    base = clean
    i = 1
    while clean.lower() in used_names:
        p = Path(base)
        clean = f"{p.stem}_{i}{p.suffix}"
        i += 1

    used_names.add(clean.lower())
    dest = COLLECTED / clean
    dest.write_bytes(src_data)
    collect_state["bytes"] += len(src_data)
    return dest.name


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    if OUT.exists():
        for p in OUT.iterdir():
            if p.is_dir():
                shutil.rmtree(p)
            else:
                p.unlink()

    COLLECTED.mkdir(parents=True, exist_ok=True)

    records = []
    tree = []
    zip_count = 0
    file_count = 0
    errors = []

    log("[Stage40A] Scanning PROJECT_ROOT assets")

    for path in iter_files():
        file_count += 1
        rel = safe_rel(path)

        try:
            size = path.stat().st_size
        except Exception as e:
            errors.append({"path": rel, "error": str(e)})
            continue

        tree.append(f"{size:12d}  {rel}")

        suffix = path.suffix.lower()

        # Inspect standalone text/script files.
        if suffix in TEXT_EXTS and size <= MAX_TEXT_BYTES:
            try:
                data = path.read_bytes()
                rec = inspect_blob(
                    rel,
                    data,
                    "file",
                )
                rec["path"] = str(path)
                records.append(rec)
            except Exception as e:
                errors.append({"path": rel, "error": str(e)})

        # Binary extracted resources can still expose the narrow menu signature.
        elif suffix not in SKIP_EXTS and size <= MAX_TEXT_BYTES:
            try:
                data = path.read_bytes()
                if any(sig in data for sig in MENU_SIGS):
                    rec = inspect_blob(
                        rel,
                        data,
                        "binary_file",
                    )
                    rec["path"] = str(path)
                    records.append(rec)
            except Exception:
                pass

        # Search prior tool/result ZIP contents without extracting everything.
        if suffix == ".zip" and size <= 2 * 1024 * 1024 * 1024:
            zip_count += 1

            try:
                with zipfile.ZipFile(path) as z:
                    for zi in z.infolist():
                        if zi.is_dir():
                            continue
                        if zi.file_size > MAX_MEMBER_BYTES:
                            continue

                        lname = zi.filename.lower()
                        ext = Path(lname).suffix

                        interesting_name = any(
                            tok in lname
                            for tok in (
                                "39a", "38b", "39f",
                                "translation", "korean",
                                "priority", "clean",
                                "corpus", "localiz",
                                "font", "glyph",
                                "mdi", "menu",
                            )
                        )

                        if ext not in TEXT_EXTS and not interesting_name:
                            continue

                        try:
                            data = z.read(zi)
                        except Exception:
                            continue

                        rec = inspect_blob(
                            f"{rel}::{zi.filename}",
                            data,
                            "zip_member",
                            container=rel,
                        )

                        # Avoid adding thousands of generic log members.
                        if (
                            rec["score"] > 0
                            or rec["menu_signature_hits"]
                            or interesting_name
                        ):
                            rec["zip_path"] = str(path)
                            rec["zip_member"] = zi.filename
                            records.append(rec)

            except Exception as e:
                errors.append({"path": rel, "error": f"zip: {e}"})

    TREE_TXT.write_text(
        "\n".join(tree),
        encoding="utf-8",
    )

    records.sort(
        key=lambda x: (
            x.get("score", 0),
            x.get("hangul_chars", 0),
            -x.get("size", 0),
        ),
        reverse=True,
    )

    # Copy top useful candidates into the upload ZIP so the next stage can be
    # designed from exact bytes, not filenames alone.
    used_names = set()
    collect_state = {"bytes": 0}
    collected = []

    for rec in records:
        if rec.get("score", 0) < 12:
            continue
        if len(collected) >= 80:
            break

        data = None

        try:
            if rec["source_type"] in ("file", "binary_file"):
                data = Path(rec["path"]).read_bytes()
            elif rec["source_type"] == "zip_member":
                with zipfile.ZipFile(rec["zip_path"]) as z:
                    data = z.read(rec["zip_member"])
        except Exception:
            continue

        if data is None:
            continue

        copied = collect_copy(
            data,
            rec["name"],
            used_names,
            collect_state,
        )
        if copied:
            rec["collected_as"] = copied
            collected.append(copied)

    report = {
        "stage": "40A",
        "purpose":
            "Discover and collect the exact existing Stage38B/39A translation "
            "corpus and compiled localization/MDI artifacts needed for mass "
            "A-priority insertion.",
        "root": str(ROOT),
        "files_scanned": file_count,
        "zip_files_scanned": zip_count,
        "candidate_count": len(records),
        "collected_count": len(collected),
        "collected_bytes": collect_state["bytes"],
        "top_candidates": records[:120],
        "errors": errors[:200],
        "stage39u_baseline":
            "Renderer-side widened UTF-8 decoding is visually proven working. "
            "Stage40 should preserve the BOOT helper and production 847-glyph font.",
        "completed": True,
    }

    REPORT_PATH.write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    with CANDIDATES_TSV.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow([
            "rank",
            "score",
            "source_type",
            "size",
            "hangul_chars",
            "line_count",
            "name",
            "reasons",
            "collected_as",
        ])

        for i, rec in enumerate(records[:500], 1):
            w.writerow([
                i,
                rec.get("score", 0),
                rec.get("source_type", ""),
                rec.get("size", 0),
                rec.get("hangul_chars", 0),
                rec.get("line_count", 0),
                rec.get("name", ""),
                "; ".join(rec.get("reasons", [])),
                rec.get("collected_as", ""),
            ])

    if SUCCESS_ZIP.exists():
        SUCCESS_ZIP.unlink()

    with zipfile.ZipFile(
        SUCCESS_ZIP,
        "w",
        zipfile.ZIP_DEFLATED,
    ) as z:
        for p in sorted(OUT.rglob("*")):
            if p.is_file():
                z.write(
                    p,
                    p.relative_to(OUT).as_posix(),
                )

    log("[Stage40A] COMPLETE")
    log(f"[Stage40A] Upload ZIP: {SUCCESS_ZIP}")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        OUT.mkdir(parents=True, exist_ok=True)
        LOG_DIR.mkdir(parents=True, exist_ok=True)

        (OUT / "FAILURE.txt").write_text(
            traceback.format_exc(),
            encoding="utf-8",
        )

        try:
            if FAIL_ZIP.exists():
                FAIL_ZIP.unlink()

            with zipfile.ZipFile(
                FAIL_ZIP,
                "w",
                zipfile.ZIP_DEFLATED,
            ) as z:
                for p in sorted(OUT.rglob("*")):
                    if p.is_file():
                        z.write(
                            p,
                            p.relative_to(OUT).as_posix(),
                        )
        except Exception:
            pass

        print(traceback.format_exc(), flush=True)
        print(
            f"STAGE 40A FAILED: {FAIL_ZIP}",
            flush=True,
        )
        raise SystemExit(1)
