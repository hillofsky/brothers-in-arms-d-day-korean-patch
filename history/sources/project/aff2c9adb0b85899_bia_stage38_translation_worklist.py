#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
import traceback
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(r"PROJECT_ROOT")
OUT = ROOT / "analysis" / "stage38_translation_worklist"
LOG_DIR = ROOT / "log"

SUCCESS_ZIP = LOG_DIR / "bia_stage38_upload.zip"
FAIL_ZIP = LOG_DIR / "fail_bia_stage38_upload.zip"

# Stage37 was polluted by false Hangul created when cp1252/UTF-8 game files
# were guessed as CP949/UTF-16.  Stage38 deliberately NEVER uses CP949 for
# original game localization files.
KNOWN_TEST_KOREAN = {
    "한글", "한글B", "한글테스트",
}

PRIORITY_A = {
    "NEWLOCALIZE", "LOCALIZE",
    "MEMORYCARD", "MEMORYSTICK", "LOCALONL", "DNASERR",
    "CHAPTERS", "GUI", "GUIDEMO", "EXTRAS", "GAMEPLAY",
    "GBXBASE", "GBXGAMEPLAY", "GBXHUD", "GBXINVENTORY",
    "GBXMP", "GBXSCRIPTED", "GBXUI", "GBXVEHICLES",
    "TRAININGBUTTONS", "DEFMPMAPS", "DEFMPMAPS_DLC",
}

PRIORITY_C = {
    "ENGINE", "CORE", "CREDITS",
}

# Keys which are overwhelmingly assets/config rather than text shown to user.
EXCLUDE_KEY_RE = re.compile(
    r"""(?ix)
    (^|_)
    (
      image|img|texture|tex|material|mesh|sound|music|package|class|object|
      font|shader|effect|actor|pawn|weaponclass|inventoryclass|
      map|mapname|filename|file|path|url|port|ip|server|
      count|index|id|guid|version|size|width|height|
      time|delay|duration|rate|scale|offset|position|rotation|
      color|alpha|volume|pitch|priority|weight|
      x|y|z
    )
    ($|_)
    """
)

# Common resource/object forms that should not be translated.
RESOURCE_VALUE_RE = re.compile(
    r"""(?ix)
    ^\s*
    (
       \(?name= |
       class= |
       object= |
       [a-z0-9_]+\.[a-z0-9_]+\.[a-z0-9_]+ |
       [a-z0-9_]+/[a-z0-9_./-]+ |
       [a-z]:\\ |
       0x[0-9a-f]+ |
       [-+]?\d+(?:\.\d+)? |
       true|false|none|null
    )
    \s*$
    """
)

TOKEN_RE = re.compile(
    r"""(
        %[A-Za-z0-9_]+% |
        %(?:s|d|i|f|u|x|X|c) |
        <[^<>]+> |
        \\[nrt] |
        \{[^{}]+\}
    )""",
    re.X,
)

HUMAN_WORD_RE = re.compile(r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ'’.-]*")


def log(msg: str):
    print(msg, flush=True)


def sha1_bytes(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


def locate_system_dir() -> Path:
    preferred = ROOT / "extracted" / "PSP_GAME" / "USRDIR" / "SYSTEM"
    if (preferred / "LOCALIZE.INT").exists():
        return preferred

    hits = []
    for p in ROOT.rglob("LOCALIZE.INT"):
        if p.is_file() and p.parent.name.upper() == "SYSTEM":
            if (p.parent / "NEWLOCALIZE.INT").exists():
                hits.append(p.parent)

    if not hits:
        raise RuntimeError(
            "Could not locate extracted PSP_GAME\\USRDIR\\SYSTEM under PROJECT_ROOT. "
            "Expected PROJECT_ROOT\\extracted\\PSP_GAME\\USRDIR\\SYSTEM."
        )

    # Prefer shortest path / extracted-like directory.
    hits.sort(
        key=lambda p: (
            0 if "extracted" in str(p).lower() else 1,
            len(str(p)),
        )
    )
    return hits[0]


def decode_game_text(data: bytes):
    """
    Decode original localization text without CP949 guessing.

    Known BIA assets are UTF-8/ASCII or Windows-1252.  UTF-16 is accepted only
    when a BOM is actually present.
    """
    if data.startswith(b"\xff\xfe"):
        return data.decode("utf-16le"), "utf-16le"
    if data.startswith(b"\xfe\xff"):
        return data.decode("utf-16be"), "utf-16be"

    try:
        return data.decode("utf-8-sig"), "utf-8-sig"
    except UnicodeDecodeError:
        return data.decode("cp1252"), "cp1252"


def parse_int_file(path: Path):
    raw = path.read_bytes()
    text, encoding = decode_game_text(raw)

    # A strong guard against Stage37's false-positive decoding.
    replacement_count = text.count("\ufffd")
    if replacement_count:
        raise RuntimeError(
            f"{path}: decoded with replacement characters unexpectedly"
        )

    rows = []
    section = ""
    for lineno, raw_line in enumerate(text.splitlines(), 1):
        stripped = raw_line.strip()
        if not stripped or stripped.startswith(";"):
            continue

        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped[1:-1].strip()
            continue

        if "=" not in raw_line:
            continue

        key, value = raw_line.split("=", 1)
        key = key.strip()
        value = value.strip()

        rows.append({
            "path": path,
            "stem": path.stem.upper(),
            "line": lineno,
            "section": section,
            "key": key,
            "raw_value": value,
            "encoding": encoding,
            "file_sha1": sha1_bytes(raw),
        })

    return rows


def strip_outer_quotes(value: str):
    """
    Preserve quote style so translated text can later be reinserted exactly.
    """
    if len(value) >= 6 and value.startswith('"""') and value.endswith('"""'):
        return value[3:-3], '"""'
    if len(value) >= 2 and value.startswith('"') and value.endswith('"'):
        return value[1:-1], '"'
    return value, ""


def classify_file(stem: str):
    s = stem.upper()

    if s in PRIORITY_A:
        return "A", "core UI/system"

    if (
        re.match(r"^D\d", s)
        and not s.endswith("_PSP_8BIT")
    ):
        return "B", "story/dialogue mission"

    if s.startswith("S_SKR_"):
        return "B", "skirmish mission"

    if s in PRIORITY_C:
        return "C", "secondary/system"

    return "X", "not targeted"


def looks_translatable(row):
    stem = row["stem"]
    section = row["section"]
    key = row["key"]
    raw = row["raw_value"]

    priority, category = classify_file(stem)
    if priority == "X":
        return False, "non-target file", priority, category

    core, quote = strip_outer_quotes(raw)
    t = core.strip()

    if not t:
        return False, "empty", priority, category

    # Numerical timing rows, especially VOICEOVER_X_T=-1.5.
    if re.search(r"(?:^|_)T$", key, re.I) and re.fullmatch(
        r"[-+]?\d+(?:\.\d+)?", t
    ):
        return False, "timing value", priority, category

    if EXCLUDE_KEY_RE.search(key):
        # Some keys called TITLE/NAME are visible, so only generic resource-ish
        # names are excluded by the regexp.
        return False, "resource/config key", priority, category

    if RESOURCE_VALUE_RE.match(t):
        return False, "resource/config value", priority, category

    # Explicit resource prefixes common in Unreal/Magma assets.
    if re.match(
        r"(?i)^(?:t_|m_|s_|a_|p_|w_|gbx|engine\.|core\.)[A-Za-z0-9_.]+$",
        t,
    ):
        return False, "asset identifier", priority, category

    words = HUMAN_WORD_RE.findall(t)

    # Keep very short visible UI strings such as "On", "No", "OK".
    if len(t) <= 32 and re.search(r"[A-Za-z]", t):
        return True, "", priority, category

    # Longer strings need at least two human-readable words or punctuation.
    if len(words) >= 2:
        return True, "", priority, category

    if any(ch in t for ch in "!?.,:;"):
        if re.search(r"[A-Za-z]", t):
            return True, "", priority, category

    return False, "not human-readable text", priority, category


def token_signature(text: str):
    return TOKEN_RE.findall(text)


def normalize_dedupe_key(text: str):
    # Exact text semantics, but normalize CR/LF and insignificant outer spaces.
    return text.replace("\r\n", "\n").strip()


def write_tsv(path: Path, header, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter="\t", quoting=csv.QUOTE_MINIMAL)
        w.writerow(header)
        w.writerows(rows)


def zip_outputs(zip_path: Path, root: Path):
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    if zip_path.exists():
        zip_path.unlink()

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(root.rglob("*")):
            if p.is_file():
                z.write(p, p.relative_to(root).as_posix())


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    system_dir = locate_system_dir()
    log(f"[Stage38] SYSTEM: {system_dir}")

    int_files = sorted(system_dir.glob("*.INT"))
    if not int_files:
        raise RuntimeError(f"No .INT files found in {system_dir}")

    all_entries = []
    source_meta = []
    excluded_rows = []

    for path in int_files:
        try:
            parsed = parse_int_file(path)
        except Exception as e:
            source_meta.append([
                path.name, "", "", 0, 0, f"ERROR: {e}"
            ])
            continue

        if parsed:
            encoding = parsed[0]["encoding"]
            file_sha1 = parsed[0]["file_sha1"]
        else:
            data = path.read_bytes()
            _, encoding = decode_game_text(data)
            file_sha1 = sha1_bytes(data)

        priority, category = classify_file(path.stem.upper())

        accepted_count = 0
        for row in parsed:
            ok, reason, p, cat = looks_translatable(row)
            row["priority"] = p
            row["category"] = cat
            row["accepted"] = ok
            row["exclude_reason"] = reason

            if ok:
                accepted_count += 1
                all_entries.append(row)
            else:
                excluded_rows.append(row)

        source_meta.append([
            path.name,
            priority,
            category,
            len(parsed),
            accepted_count,
            encoding,
            file_sha1,
        ])

    if not all_entries:
        raise RuntimeError("No translatable INT entries were extracted.")

    # Build deduplicated translation units.
    units = {}
    for row in all_entries:
        core, quote_style = strip_outer_quotes(row["raw_value"])
        dedupe = normalize_dedupe_key(core)

        u = units.get(dedupe)
        if u is None:
            u = {
                "english": core,
                "quote_styles": Counter(),
                "priorities": set(),
                "categories": set(),
                "refs": [],
                "tokens": token_signature(core),
            }
            units[dedupe] = u

        u["quote_styles"][quote_style] += 1
        u["priorities"].add(row["priority"])
        u["categories"].add(row["category"])
        u["refs"].append(row)

    priority_rank = {"A": 0, "B": 1, "C": 2}

    def unit_sort(item):
        key, u = item
        pr = min(
            u["priorities"],
            key=lambda x: priority_rank.get(x, 9),
        )
        # Core UI before dialogue, then stable English ordering.
        return (
            priority_rank.get(pr, 9),
            -len(u["refs"]),
            u["english"].lower(),
        )

    sorted_units = sorted(units.items(), key=unit_sort)

    unit_rows = []
    unit_lookup = {}
    for idx, (dedupe, u) in enumerate(sorted_units, 1):
        unit_id = f"BIA-{idx:05d}"
        unit_lookup[dedupe] = unit_id

        best_priority = min(
            u["priorities"],
            key=lambda x: priority_rank.get(x, 9),
        )

        refs = u["refs"]
        ref_text = " | ".join(
            f'{r["stem"]}:{r["section"]}:{r["key"]}@{r["line"]}'
            for r in refs[:8]
        )
        if len(refs) > 8:
            ref_text += f" | +{len(refs)-8} more"

        unit_rows.append([
            unit_id,
            best_priority,
            ",".join(sorted(u["categories"])),
            u["english"],
            "",
            json.dumps(u["tokens"], ensure_ascii=False),
            len(refs),
            ref_text,
            " | ".join(
                f'{k}:{v}'
                for k, v in sorted(u["quote_styles"].items())
            ),
            "",
        ])

    # Row-level map used later to apply translated units to exact source lines.
    entry_rows = []
    for row in all_entries:
        core, quote_style = strip_outer_quotes(row["raw_value"])
        unit_id = unit_lookup[normalize_dedupe_key(core)]
        entry_rows.append([
            unit_id,
            row["priority"],
            row["category"],
            row["path"].name,
            row["line"],
            row["section"],
            row["key"],
            row["raw_value"],
            quote_style,
            row["encoding"],
            row["file_sha1"],
        ])

    # Summary.
    priority_entries = Counter(r["priority"] for r in all_entries)
    priority_units = Counter(row[1] for row in unit_rows)

    summary = {
        "stage": 38,
        "purpose": "Generate clean Korean translation worklists from original BIA .INT files",
        "system_dir": str(system_dir),
        "source_int_files": len(int_files),
        "accepted_entry_rows": len(all_entries),
        "deduplicated_translation_units": len(unit_rows),
        "priority_entry_counts": dict(priority_entries),
        "priority_unit_counts": dict(priority_units),
        "stage37_correction": {
            "status": "INVALID_AS_REAL_CORPUS",
            "reason":
                "Stage37 guessed CP949/UTF-16 for original Western game files, "
                "creating false Hangul syllables from cp1252/ASCII bytes. "
                "Observed garbage included 뀠/뼊/윊/췗. The only meaningful "
                "Korean strings were earlier font test artifacts such as "
                "한글테스트/한글B.",
            "production_atlas_must_not_use_stage37_plan": True,
        },
        "encoding_policy": [
            "UTF-8/UTF-8-SIG",
            "Windows-1252 fallback",
            "UTF-16 only with BOM",
            "NO CP949 guessing",
        ],
        "next_step":
            "Translate stage38 batch TSV files. After completed translations "
            "are merged, recalculate the actual U+AC00..U+D7A3 corpus and build "
            "the production atlas.",
    }

    # Clean output folder before writing.
    for p in OUT.iterdir():
        if p.is_file():
            p.unlink()
        elif p.is_dir():
            import shutil
            shutil.rmtree(p)

    summary_path = OUT / "stage38_summary.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    source_path = OUT / "stage38_source_files.tsv"
    write_tsv(
        source_path,
        [
            "file", "priority", "category", "parsed_entries",
            "accepted_entries", "encoding", "sha1",
        ],
        source_meta,
    )

    units_path = OUT / "stage38_translation_units.tsv"
    unit_header = [
        "id", "priority", "category", "English", "한국어",
        "control_tokens", "reference_count", "references",
        "quote_styles", "메모",
    ]
    write_tsv(units_path, unit_header, unit_rows)

    entries_path = OUT / "stage38_entry_map.tsv"
    write_tsv(
        entries_path,
        [
            "id", "priority", "category", "file", "line",
            "section", "key", "original_raw_value", "quote_style",
            "encoding", "source_sha1",
        ],
        entry_rows,
    )

    excluded_path = OUT / "stage38_excluded_samples.tsv"
    excluded_sample_rows = []
    for row in excluded_rows[:3000]:
        excluded_sample_rows.append([
            row["path"].name,
            row["line"],
            row["section"],
            row["key"],
            row["raw_value"],
            row["exclude_reason"],
            row["priority"],
        ])
    write_tsv(
        excluded_path,
        [
            "file", "line", "section", "key", "raw_value",
            "reason", "priority",
        ],
        excluded_sample_rows,
    )

    # ChatGPT-ready chunks.
    batch_dir = OUT / "batches"
    batch_dir.mkdir(parents=True, exist_ok=True)

    BATCH_SIZE = 220
    for start in range(0, len(unit_rows), BATCH_SIZE):
        batch_no = start // BATCH_SIZE + 1
        batch = unit_rows[start:start+BATCH_SIZE]
        batch_path = batch_dir / f"bia_translation_batch_{batch_no:03d}.tsv"
        write_tsv(batch_path, unit_header, batch)

    instructions = OUT / "TRANSLATION_README.md"
    instructions.write_text(
        """# BIA Stage 38 한국어 번역 배치

각 `batches/bia_translation_batch_XXX.tsv`의 `한국어` 열을 채웁니다.

## 규칙

- `English` 의미를 자연스러운 한국어 게임 문장으로 번역합니다.
- `control_tokens`에 있는 토큰은 종류/개수/순서를 그대로 보존합니다.
- `<PROFILE>`, `%s`, `%d`, `%newline%` 같은 런타임 토큰을 번역하거나 삭제하지 않습니다.
- 고유명사/계급/군사용어를 일관되게 번역합니다.
- `id`, `priority`, `category`, `English`, `control_tokens`,
  `reference_count`, `references`, `quote_styles`는 수정하지 않습니다.
- 확신하기 어려운 행은 `한국어`를 비우고 `메모`에 이유를 적습니다.
- Stage37에서 계산한 글꼴 corpus는 사용하지 않습니다. 실제 번역이 완료된 후
  이 `한국어` 열들만 모아 한글 고유 음절을 다시 계산합니다.

## 우선순위

- A: 메뉴/UI/시스템/공통 게임 텍스트
- B: 스토리 대사 및 스커미시 미션 텍스트
- C: 엔진/크레딧 등 후순위 텍스트

파일 순서는 A -> B -> C로 정렬되어 있습니다.
""",
        encoding="utf-8",
    )

    zip_outputs(SUCCESS_ZIP, OUT)

    log("")
    log("[Stage38] COMPLETE")
    log(f"  source INT files        : {len(int_files)}")
    log(f"  accepted entry rows     : {len(all_entries)}")
    log(f"  deduplicated units      : {len(unit_rows)}")
    log(f"  batches                 : {(len(unit_rows)+BATCH_SIZE-1)//BATCH_SIZE}")
    log(f"  output                  : {SUCCESS_ZIP}")


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

        # Failure ZIP contains script diagnostics only.
        if FAIL_ZIP.exists():
            FAIL_ZIP.unlink()
        with zipfile.ZipFile(FAIL_ZIP, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(failure, "FAILURE.txt")

        print(traceback.format_exc(), flush=True)
        print(f"STAGE 38 FAILED: {FAIL_ZIP}", flush=True)
        raise SystemExit(1)
