#!/usr/bin/env python3
from pathlib import Path
import argparse,csv,json,re,collections,shutil,hashlib
ap=argparse.ArgumentParser()
ap.add_argument("--root",required=True)
ap.add_argument("--mapping",required=True)
ap.add_argument("--out",required=True)
a=ap.parse_args()

root=Path(a.root);out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
master=root/"translation"/"text_master.tsv"
current=root/"translation"/"campaign_next_translation.tsv"
mapping=json.loads(Path(a.mapping).read_text(encoding="utf-8"))

def read(p):
    with p.open("r",encoding="utf-8-sig",newline="") as f:
        rd=csv.DictReader(f,delimiter="\t")
        return rd.fieldnames,list(rd)

fields,mrows=read(master)
bfields,brows=read(current)
idx={r["resource_id"]:r for r in mrows}
trans={x["resource_id"]:x for x in mapping["translations"]}

if len(trans)!=119:
    raise RuntimeError(f"Expected 119 Bookends translations, got {len(trans)}")
if len(brows)!=43:
    raise RuntimeError(f"Current D15_1130 batch should contain 43 rows, got {len(brows)}")
if not {r["resource_id"] for r in brows}.issubset(set(trans)):
    raise RuntimeError("Current D15_1130 batch is not a subset of STEP_061 mapping")

before=collections.Counter(r["status"] for r in mrows if r.get("category")=="campaign")
expected={"VERIFIED_APPLIED":137,"TRANSLATED_PENDING_APPLY":90,"TRANSLATED_REVIEWED":794,"NEEDS_TRANSLATION":281}
for k,v in expected.items():
    if before[k]!=v:
        raise RuntimeError(f"STEP_061 pre-state mismatch {k}: {before[k]} != {v}")

shutil.copy2(master,out/"text_master_BEFORE.tsv")
shutil.copy2(current,out/"campaign_next_translation_BEFORE.tsv")

book_groups=["D15_1130_BOOKENDS","D15_1230_BOOKENDS2","D15_1300_BOOKENDS4","D15_1330_BOOKENDS3"]
for rid,t in trans.items():
    if rid not in idx:
        raise RuntimeError(f"Missing master ID {rid}")
    mr=idx[rid]
    if mr["status"]!="NEEDS_TRANSLATION":
        raise RuntimeError(f"{rid} status={mr['status']}")
    if mr["source_text"]!=t["source_text"]:
        raise RuntimeError(f"Source mismatch {rid}")
    if not any(g in mr.get("references","") for g in book_groups):
        raise RuntimeError(f"Bookends reference missing {rid}")
    mr["ko_current"]=t["ko_current"]
    mr["ko_review"]=t["ko_review"]
    mr["status"]="TRANSLATED_REVIEWED"
    n=mr.get("notes","")
    mr["notes"]=(n+"; " if n else "")+"STEP_061 reviewed; all Bookends parts; ISO not yet applied."

tmp=master.with_suffix(".tmp")
with tmp.open("w",encoding="utf-8-sig",newline="") as f:
    w=csv.DictWriter(f,fieldnames=fields,delimiter="\t",lineterminator="\n")
    w.writeheader();w.writerows(mrows)
tmp.replace(master)

after=collections.Counter(r["status"] for r in mrows if r.get("category")=="campaign")
expected2={"VERIFIED_APPLIED":137,"TRANSLATED_PENDING_APPLY":90,"TRANSLATED_REVIEWED":913,"NEEDS_TRANSLATION":162}
for k,v in expected2.items():
    if after[k]!=v:
        raise RuntimeError(f"STEP_061 post-state mismatch {k}: {after[k]} != {v}")
if sum(after.values())!=1302:
    raise RuntimeError(f"Campaign total changed: {sum(after.values())}")

left_book=[
    r["resource_id"] for r in mrows
    if r.get("status")=="NEEDS_TRANSLATION"
    and any(g in r.get("references","") for g in book_groups)
]
if left_book:
    raise RuntimeError(f"Bookends still has untranslated IDs: {left_book}")

subset=[r for r in mrows if r["resource_id"] in trans]
with (out/"D15_BOOKENDS_ALL_PARTS_KO_reviewed.tsv").open("w",encoding="utf-8-sig",newline="") as f:
    w=csv.DictWriter(f,fieldnames=fields,delimiter="\t",lineterminator="\n")
    w.writeheader();w.writerows(subset)

# After the four final story groups, export every remaining campaign row.
# They are skirmish/system campaign strings, not chronological Dxx story groups.
remaining=[
    r for r in mrows
    if r.get("category")=="campaign" and r.get("status")=="NEEDS_TRANSLATION"
]
if len(remaining)!=162:
    raise RuntimeError(f"Unexpected final campaign remainder: {len(remaining)} != 162")

dpat=re.compile(r'(?<![A-Z0-9])((D0?\d{1,2})_(\d{4})_[A-Z0-9_]+)(?=:)',re.I)
story_left=[r["resource_id"] for r in remaining if dpat.search(r.get("references",""))]
if story_left:
    raise RuntimeError(f"Unexpected chronological story refs remain: {story_left[:20]}")

with current.open("w",encoding="utf-8-sig",newline="") as f:
    w=csv.DictWriter(f,fieldnames=fields,delimiter="\t",lineterminator="\n")
    w.writeheader();w.writerows(remaining)

shutil.copy2(master,out/"text_master_AFTER.tsv")
shutil.copy2(current,out/"campaign_next_translation.tsv")
with (out/"campaign_remaining_skirmish_system.tsv").open("w",encoding="utf-8-sig",newline="") as f:
    w=csv.DictWriter(f,fieldnames=fields,delimiter="\t",lineterminator="\n")
    w.writeheader();w.writerows(remaining)

report={
    "step":"STEP_061",
    "translations_applied_to_metadata":119,
    "completed_reference_groups":book_groups,
    "status_counts":dict(after),
    "chronological_story_groups_remaining":0,
    "next_pool":"SKIRMISH_AND_SYSTEM_CAMPAIGN_REMAINDER",
    "next_unit_count":len(remaining),
    "master_sha256":hashlib.sha256(master.read_bytes()).hexdigest(),
    "next_batch_sha256":hashlib.sha256(current.read_bytes()).hexdigest(),
    "iso_modified":False,
    "movie_validation_resumed":False
}
(out/"step061_report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(report,ensure_ascii=False))
