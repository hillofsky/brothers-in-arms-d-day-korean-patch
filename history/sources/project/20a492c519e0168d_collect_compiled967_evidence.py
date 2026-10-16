#!/usr/bin/env python3
import csv, hashlib, json, os, shutil, sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT=Path(r"PROJECT_ROOT")
OUT=None

WANTED={
    "allstream_fstring_refs.tsv",
    "allstream_font_objects.tsv",
    "allstream_mdi_glyph_demand.tsv",
    "stage39a_font_plan.json",
    "build_campaign43a.py",
    "campaign_final_apply_split.tsv",
    "campaign_unapplied_ready_for_iso.tsv",
    "stage38_translation_units.tsv",
    "stage38_entry_map.tsv",
    "text_master.tsv",
    "bia_stage40i_actual_resource_trace.py",
    "bia_stage36_base.py",
    "nonmovie_92_refined.tsv",
    "movie_st1_lineage.tsv",
    "movie_st1_lineage_verified.tsv",
}

def sha256(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""):h.update(b)
    return h.hexdigest()

def read_tsv_info(p):
    info={"path":str(p),"rows":None,"columns":[],"classification_counts":{}}
    try:
        with p.open("r",encoding="utf-8-sig",errors="replace",newline="") as f:
            r=csv.DictReader(f,delimiter="\t")
            info["columns"]=r.fieldnames or []
            rows=list(r)
        info["rows"]=len(rows)
        for col in info["columns"]:
            lc=col.lower()
            if any(k in lc for k in ("class","type","status","bucket","split","category")):
                c=Counter((row.get(col) or "").strip() for row in rows)
                if 1 < len(c) <= 20:
                    info["classification_counts"][col]=dict(c.most_common())
        # Useful generic cardinalities.
        for col in info["columns"]:
            lc=col.lower()
            if lc in ("resource_id","mdi","mdi_file","file","source_file","target_mdi","filename"):
                vals={(row.get(col) or "").strip() for row in rows if (row.get(col) or "").strip()}
                info.setdefault("unique_values",{})[col]=len(vals)
    except Exception as e:
        info["error"]=repr(e)
    return info

def main():
    global OUT
    import argparse
    ap=argparse.ArgumentParser()
    ap.add_argument("--outdir",required=True)
    a=ap.parse_args()
    OUT=Path(a.outdir);OUT.mkdir(parents=True,exist_ok=True)
    ev=OUT/"evidence";ev.mkdir(exist_ok=True)

    found=[]
    # One bounded tree enumeration: PROJECT_ROOT only, filenames only.
    for dirpath, dirnames, filenames in os.walk(ROOT):
        # Skip massive generated/archive dirs that cannot contain authoritative analysis source?
        # Do NOT skip log/analysis/work because expected evidence can live there.
        for fn in filenames:
            if fn in WANTED:
                p=Path(dirpath)/fn
                found.append(p)

    manifest=[]
    name_counts=Counter(p.name for p in found)
    for i,p in enumerate(sorted(found,key=lambda x:str(x).lower()),1):
        rel=p.relative_to(ROOT)
        rec={
            "name":p.name,
            "path":str(p),
            "relative_path":str(rel),
            "size":p.stat().st_size,
            "mtime":p.stat().st_mtime,
            "sha256":sha256(p),
        }
        manifest.append(rec)
        safe=f"{i:03d}_{p.name}"
        shutil.copy2(p,ev/safe)
        rec["copied_as"]=safe

    (OUT/"source_manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    with (OUT/"source_manifest.tsv").open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=["name","path","relative_path","size","mtime","sha256","copied_as"],delimiter="\t")
        w.writeheader();w.writerows(manifest)

    per_name={n:[m for m in manifest if m["name"]==n] for n in sorted(WANTED)}
    summary={
        "step":"STEP_072",
        "status":"PRECHECK",
        "root":str(ROOT),
        "wanted_count":len(WANTED),
        "found_file_count":len(found),
        "found_name_count":sum(1 for n in WANTED if per_name[n]),
        "missing_names":[n for n in sorted(WANTED) if not per_name[n]],
        "duplicates":{n:len(v) for n,v in per_name.items() if len(v)>1},
        "source_iso":{},
        "tsv_profiles":[],
        "json_profiles":[],
        "python_profiles":[],
        "iso_modified":False,
    }

    # Hash baselines only; never copy/mutate the huge ISO.
    for key,path in {
        "stage69_fix2":ROOT/"BIA_STAGE69_FIX2_NONMDI_INT92_TEST.iso",
        "stage43t":ROOT/"BIA_STAGE43T_TITLE_PROMPT_FIX.iso",
    }.items():
        d={"path":str(path),"exists":path.exists()}
        if path.exists():
            d["size"]=path.stat().st_size
            d["sha256"]=sha256(path)
        summary["source_iso"][key]=d

    for m in manifest:
        p=ROOT/Path(m["relative_path"])
        if p.suffix.lower()==".tsv":
            summary["tsv_profiles"].append(read_tsv_info(p))
        elif p.suffix.lower()==".json":
            try:
                obj=json.loads(p.read_text(encoding="utf-8-sig",errors="replace"))
                profile={"path":str(p),"type":type(obj).__name__}
                if isinstance(obj,dict):
                    profile["top_keys"]=list(obj)[:100]
                elif isinstance(obj,list):
                    profile["length"]=len(obj)
                summary["json_profiles"].append(profile)
            except Exception as e:
                summary["json_profiles"].append({"path":str(p),"error":repr(e)})
        elif p.suffix.lower()==".py":
            txt=p.read_text(encoding="utf-8-sig",errors="replace")
            funcs=[]
            for line in txt.splitlines():
                s=line.lstrip()
                if s.startswith("def "):
                    funcs.append(s.split("(",1)[0][4:])
            summary["python_profiles"].append({
                "path":str(p),
                "functions":funcs[:300],
                "has_append_iso_file_and_repoint":"append_iso_file_and_repoint" in txt,
                "has_rebuild_mdi":"rebuild_mdi" in txt,
                "has_rebuild_dsx":"rebuild_dsx" in txt,
                "has_parse_mdi":"parse_mdi" in txt,
            })

    # Hard requirements for building the generalized 967 patcher next.
    required=[
        "allstream_fstring_refs.tsv",
        "allstream_font_objects.tsv",
        "allstream_mdi_glyph_demand.tsv",
        "stage39a_font_plan.json",
        "build_campaign43a.py",
        "campaign_final_apply_split.tsv",
        "stage38_translation_units.tsv",
        "stage38_entry_map.tsv",
        "bia_stage40i_actual_resource_trace.py",
    ]
    summary["required_for_next"]=required
    summary["required_missing"]=[n for n in required if not per_name[n]]

    # Soft assertions from the already-known project state. These are evidence checks,
    # not reasons to mutate anything.
    split_profiles=[x for x in summary["tsv_profiles"] if Path(x["path"]).name=="campaign_final_apply_split.tsv"]
    expected={}
    for x in split_profiles:
        expected[x["path"]]={
            "rows":x.get("rows"),
            "columns":x.get("columns"),
            "classification_counts":x.get("classification_counts"),
            "unique_values":x.get("unique_values",{}),
        }
    summary["campaign_split_observed"]=expected

    summary["status"]="READY_FOR_GENERALIZED_PATCHER" if not summary["required_missing"] else "BLOCKED_MISSING_EVIDENCE"
    (OUT/"step072_report.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")

    lines=[
        f"STATUS={summary['status']}",
        f"FOUND_FILES={summary['found_file_count']}",
        f"FOUND_NAMES={summary['found_name_count']}/{summary['wanted_count']}",
        "MISSING_REQUIRED="+",".join(summary["required_missing"]),
        "ISO_MODIFIED=FALSE",
    ]
    (OUT/"STEP072_SUMMARY.txt").write_text("\n".join(lines)+"\n",encoding="utf-8")

    if summary["required_missing"]:
        raise SystemExit(4)

if __name__=="__main__":
    main()
