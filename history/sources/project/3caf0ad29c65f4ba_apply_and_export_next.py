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

if len(trans)!=60:
    raise RuntimeError(f"Expected 60 translations, got {len(trans)}")
if len(brows)!=24:
    raise RuntimeError(f"STEP_059-exported Part 1 batch should contain 24 rows, got {len(brows)}")
if not set(bidx).issubset(set(trans)):
    raise RuntimeError("Part 1 batch IDs are not a subset of STEP_060 mapping")

extra_ids=set(trans)-set(bidx)
if len(extra_ids)!=36:
    raise RuntimeError(f"Expected 36 Part-2-only IDs, got {len(extra_ids)}")

before=collections.Counter(r["status"] for r in mrows if r.get("category")=="campaign")
expected={"VERIFIED_APPLIED":137,"TRANSLATED_PENDING_APPLY":90,"TRANSLATED_REVIEWED":734,"NEEDS_TRANSLATION":341}
for k,v in expected.items():
    if before[k]!=v:
        raise RuntimeError(f"STEP_060 pre-state mismatch {k}: {before[k]} != {v}")

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
        raise RuntimeError(f"Part 1 source mismatch {rid}")
    refs=mr.get("references","")
    if ("D10_0801_THEALLAMERICANS" not in refs and
        "D10_0802_THEALLAMERICANS" not in refs):
        raise RuntimeError(f"All Americans reference missing {rid}")
    mr["ko_current"]=t["ko_current"]
    mr["ko_review"]=t["ko_review"]
    mr["status"]="TRANSLATED_REVIEWED"
    n=mr.get("notes","")
    mr["notes"]=(n+"; " if n else "")+"STEP_060 reviewed; All Americans Parts 1/2; ISO not yet applied."

tmp=master.with_suffix(".tmp")
with tmp.open("w",encoding="utf-8-sig",newline="") as f:
    w=csv.DictWriter(f,fieldnames=fields,delimiter="\t",lineterminator="\n")
    w.writeheader();w.writerows(mrows)
tmp.replace(master)

after=collections.Counter(r["status"] for r in mrows if r.get("category")=="campaign")
expected2={"VERIFIED_APPLIED":137,"TRANSLATED_PENDING_APPLY":90,"TRANSLATED_REVIEWED":794,"NEEDS_TRANSLATION":281}
for k,v in expected2.items():
    if after[k]!=v:
        raise RuntimeError(f"STEP_060 post-state mismatch {k}: {after[k]} != {v}")
if sum(after.values())!=1302:
    raise RuntimeError(f"Campaign total changed: {sum(after.values())}")

# Confirm both All Americans groups are fully translated in metadata.
left=[
    r["resource_id"] for r in mrows
    if r.get("status")=="NEEDS_TRANSLATION"
    and (
        "D10_0801_THEALLAMERICANS" in r.get("references","")
        or "D10_0802_THEALLAMERICANS" in r.get("references","")
    )
]
if left:
    raise RuntimeError(f"All Americans still has untranslated IDs: {left}")

subset=[r for r in mrows if r["resource_id"] in trans]
with (out/"D10_THEALLAMERICANS_PART1_PART2_KO_reviewed.tsv").open("w",encoding="utf-8-sig",newline="") as f:
    w=csv.DictWriter(f,fieldnames=fields,delimiter="\t",lineterminator="\n")
    w.writeheader();w.writerows(subset)

pat=re.compile(r'(?<![A-Z0-9])((D0?\d{1,2})_(\d{4})_[A-Z0-9_]+)(?=:)',re.I)
remaining=[r for r in mrows if r.get("category")=="campaign" and r.get("status")=="NEEDS_TRANSLATION"]
groups=collections.defaultdict(set)
for r in remaining:
    for full,day,tm in pat.findall(r.get("references","")):
        groups[full.upper()].add(r["resource_id"])

def key(g):
    m=re.match(r'D0?(\d+)_(\d{4})_',g,re.I)
    return (int(m.group(1)),int(m.group(2)),g) if m else (999,9999,g)

if not groups:
    raise RuntimeError("No remaining campaign reference groups")
next_group=min(groups,key=key)
ids=groups[next_group]
next_rows=[r for r in mrows if r["resource_id"] in ids and r["status"]=="NEEDS_TRANSLATION"]

if next_group!="D15_1130_BOOKENDS":
    raise RuntimeError(f"Unexpected next group: {next_group}")
if len(next_rows)!=43:
    raise RuntimeError(f"Unexpected next count: {len(next_rows)} != 43")

with current.open("w",encoding="utf-8-sig",newline="") as f:
    w=csv.DictWriter(f,fieldnames=fields,delimiter="\t",lineterminator="\n")
    w.writeheader();w.writerows(next_rows)

shutil.copy2(master,out/"text_master_AFTER.tsv")
shutil.copy2(current,out/"campaign_next_translation.tsv")

report={
    "step":"STEP_060",
    "translations_applied_to_metadata":60,
    "completed_reference_groups":["D10_0801_THEALLAMERICANS","D10_0802_THEALLAMERICANS"],
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
(out/"step060_report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(report,ensure_ascii=False))
