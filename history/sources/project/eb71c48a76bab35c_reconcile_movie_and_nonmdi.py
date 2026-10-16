#!/usr/bin/env python3
from pathlib import Path
import csv,json,re,collections,hashlib,importlib.util,sys,shutil

ROOT=Path(r"PROJECT_ROOT")
OUT=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/"log"/"STEP_068"/"outputs"
OUT.mkdir(parents=True,exist_ok=True)

CURRENT=ROOT/"BIA_STAGE43T_TITLE_PROMPT_FIX.iso"
MOVIE_BASE=ROOT/"BIA_STAGE42H_ALL8_MOVIES_512_TEST.iso"
ORIGINAL=ROOT/"Brothers in Arms - D-Day (USA) (v1.01).iso"
MASTER=ROOT/"translation"/"text_master.tsv"
STEP67=ROOT/"log"/"STEP_067"/"outputs"
STEP66=ROOT/"log"/"STEP_066"/"outputs"
MOVIE_TSV=ROOT/"analysis"/"stage42a_movie_st1_sweep"/"movie_subtitles.tsv"
PLAN=ROOT/"bia_stage39a_tools"/"stage39a_font_plan.json"
HELPER=ROOT/"bia_stage40i_tools"/"bia_stage40i_actual_resource_trace.py"
PARTS=["PSP_GAME","USRDIR","SYSTEM"]

def read_tsv(p):
    with p.open("r",encoding="utf-8-sig",newline="") as f:
        rd=csv.DictReader(f,delimiter="\t")
        return rd.fieldnames,list(rd)

def write_tsv(p,fields,rows):
    with p.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields,delimiter="\t",lineterminator="\n",extrasaction="ignore")
        w.writeheader();w.writerows(rows)

def norm(s):
    s=(s or "").replace("\\"," ").replace("\r"," ").replace("\n"," ")
    return re.sub(r"\s+"," ",s).strip()

def sha256(data):
    return hashlib.sha256(data).hexdigest()

def hangul_count(data):
    t=data.decode("utf-8",errors="ignore")
    return sum(1 for c in t if 0xAC00<=ord(c)<=0xD7A3)

rep67=json.loads((STEP67/"step067_report.json").read_text(encoding="utf-8"))
if rep67["input_unresolved_ids"]!=198:
    raise RuntimeError(f"STEP067 input mismatch: {rep67['input_unresolved_ids']}")
class_fields,class_rows=read_tsv(STEP67/"unresolved_198_classification.tsv")
if len(class_rows)!=198:
    raise RuntimeError(f"Expected 198 classification rows, got {len(class_rows)}")

mf,mrows=read_tsv(MASTER)
mby={r["resource_id"]:r for r in mrows}
all_unap=[
    r for r in mrows
    if r.get("category")=="campaign"
    and r.get("status") in ("TRANSLATED_PENDING_APPLY","TRANSLATED_REVIEWED")
]
if len(all_unap)!=1165:
    raise RuntimeError(f"Expected 1165 unapplied campaign IDs, got {len(all_unap)}")

movf,movie_rows=read_tsv(MOVIE_TSV)
if len(movie_rows)!=133:
    raise RuntimeError(f"Expected 133 Stage42A movie subtitle fields, got {len(movie_rows)}")
movie_files=sorted({r["file"] for r in movie_rows})
if len(movie_files)!=8:
    raise RuntimeError(f"Expected 8 movie ST1 files, got {len(movie_files)}")

# --------------------------------------------------------------------
# Exact campaign-ID -> Stage42A movie field crosswalk.
# "movie evidence" from STEP067 was intentionally broad; this pass only
# accepts normalized exact-substring overlap against the actual ST1 field.
# --------------------------------------------------------------------
movie_cross=[]
exact_movie_ids=set()
for row in class_rows:
    rid=row["resource_id"];src=norm(row["source_text"])
    matches=[]
    for mr in movie_rows:
        e=norm(mr["english"])
        if src and (src in e or e in src):
            matches.append(mr)
    for mr in matches:
        movie_cross.append({
            "resource_id":rid,
            "source_text":row["source_text"],
            "korean":row["korean"],
            "movie_file":mr["file"],
            "field_index":mr["field_index"],
            "time_start":mr["time_start"],
            "time_end":mr["time_end"],
            "movie_english":mr["english"],
            "match_kind":"NORMALIZED_SUBSTRING",
        })
    if matches:
        exact_movie_ids.add(rid)

write_tsv(
    OUT/"movie_exact_campaign_crosswalk.tsv",
    ["resource_id","source_text","korean","movie_file","field_index","time_start","time_end","movie_english","match_kind"],
    movie_cross
)

# --------------------------------------------------------------------
# Static lineage verification:
# compare all eight ST1 files in original -> Stage42H -> Stage43T.
# Stage43A historical script used Stage42H as its source ISO, so equality
# between Stage42H and Stage43T proves later campaign stages preserved bytes.
# --------------------------------------------------------------------
sp=importlib.util.spec_from_file_location("biahelper",HELPER)
mod=importlib.util.module_from_spec(sp);sp.loader.exec_module(mod)
_,b=mod.load_helpers()

lineage=[]
all_current_equal_moviebase=True
all_moviebase_modified_from_original=True
for name in movie_files:
    rec={"file":name}
    blobs={}
    for label,iso in [("original",ORIGINAL),("stage42h",MOVIE_BASE),("stage43t",CURRENT)]:
        if not iso.exists():
            rec[label+"_exists"]=0
            rec[label+"_sha256"]=""
            rec[label+"_size"]=0
            rec[label+"_hangul_bytes_decoded_count"]=0
            blobs[label]=None
            continue
        try:
            _,blob=b.iso_read_file(iso,PARTS+[name])
            blobs[label]=blob
            rec[label+"_exists"]=1
            rec[label+"_sha256"]=sha256(blob)
            rec[label+"_size"]=len(blob)
            rec[label+"_hangul_bytes_decoded_count"]=hangul_count(blob)
        except Exception:
            blobs[label]=None
            rec[label+"_exists"]=0
            rec[label+"_sha256"]=""
            rec[label+"_size"]=0
            rec[label+"_hangul_bytes_decoded_count"]=0
    eq=(blobs["stage42h"] is not None and blobs["stage43t"] is not None and blobs["stage42h"]==blobs["stage43t"])
    modified=(blobs["original"] is not None and blobs["stage42h"] is not None and blobs["original"]!=blobs["stage42h"])
    rec["stage42h_equals_stage43t"]=int(eq)
    rec["stage42h_differs_from_original"]=int(modified)
    all_current_equal_moviebase &= eq
    all_moviebase_modified_from_original &= modified
    lineage.append(rec)

write_tsv(
    OUT/"movie_st1_lineage.tsv",
    ["file",
     "original_exists","original_sha256","original_size","original_hangul_bytes_decoded_count",
     "stage42h_exists","stage42h_sha256","stage42h_size","stage42h_hangul_bytes_decoded_count",
     "stage43t_exists","stage43t_sha256","stage43t_size","stage43t_hangul_bytes_decoded_count",
     "stage42h_equals_stage43t","stage42h_differs_from_original"],
    lineage
)

# --------------------------------------------------------------------
# Recover focused historical Stage42H evidence and Stage43A lineage scripts.
# --------------------------------------------------------------------
terms=[
    "BIA_STAGE42H_ALL8_MOVIES_512_TEST.iso",
    "STAGE42H",
    "ALL8_MOVIES",
    "movie_subtitles.tsv",
    "EM_1230_BOOKENDS2.ST1",
    "EM_VICTORYINCARETAN.ST1",
]
text_exts={".py",".ps1",".json",".md",".txt",".tsv",".csv"}
evidence=[]
evdir=OUT/"movie_pipeline_evidence"
evdir.mkdir(exist_ok=True)
seen=set();copied_bytes=0

for base in [ROOT/"work",ROOT/"analysis",ROOT/"log"]:
    if not base.exists():continue
    for p in base.rglob("*"):
        try:
            if not p.is_file() or p.suffix.lower() not in text_exts or p.stat().st_size>20*1024*1024:
                continue
            data=p.read_bytes()
            text=data.decode("utf-8-sig",errors="replace")
            hits=[t for t in terms if t.lower() in text.lower() or t.lower() in p.name.lower()]
            if not hits:continue
            rel=str(p.relative_to(ROOT))
            h=sha256(data)
            evidence.append({"path":rel,"size":len(data),"terms":";".join(hits),"sha256":h})
            if h not in seen and len(data)<=5*1024*1024 and copied_bytes+len(data)<=40*1024*1024:
                seen.add(h);copied_bytes+=len(data)
                safe=re.sub(r'[^A-Za-z0-9._\-가-힣]+','_',rel)
                if len(safe)>220:safe=safe[-220:]
                (evdir/safe).write_bytes(data)
        except Exception:
            pass

write_tsv(OUT/"movie_pipeline_evidence.tsv",["path","size","terms","sha256"],evidence)

# --------------------------------------------------------------------
# Refine remaining 127: preserve STEP067 evidence, but movie classification
# now requires a real Stage42A subtitle field match.
# --------------------------------------------------------------------
plan=json.loads(PLAN.read_text(encoding="utf-8"))
basechars={x["char"] for x in plan["layout"]}
nonmovie_rows=[]
refined_counts=collections.Counter()

for row in class_rows:
    rid=row["resource_id"]
    if rid in exact_movie_ids:
        continue
    ko=row["korean"]
    extra=sorted({c for c in ko if ord(c)>127 and c not in basechars})
    mdi_key_count=int(row["mdi_key_hit_count"])
    raw_paths=[x for x in row["raw_non_int_paths"].split(";") if x]
    # Foreign localization copies are evidence of text duplication, not the
    # runtime English source. Retain only English/runtime binary/config assets.
    meaningful_non_int=[
        p for p in raw_paths
        if not re.search(r"/(DEU|FRA|ESP|ITA)/",p,re.I)
    ]
    if mdi_key_count>0:
        refined="DYNAMIC_INT_KEY_CANDIDATE"
    elif meaningful_non_int:
        refined="NON_INT_RUNTIME_ASSET_CANDIDATE"
    else:
        refined="INT_ONLY_OR_UNUSED_CANDIDATE"
    refined_counts[refined]+=1
    nonmovie_rows.append({
        **row,
        "refined_classification":refined,
        "meaningful_non_int_paths":";".join(meaningful_non_int),
        "additional_chars_vs_stage39":"".join(extra),
        "additional_char_count_vs_stage39":len(extra),
    })

write_tsv(
    OUT/"nonmovie_127_refined.tsv",
    list(class_fields)+[
        "refined_classification","meaningful_non_int_paths",
        "additional_chars_vs_stage39","additional_char_count_vs_stage39"
    ],
    nonmovie_rows
)

# Group the 127 by source INT so the direct-INT patch stage can operate safely.
grouped=collections.defaultdict(list)
for r in nonmovie_rows:
    for f in [x for x in r["source_files"].split(";") if x]:
        grouped[f].append(r)

group_rows=[]
for f,rr in sorted(grouped.items()):
    ids={x["resource_id"] for x in rr}
    cc=collections.Counter(x["refined_classification"] for x in rr)
    chars=sorted({c for x in rr for c in x["additional_chars_vs_stage39"]})
    group_rows.append({
        "source_file":f,
        "unique_ids":len(ids),
        "refined_classes_json":json.dumps(cc,ensure_ascii=False),
        "additional_chars_vs_stage39":"".join(chars),
        "additional_char_count_vs_stage39":len(chars),
    })
write_tsv(
    OUT/"nonmovie_source_groups.tsv",
    ["source_file","unique_ids","refined_classes_json","additional_chars_vs_stage39","additional_char_count_vs_stage39"],
    group_rows
)

# --------------------------------------------------------------------
# Final split of the original 1165 unapplied rows.
# 967 compiled IDs are proven by STEP066.
# 71 exact movie ST1 IDs are statically reconciled here.
# 127 remain for INT/non-MDI treatment.
# --------------------------------------------------------------------
resolved_compiled=set()
covf,covrows=read_tsv(STEP66/"allstream_id_coverage.tsv")
for r in covrows:
    if int(r["all_structural_refs"])>0:
        resolved_compiled.add(r["resource_id"])
if len(resolved_compiled)!=967:
    raise RuntimeError(f"Expected 967 compiled IDs, got {len(resolved_compiled)}")

nonmovie_ids={r["resource_id"] for r in nonmovie_rows}
if len(exact_movie_ids)!=71:
    raise RuntimeError(f"Expected refined exact movie set of 71, got {len(exact_movie_ids)}")
if len(nonmovie_ids)!=127:
    raise RuntimeError(f"Expected refined nonmovie set of 127, got {len(nonmovie_ids)}")
if resolved_compiled & exact_movie_ids or resolved_compiled & nonmovie_ids or exact_movie_ids & nonmovie_ids:
    raise RuntimeError("Final split sets overlap")
if len(resolved_compiled|exact_movie_ids|nonmovie_ids)!=1165:
    raise RuntimeError("Final split does not cover 1165 IDs")

manifest=[]
for r in all_unap:
    rid=r["resource_id"]
    if rid in resolved_compiled:
        cls="COMPILED_MDI_PATCH"
    elif rid in exact_movie_ids:
        cls="MOVIE_ST1_ALREADY_IN_BUILD_STATIC_CHECK"
    elif rid in nonmovie_ids:
        cls="NON_MDI_INT_OR_RUNTIME_PATCH"
    else:
        raise RuntimeError(f"Unclassified ID {rid}")
    manifest.append({
        "resource_id":rid,
        "status":r["status"],
        "source_text":r["source_text"],
        "korean":r.get("ko_review") or r.get("ko_current"),
        "final_apply_class":cls,
    })

write_tsv(
    OUT/"campaign_final_apply_split.tsv",
    ["resource_id","status","source_text","korean","final_apply_class"],
    manifest
)

movie_static_proven=bool(all_current_equal_moviebase and all_moviebase_modified_from_original)
report={
    "step":"STEP_068",
    "status":"VERIFIED",
    "input_unapplied_campaign_ids":1165,
    "compiled_mdi_patch_ids":len(resolved_compiled),
    "step067_movie_evidence_ids":rep67["ids_with_movie_history_evidence"],
    "exact_stage42a_movie_ids":len(exact_movie_ids),
    "movie_false_positive_ids":rep67["ids_with_movie_history_evidence"]-len(exact_movie_ids),
    "nonmovie_remaining_ids":len(nonmovie_ids),
    "nonmovie_refined_counts":dict(refined_counts),
    "movie_files":movie_files,
    "stage42h_iso_exists":MOVIE_BASE.exists(),
    "stage42h_equals_stage43t_all8_st1":bool(all_current_equal_moviebase),
    "stage42h_differs_from_original_all8_st1":bool(all_moviebase_modified_from_original),
    "movie_static_lineage_proven":movie_static_proven,
    "movie_playback_validation_resumed":False,
    "iso_modified":False,
    "next_phase":"BUILD_COMPILED_967_PLUS_NONMOVIE_127_PATCHER_WITH_MOVIE71_PRESERVED",
}
(OUT/"step068_report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")

(OUT/"STEP068_README.txt").write_text(f"""STEP_068 reconciliation complete.

Final 1165-ID split:
- compiled MDI patch: {len(resolved_compiled)}
- exact Stage42A movie subtitle overlap: {len(exact_movie_ids)}
- non-MDI / INT-runtime remainder: {len(nonmovie_ids)}

Movie lineage:
- Stage42H exists: {MOVIE_BASE.exists()}
- all 8 Stage42H ST1 == Stage43T ST1: {all_current_equal_moviebase}
- all 8 Stage42H ST1 differ from original: {all_moviebase_modified_from_original}

No ISO was modified.
No deferred movie playback validation was resumed.
""",encoding="utf-8")
print(json.dumps(report,ensure_ascii=False))
