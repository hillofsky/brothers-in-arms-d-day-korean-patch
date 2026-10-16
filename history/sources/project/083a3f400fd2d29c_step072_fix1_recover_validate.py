#!/usr/bin/env python3
from __future__ import annotations
import csv, hashlib, io, json, os, re, shutil, sys, zipfile
from collections import Counter
from pathlib import Path

ROOT=Path(r"PROJECT_ROOT")
PREV=ROOT/"log"/"STEP_072"/"outputs"

REQUIRED_EVIDENCE=[
    "allstream_fstring_refs.tsv",
    "allstream_font_objects.tsv",
    "allstream_mdi_glyph_demand.tsv",
    "stage39a_font_plan.json",
    "campaign_final_apply_split.tsv",
    "stage38_translation_units.tsv",
    "stage38_entry_map.tsv",
    "bia_stage40i_actual_resource_trace.py",
    "bia_stage36_base.py",
]
HISTORICAL="build_campaign43a.py"

def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()

def sha256_file(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""):h.update(b)
    return h.hexdigest()

def find_prev_evidence(name):
    ev=PREV/"evidence"
    if not ev.exists(): return []
    return [p for p in ev.iterdir() if p.is_file() and p.name.endswith("_"+name)]

def search_plain(name):
    hits=[]
    for dp,dns,fns in os.walk(ROOT):
        for fn in fns:
            if fn.lower()==name.lower():
                hits.append(Path(dp)/fn)
    return hits

def archive_candidates():
    roots=[ROOT/"log",ROOT/"incoming",ROOT/"analysis"]
    for root in roots:
        if not root.exists():continue
        for dp,dns,fns in os.walk(root):
            for fn in fns:
                if not fn.lower().endswith(".zip"):continue
                p=Path(dp)/fn
                # Prefer historically relevant archives first but still inspect all
                yield p

def recover_historical(out):
    result={"plain_hits":[],"archive_hits":[],"candidate_43a_scripts":[]}
    for p in search_plain(HISTORICAL):
        result["plain_hits"].append(str(p))
        dest=out/"historical"/HISTORICAL
        dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(p,dest)
        result["recovered_to"]=str(dest)
        result["sha256"]=sha256_file(dest)
        return result

    # Search ZIP central directories for the exact basename first.
    checked=0
    for zp in archive_candidates():
        checked+=1
        try:
            with zipfile.ZipFile(zp) as z:
                names=z.namelist()
                exact=[n for n in names if Path(n.replace("\\","/")).name.lower()==HISTORICAL.lower()]
                for n in exact:
                    b=z.read(n)
                    dest=out/"historical"/HISTORICAL
                    dest.parent.mkdir(parents=True,exist_ok=True)
                    dest.write_bytes(b)
                    result["archive_hits"].append({"zip":str(zp),"entry":n,"sha256":sha256_bytes(b)})
                    result["recovered_to"]=str(dest)
                    result["sha256"]=sha256_bytes(b)
                    result["archives_checked"]=checked
                    return result

                # Record plausible 43A/campaign builders for diagnosis.
                for n in names:
                    bn=Path(n.replace("\\","/")).name.lower()
                    if bn.endswith(".py") and ("43a" in bn or ("campaign" in bn and "build" in bn)):
                        result["candidate_43a_scripts"].append({"zip":str(zp),"entry":n})
        except Exception:
            pass
    result["archives_checked"]=checked
    return result

def parse_tsv(path):
    with path.open("r",encoding="utf-8-sig",errors="replace",newline="") as f:
        return list(csv.DictReader(f,delimiter="\t"))

def main():
    import argparse
    ap=argparse.ArgumentParser()
    ap.add_argument("--outdir",required=True)
    a=ap.parse_args()
    out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)
    evidence=out/"evidence";evidence.mkdir(exist_ok=True)

    report={
        "step":"STEP_072_FIX1",
        "status":"IN_PROGRESS",
        "iso_modified":False,
        "previous_step072_exists":PREV.exists(),
        "evidence":{},
    }

    # Reuse the evidence already collected by failed STEP072 instead of rescanning
    # the whole project. Fall back to exact-name filesystem lookup only if needed.
    canonical={}
    for name in REQUIRED_EVIDENCE:
        prev=find_prev_evidence(name)
        src=prev[0] if prev else None
        provenance="STEP_072_PREVIOUS_EVIDENCE"
        if src is None:
            hits=search_plain(name)
            src=hits[0] if hits else None
            provenance="FILESYSTEM_EXACT_NAME"
        if src is None:
            report["evidence"][name]={"found":False}
            continue
        dst=evidence/name
        shutil.copy2(src,dst)
        canonical[name]=dst
        report["evidence"][name]={
            "found":True,
            "source":str(src),
            "provenance":provenance,
            "size":dst.stat().st_size,
            "sha256":sha256_file(dst),
        }

    missing=[n for n in REQUIRED_EVIDENCE if n not in canonical]
    report["required_evidence_missing"]=missing
    if missing:
        report["status"]="BLOCKED_MISSING_CORE_EVIDENCE"
        (out/"step072_fix1_report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
        raise SystemExit(4)

    # Recover historical first-mission builder from archived ZIPs if possible.
    hist=recover_historical(out)
    report["historical_campaign43a"]=hist

    # Structural validation of the actual 967 set.
    refs=parse_tsv(canonical["allstream_fstring_refs.tsv"])
    split=parse_tsv(canonical["campaign_final_apply_split.tsv"])
    glyph=parse_tsv(canonical["allstream_mdi_glyph_demand.tsv"])
    font=parse_tsv(canonical["allstream_font_objects.tsv"])

    compiled_ids={r["resource_id"] for r in split if r["final_apply_class"]=="COMPILED_MDI_PATCH"}
    movie_ids={r["resource_id"] for r in split if r["final_apply_class"]=="MOVIE_ST1_ALREADY_IN_STAGE43T_STATIC"}
    nonmdi_ids={r["resource_id"] for r in split if r["final_apply_class"]=="NON_MDI_INT_OR_RUNTIME_PATCH"}

    matched_ids=set()
    target_rows=[]
    target_mdis=set()
    confidence=Counter()
    for r in refs:
        ids=[x.strip() for x in re.split(r"[|,; ]+",r.get("resource_ids","")) if x.strip().startswith("BIA-")]
        hit=[x for x in ids if x in compiled_ids]
        if hit:
            matched_ids.update(hit)
            target_rows.append(r)
            target_mdis.add(r["mdi"])
            confidence[r.get("confidence","")]+=1

    glyph_by={r["mdi"]:r for r in glyph}
    glyph_missing=sorted(m for m in target_mdis if m not in glyph_by)
    glyph_not_fit=sorted(m for m in target_mdis if glyph_by.get(m,{}).get("fits_stage43a_60_slots")!="1")
    font_mdis={r["mdi"] for r in font}
    font_missing=sorted(target_mdis-font_mdis)

    base_src=canonical["bia_stage36_base.py"].read_text(encoding="utf-8-sig",errors="replace")
    helper_checks={
        "append_iso_file_and_repoint":"def append_iso_file_and_repoint" in base_src,
        "parse_mdi":"def parse_mdi" in base_src,
        "rebuild_mdi":"def rebuild_mdi" in base_src,
        "parse_dsx":"def parse_dsx" in base_src,
        "rebuild_dsx_from_logical":"def rebuild_dsx_from_logical" in base_src,
        "patch_dsl_descriptor":"def patch_dsl_descriptor" in base_src,
    }

    report["compiled967_validation"]={
        "compiled_ids":len(compiled_ids),
        "movie_ids":len(movie_ids),
        "nonmdi_ids":len(nonmdi_ids),
        "all_split_total":len(compiled_ids|movie_ids|nonmdi_ids),
        "matched_compiled_ids":len(matched_ids),
        "missing_compiled_ids":sorted(compiled_ids-matched_ids),
        "structural_reference_rows":len(target_rows),
        "target_mdis":len(target_mdis),
        "target_mdi_names":sorted(target_mdis),
        "confidence_counts":dict(confidence),
        "glyph_plan_missing_mdis":glyph_missing,
        "glyph_capacity_fail_mdis":glyph_not_fit,
        "font_object_missing_mdis":font_missing,
        "helper_checks":helper_checks,
    }

    hard_ok=(
        len(compiled_ids)==967 and
        len(matched_ids)==967 and
        len(target_rows)==2333 and
        len(target_mdis)==32 and
        not glyph_missing and
        not glyph_not_fit and
        not font_missing and
        all(helper_checks.values())
    )
    report["generalized_patcher_prerequisites_verified"]=hard_ok

    # Historical 43A source is useful as a reference, but no longer a hard block
    # because the structural refs, font plan and all ISO/MDI/DSX rebuild primitives
    # are independently present and validated.
    report["historical_43a_recovered"]=bool(hist.get("recovered_to"))
    report["historical_43a_required_for_next"]=False
    report["status"]="VERIFIED_READY_FOR_GENERALIZED_PATCHER" if hard_ok else "BLOCKED_STRUCTURAL_VALIDATION"

    (out/"step072_fix1_report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    (out/"STEP072_FIX1_SUMMARY.txt").write_text(
        "\n".join([
            f"STATUS={report['status']}",
            f"HISTORICAL_43A_RECOVERED={report['historical_43a_recovered']}",
            "HISTORICAL_43A_REQUIRED_FOR_NEXT=FALSE",
            f"COMPILED_IDS={len(compiled_ids)}",
            f"MATCHED_IDS={len(matched_ids)}",
            f"STRUCTURAL_REFERENCE_ROWS={len(target_rows)}",
            f"TARGET_MDIS={len(target_mdis)}",
            f"GLYPH_CAPACITY_FAILURES={len(glyph_not_fit)}",
            f"FONT_OBJECT_MISSING_MDIS={len(font_missing)}",
            f"HELPERS_COMPLETE={all(helper_checks.values())}",
            "ISO_MODIFIED=FALSE",
        ])+"\n",encoding="utf-8"
    )
    if not hard_ok:
        raise SystemExit(5)

if __name__=="__main__":
    main()
