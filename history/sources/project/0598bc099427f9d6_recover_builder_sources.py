#!/usr/bin/env python3
from pathlib import Path
import zipfile, hashlib, json, shutil, os, re, sys

ROOT = Path(r"PROJECT_ROOT")
OUT = None

STEP064_ZIP = ROOT / "log" / "bia_STEP_064_exact_campaign_apply_recovery_RESULT.zip"
STEP064_ENTRY = "outputs/recovered_pipeline_files/FS_log__STEP_044_FIX6__outputs__source_evidence__07_build_campaign43a.py__07_build_campaign43a.py"

PLAIN_CANDIDATES = [
    ROOT / "bia_stage39b_tools" / "bia_stage39b_compiled_mdi_text.py",
    ROOT / "bia_stage39b_tools" / "bia_stage36_base.py",
    ROOT / "bia_stage40i_tools" / "bia_stage40i_actual_resource_trace.py",
]

LEGACY_ZIPS = [
    Path(r"SESSION_SESSION_OUTPUTS\bia_stage40y_handoff.zip"),
    ROOT / "log" / "fall_bia_STEP_044_campaign_next_batch_RESULT.zip",
    ROOT / "log" / "fall_bia_STEP_068_movie_nonmdi_reconcile_RESULT.zip",
]

WANTED_BASENAMES = {
    "build_campaign43a.py",
    "build_firstmission40y.py",
    "build_campaign40r.py",
    "bia_stage39b_compiled_mdi_text.py",
    "bia_stage36_base.py",
    "bia_stage40i_actual_resource_trace.py",
}

def sha256(b: bytes):
    return hashlib.sha256(b).hexdigest()

def add_bytes(manifest, label, source, entry, data):
    dst = OUT / "recovered"
    dst.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", label)
    p = dst / safe
    p.write_bytes(data)
    manifest.append({
        "label": label,
        "source": source,
        "entry": entry,
        "output": str(p),
        "size": len(data),
        "sha256": sha256(data),
    })
    return p

def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", required=True)
    args = ap.parse_args()

    global OUT
    OUT = Path(args.outdir)
    OUT.mkdir(parents=True, exist_ok=True)

    manifest = []
    report = {
        "step": "STEP_073",
        "status": "IN_PROGRESS",
        "iso_modified": False,
        "step064_zip": str(STEP064_ZIP),
        "step064_entry": STEP064_ENTRY,
        "exact_campaign43a_recovered": False,
        "plain_files": [],
        "archive_candidates": [],
    }

    # 1) Exact known successful Stage43A builder source.
    if not STEP064_ZIP.exists():
        raise RuntimeError(f"Missing verified STEP064 result ZIP: {STEP064_ZIP}")

    with zipfile.ZipFile(STEP064_ZIP) as z:
        names = z.namelist()
        if STEP064_ENTRY in names:
            data = z.read(STEP064_ENTRY)
            out = add_bytes(
                manifest,
                "build_campaign43a.py",
                str(STEP064_ZIP),
                STEP064_ENTRY,
                data,
            )
            report["exact_campaign43a_recovered"] = True
            report["campaign43a_output"] = str(out)
        else:
            # Allow exact suffix recovery if slash normalization differs.
            norm_target = STEP064_ENTRY.replace("\\", "/").lower()
            hit = None
            for n in names:
                if n.replace("\\", "/").lower() == norm_target:
                    hit = n
                    break
            if hit is None:
                # Last-resort: the unique candidate ending in 07_build_campaign43a.py.
                cand = [n for n in names if n.replace("\\","/").lower().endswith("07_build_campaign43a.py")]
                if len(cand) == 1:
                    hit = cand[0]
            if hit is None:
                raise RuntimeError("Exact Stage43A source entry not found in verified STEP064 ZIP")
            data = z.read(hit)
            out = add_bytes(
                manifest,
                "build_campaign43a.py",
                str(STEP064_ZIP),
                hit,
                data,
            )
            report["exact_campaign43a_recovered"] = True
            report["campaign43a_output"] = str(out)

    # 2) Current helper sources, exact paths only.
    for p in PLAIN_CANDIDATES:
        rec = {"path": str(p), "exists": p.exists()}
        if p.exists():
            data = p.read_bytes()
            add_bytes(manifest, p.name, str(p), "", data)
            rec["size"] = len(data)
            rec["sha256"] = sha256(data)
        report["plain_files"].append(rec)

    # 3) Targeted historical builder recovery from known legacy archives only.
    seen_labels = {m["label"] for m in manifest}
    for zp in LEGACY_ZIPS:
        zrec = {"zip": str(zp), "exists": zp.exists(), "matches": []}
        if zp.exists():
            try:
                with zipfile.ZipFile(zp) as z:
                    for n in z.namelist():
                        base = Path(n.replace("\\","/")).name
                        if base in WANTED_BASENAMES:
                            b = z.read(n)
                            label = base
                            # Don't overwrite the exact Stage43A source.
                            if label in seen_labels:
                                label = f"{zp.stem}__{base}"
                            add_bytes(manifest, label, str(zp), n, b)
                            seen_labels.add(label)
                            zrec["matches"].append({"entry": n, "basename": base, "sha256": sha256(b)})
            except Exception as e:
                zrec["error"] = repr(e)
        report["archive_candidates"].append(zrec)

    # 4) Source-level capability inventory to guide generalized patcher.
    capabilities = []
    for m in manifest:
        op = Path(m["output"])
        if op.suffix.lower() != ".py":
            continue
        txt = op.read_text(encoding="utf-8-sig", errors="replace")
        funcs = re.findall(r"(?m)^def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", txt)
        classes = re.findall(r"(?m)^class\s+([A-Za-z_][A-Za-z0-9_]*)\s*[:(]", txt)
        capabilities.append({
            "label": m["label"],
            "functions": funcs,
            "classes": classes,
            "mentions": {
                "append_iso_file_and_repoint": "append_iso_file_and_repoint" in txt,
                "rebuild_mdi": "rebuild_mdi" in txt,
                "rebuild_dsx": "rebuild_dsx" in txt,
                "stage39a_font_plan": "stage39a_font_plan" in txt,
                "payload_stream35": ("stream35" in txt.lower()) or ("0xB000" in txt),
                "atlas_stream34": ("stream34" in txt.lower()) or ("0x09DF3020" in txt),
                "dsl_relocation": ("0x31E2AE" in txt) or ("DSL" in txt and "reloc" in txt.lower()),
                "fstring": "FString" in txt or "fstring" in txt,
                "glyph": "glyph" in txt.lower(),
                "atlas": "atlas" in txt.lower(),
            },
        })
    report["capabilities"] = capabilities

    required = [
        "build_campaign43a.py",
        "bia_stage39b_compiled_mdi_text.py",
        "bia_stage36_base.py",
    ]
    labels = {m["label"] for m in manifest}
    report["required_labels"] = required
    report["missing_required_labels"] = [x for x in required if x not in labels]
    report["manifest_count"] = len(manifest)
    report["status"] = "VERIFIED_SOURCE_RECOVERY" if not report["missing_required_labels"] else "BLOCKED_MISSING_SOURCE"

    (OUT/"source_recovery_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (OUT/"step073_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    summary = [
        f"STATUS={report['status']}",
        f"EXACT_CAMPAIGN43A_RECOVERED={report['exact_campaign43a_recovered']}",
        f"MANIFEST_COUNT={len(manifest)}",
        "MISSING_REQUIRED=" + ",".join(report["missing_required_labels"]),
        "ISO_MODIFIED=FALSE",
    ]
    (OUT/"STEP073_SUMMARY.txt").write_text("\n".join(summary)+"\n", encoding="utf-8")

    if report["missing_required_labels"]:
        raise SystemExit(4)

if __name__ == "__main__":
    main()
