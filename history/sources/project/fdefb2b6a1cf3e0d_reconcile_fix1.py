#!/usr/bin/env python3
from pathlib import Path
import csv,json,re,collections,hashlib,importlib.util,sys

ROOT=Path(r"PROJECT_ROOT")
OUT=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/"log"/"STEP_068_FIX1"/"outputs"
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
        rd=csv.DictReader(f,delimiter="\t");return rd.fieldnames,list(rd)

def write_tsv(p,fields,rows):
    with p.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields,delimiter="\t",lineterminator="\n",extrasaction="ignore")
        w.writeheader();w.writerows(rows)

def norm(s):
    # ST1 uses "\" as an on-screen line separator. For transcript identity
    # comparisons it is whitespace, not semantic text.
    s=(s or "").replace("\\"," ").replace("\r"," ").replace("\n"," ")
    return re.sub(r"\s+"," ",s).strip()

def segments(s):
    return [re.sub(r"\s+"," ",x).strip() for x in (s or "").split("\\") if re.sub(r"\s+"," ",x).strip()]

def sha256(data):
    return hashlib.sha256(data).hexdigest()

rep67=json.loads((STEP67/"step067_report.json").read_text(encoding="utf-8"))
if rep67["input_unresolved_ids"]!=198:
    raise RuntimeError(f"STEP067 input mismatch: {rep67['input_unresolved_ids']}")

class_fields,class_rows=read_tsv(STEP67/"unresolved_198_classification.tsv")
if len(class_rows)!=198:
    raise RuntimeError(f"Expected 198 STEP067 rows, got {len(class_rows)}")

mf,mrows=read_tsv(MASTER)
all_unap=[
    r for r in mrows
    if r.get("category")=="campaign"
    and r.get("status") in ("TRANSLATED_PENDING_APPLY","TRANSLATED_REVIEWED")
]
if len(all_unap)!=1165:
    raise RuntimeError(f"Expected 1165 unapplied campaign IDs, got {len(all_unap)}")

movf,movie_rows=read_tsv(MOVIE_TSV)
if len(movie_rows)!=133:
    raise RuntimeError(f"Expected 133 Stage42A movie fields, got {len(movie_rows)}")
movie_files=sorted({r["file"] for r in movie_rows})
if len(movie_files)!=8:
    raise RuntimeError(f"Expected 8 movie ST1 files, got {len(movie_files)}")

# ------------------------------------------------------------------
# Corrected movie crosswalk.
# STEP068 failed because it hard-coded 71 from broad history evidence.
# Actual correspondence must be derived from the 133 real ST1 fields.
# ------------------------------------------------------------------
movie_cross=[]
movie_ids=set()
for row in class_rows:
    rid=row["resource_id"];srcn=norm(row["source_text"])
    if not srcn: continue
    for mr in movie_rows:
        en=norm(mr["english"])
        if not en: continue
        segs=segments(mr["english"])
        if srcn==en:
            kind="FIELD_EQUAL"
        elif srcn in segs:
            kind="SEGMENT_EQUAL"
        elif srcn in en or en in srcn:
            # Valid for wrapped dialogue and title-card compound fields.
            kind="NORMALIZED_CONTAINMENT"
        else:
            continue
        movie_ids.add(rid)
        movie_cross.append({
            "resource_id":rid,
            "source_text":row["source_text"],
            "korean":row["korean"],
            "movie_file":mr["file"],
            "field_index":mr["field_index"],
            "time_start":mr["time_start"],
            "time_end":mr["time_end"],
            "movie_english":mr["english"],
            "match_kind":kind,
        })

if len(movie_ids)!=106:
    raise RuntimeError(f"Corrected movie overlap changed unexpectedly: {len(movie_ids)} != 106")

kind_counts=collections.Counter(x["match_kind"] for x in movie_cross)
write_tsv(
    OUT/"movie_campaign_crosswalk_106.tsv",
    ["resource_id","source_text","korean","movie_file","field_index","time_start","time_end","movie_english","match_kind"],
    movie_cross
)

# ------------------------------------------------------------------
# Prove Stage42H movie bytes are preserved in Stage43T.
# ------------------------------------------------------------------
sp=importlib.util.spec_from_file_location("biahelper",HELPER)
mod=importlib.util.module_from_spec(sp);sp.loader.exec_module(mod)
_,b=mod.load_helpers()

lineage=[]
all_equal=True
all_changed=True
for name in movie_files:
    blobs={}
    rec={"file":name}
    for label,iso in [("original",ORIGINAL),("stage42h",MOVIE_BASE),("stage43t",CURRENT)]:
        _,blob=b.iso_read_file(iso,PARTS+[name])
        blobs[label]=blob
        rec[label+"_sha256"]=sha256(blob)
        rec[label+"_size"]=len(blob)
    eq=blobs["stage42h"]==blobs["stage43t"]
    changed=blobs["original"]!=blobs["stage42h"]
    rec["stage42h_equals_stage43t"]=int(eq)
    rec["stage42h_differs_from_original"]=int(changed)
    all_equal &= eq
    all_changed &= changed
    lineage.append(rec)

if not all_equal:
    raise RuntimeError("One or more Stage43T ST1 files differ from Stage42H")
if not all_changed:
    raise RuntimeError("One or more Stage42H ST1 files do not differ from original")

write_tsv(
    OUT/"movie_st1_lineage.tsv",
    ["file","original_sha256","original_size","stage42h_sha256","stage42h_size",
     "stage43t_sha256","stage43t_size","stage42h_equals_stage43t","stage42h_differs_from_original"],
    lineage
)

# ------------------------------------------------------------------
# Refine the actual non-movie remainder: 198 - 106 = 92.
# ------------------------------------------------------------------
plan=json.loads(PLAN.read_text(encoding="utf-8"))
basechars={x["char"] for x in plan["layout"]}
nonmovie_rows=[]
refined_counts=collections.Counter()

for row in class_rows:
    rid=row["resource_id"]
    if rid in movie_ids:
        continue
    ko=row["korean"]
    extra=sorted({c for c in ko if ord(c)>127 and c not in basechars})
    mdi_key_count=int(row["mdi_key_hit_count"])
    raw_paths=[x for x in row["raw_non_int_paths"].split(";") if x]
    meaningful_non_int=[p for p in raw_paths if not re.search(r"/(DEU|FRA|ESP|ITA)/",p,re.I)]
    if mdi_key_count>0:
        refined="DYNAMIC_INT_KEY_CANDIDATE"
    elif meaningful_non_int:
        refined="NON_INT_RUNTIME_ASSET_CANDIDATE"
    else:
        refined="INT_ONLY_OR_UNUSED_CANDIDATE"
    refined_counts[refined]+=1
    out=dict(row)
    out.update({
        "refined_classification":refined,
        "meaningful_non_int_paths":";".join(meaningful_non_int),
        "additional_chars_vs_stage39":"".join(extra),
        "additional_char_count_vs_stage39":len(extra),
    })
    nonmovie_rows.append(out)

if len(nonmovie_rows)!=92:
    raise RuntimeError(f"Expected corrected nonmovie remainder 92, got {len(nonmovie_rows)}")

write_tsv(
    OUT/"nonmovie_92_refined.tsv",
    list(class_fields)+[
        "refined_classification","meaningful_non_int_paths",
        "additional_chars_vs_stage39","additional_char_count_vs_stage39"
    ],
    nonmovie_rows
)

# Source INT groups for the future direct/dynamic INT patch phase.
grouped=collections.defaultdict(list)
for r in nonmovie_rows:
    for f in [x for x in r["source_files"].split(";") if x]:
        grouped[f].append(r)
group_rows=[]
for f,rr in sorted(grouped.items()):
    cc=collections.Counter(x["refined_classification"] for x in rr)
    chars=sorted({c for x in rr for c in x["additional_chars_vs_stage39"]})
    group_rows.append({
        "source_file":f,
        "unique_ids":len({x["resource_id"] for x in rr}),
        "refined_classes_json":json.dumps(cc,ensure_ascii=False),
        "additional_chars_vs_stage39":"".join(chars),
        "additional_char_count_vs_stage39":len(chars),
    })
write_tsv(
    OUT/"nonmovie_source_groups.tsv",
    ["source_file","unique_ids","refined_classes_json","additional_chars_vs_stage39","additional_char_count_vs_stage39"],
    group_rows
)

# ------------------------------------------------------------------
# Final 1165 split: compiled 967 + movie 106 + nonmovie 92.
# ------------------------------------------------------------------
covf,covrows=read_tsv(STEP66/"allstream_id_coverage.tsv")
compiled_ids={r["resource_id"] for r in covrows if int(r["all_structural_refs"])>0}
nonmovie_ids={r["resource_id"] for r in nonmovie_rows}

if len(compiled_ids)!=967:
    raise RuntimeError(f"Expected 967 compiled IDs, got {len(compiled_ids)}")
if compiled_ids & movie_ids or compiled_ids & nonmovie_ids or movie_ids & nonmovie_ids:
    raise RuntimeError("Final apply split sets overlap")
if len(compiled_ids|movie_ids|nonmovie_ids)!=1165:
    raise RuntimeError("Final apply split does not cover 1165 IDs")

manifest=[]
for r in all_unap:
    rid=r["resource_id"]
    if rid in compiled_ids:
        cls="COMPILED_MDI_PATCH"
    elif rid in movie_ids:
        cls="MOVIE_ST1_ALREADY_IN_STAGE43T_STATIC"
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

report={
    "step":"STEP_068_FIX1",
    "status":"VERIFIED",
    "failure_fixed":"STEP068 incorrectly hard-coded movie overlap=71; actual Stage42A ST1-derived overlap=106",
    "input_unapplied_campaign_ids":1165,
    "compiled_mdi_patch_ids":len(compiled_ids),
    "movie_st1_campaign_ids":len(movie_ids),
    "movie_crosswalk_rows":len(movie_cross),
    "movie_crosswalk_match_kinds":dict(kind_counts),
    "nonmovie_remaining_ids":len(nonmovie_ids),
    "nonmovie_refined_counts":dict(refined_counts),
    "stage42h_equals_stage43t_all8_st1":all_equal,
    "stage42h_differs_from_original_all8_st1":all_changed,
    "movie_static_lineage_proven":bool(all_equal and all_changed),
    "movie_playback_validation_resumed":False,
    "iso_modified":False,
    "next_phase":"BUILD_COMPILED_967_PLUS_NONMOVIE_92_PATCHER_PRESERVE_MOVIE106",
}
(OUT/"step068_fix1_report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")

(OUT/"STEP068_FIX1_README.txt").write_text(f"""STEP_068 FIX1 complete.

Original failure:
- incorrect hard-coded expected movie overlap: 71
- actual overlap derived from Stage42A 133 real ST1 fields: {len(movie_ids)}

Correct final split:
- compiled MDI patch IDs: {len(compiled_ids)}
- movie ST1 IDs already present in Stage43T static lineage: {len(movie_ids)}
- non-MDI / INT-runtime IDs: {len(nonmovie_ids)}

Non-MDI classes:
{json.dumps(dict(refined_counts),ensure_ascii=False,indent=2)}

All 8 Stage42H ST1 files are byte-identical to Stage43T and all 8 differ from
the original ISO.

No ISO was modified.
No deferred movie playback validation was resumed.
""",encoding="utf-8")

print(json.dumps(report,ensure_ascii=False))
