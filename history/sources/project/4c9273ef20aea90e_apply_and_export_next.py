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
bidx={r["resource_id"]:r for r in brows}
trans={x["resource_id"]:x for x in mapping["translations"]}

if len(trans)!=77:
    raise RuntimeError(f"Expected 77 translations, got {len(trans)}")
if len(brows)!=75:
    raise RuntimeError(f"Current STEP_053-exported batch should contain 75 rows, got {len(brows)}")
if not set(bidx).issubset(set(trans)):
    raise RuntimeError("Current batch is not a subset of STEP_054 mapping")

extras=set(trans)-set(bidx)
if extras!={"BIA-01748","BIA-02365"}:
    raise RuntimeError(f"Unexpected Part-2-only ID set: {sorted(extras)}")

before=collections.Counter(r["status"] for r in mrows if r.get("category")=="campaign")
expected={"VERIFIED_APPLIED":137,"TRANSLATED_PENDING_APPLY":90,"TRANSLATED_REVIEWED":465,"NEEDS_TRANSLATION":610}
for k,v in expected.items():
    if before[k]!=v:
        raise RuntimeError(f"Pre-state mismatch {k}: {before[k]} != {v}")

shutil.copy2(master,out/"text_master_BEFORE.tsv")
shutil.copy2(current,out/"campaign_next_translation_BEFORE.tsv")

for rid,t in trans.items():
    if rid not in idx:
        raise RuntimeError(f"Missing master ID {rid}")
    mr=idx[rid]
    if mr["status"]!="NEEDS_TRANSLATION":
        raise RuntimeError(f"{rid} status={mr['status']}")
    if mr["source_text"]!=t["source_text"]:
        raise RuntimeError(f"Master source mismatch {rid}")
    if rid in bidx and bidx[rid]["source_text"]!=t["source_text"]:
        raise RuntimeError(f"Current batch source mismatch {rid}")
    if rid in extras and "D7_1500_NOBETTERSPOT" not in mr.get("references",""):
        raise RuntimeError(f"Part-2 reference missing {rid}")
    mr["ko_current"]=t["ko_current"]
    mr["ko_review"]=t["ko_review"]
    mr["status"]="TRANSLATED_REVIEWED"
    note=mr.get("notes","")
    mr["notes"]=(note+"; " if note else "")+"STEP_054 reviewed; No Better Spot to Die parts 1/2; ISO not yet applied."

tmp=master.with_suffix(".tmp")
with tmp.open("w",encoding="utf-8-sig",newline="") as f:
    w=csv.DictWriter(f,fieldnames=fields,delimiter="\t",lineterminator="\n")
    w.writeheader();w.writerows(mrows)
tmp.replace(master)

after=collections.Counter(r["status"] for r in mrows if r.get("category")=="campaign")
expected2={"VERIFIED_APPLIED":137,"TRANSLATED_PENDING_APPLY":90,"TRANSLATED_REVIEWED":542,"NEEDS_TRANSLATION":533}
for k,v in expected2.items():
    if after[k]!=v:
        raise RuntimeError(f"Post-state mismatch {k}: {after[k]} != {v}")
if sum(after.values())!=1302:
    raise RuntimeError("Campaign total changed")

subset=[r for r in mrows if r["resource_id"] in trans]
with (out/"D7_NOBETTERSPOT_PART1_PART2_KO_reviewed.tsv").open("w",encoding="utf-8-sig",newline="") as f:
    w=csv.DictWriter(f,fieldnames=fields,delimiter="\t",lineterminator="\n")
    w.writeheader();w.writerows(subset)

# Confirm no untranslated No Better Spot resource remains.
left_nbs=[
    r["resource_id"] for r in mrows
    if r.get("status")=="NEEDS_TRANSLATION"
    and (
        "D7_1400_NOBETTERSPOT" in r.get("references","")
        or "D7_1500_NOBETTERSPOT" in r.get("references","")
    )
]
if left_nbs:
    raise RuntimeError(f"No Better Spot still has untranslated IDs: {left_nbs}")

pat=re.compile(r'(?<![A-Z0-9])((D0?\d{1,2})_(\d{4})_[A-Z0-9_]+)(?=:)',re.I)
remaining=[r for r in mrows if r.get("category")=="campaign" and r.get("status")=="NEEDS_TRANSLATION"]
groups=collections.defaultdict(set)
for r in remaining:
    for full,day,tm in pat.findall(r.get("references","")):
        groups[full.upper()].add(r["resource_id"])

def key(g):
    m=re.match(r'D0?(\d+)_(\d{4})_',g,re.I)
    return (int(m.group(1)),int(m.group(2)),g) if m else (999,9999,g)

cands=[g for g in groups if key(g)>(7,1400,"")]
if not cands:
    raise RuntimeError("No next untranslated campaign group")
next_group=min(cands,key=key)
ids=groups[next_group]
next_rows=[r for r in mrows if r["resource_id"] in ids and r["status"]=="NEEDS_TRANSLATION"]

with current.open("w",encoding="utf-8-sig",newline="") as f:
    w=csv.DictWriter(f,fieldnames=fields,delimiter="\t",lineterminator="\n")
    w.writeheader();w.writerows(next_rows)

shutil.copy2(master,out/"text_master_AFTER.tsv")
shutil.copy2(current,out/"campaign_next_translation.tsv")

report={
    "step":"STEP_054",
    "translations_applied_to_metadata":77,
    "completed_reference_groups":["D7_1400_NOBETTERSPOT","D7_1500_NOBETTERSPOT"],
    "status_counts":dict(after),
    "next_reference_group":next_group,
    "next_unit_count":len(next_rows),
    "remaining_group_summary":[
        {"reference_group":g,"remaining_unique_units":len(groups[g])}
        for g in sorted(groups,key=key)
    ],
    "master_sha256":hashlib.sha256(master.read_bytes()).hexdigest(),
    "next_batch_sha256":hashlib.sha256(current.read_bytes()).hexdigest(),
    "iso_modified":False,
    "movie_validation_resumed":False
}
(out/"step054_report.json").write_text(
    json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8"
)
print(json.dumps(report,ensure_ascii=False))
