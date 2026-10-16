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

def read_tsv(p):
    with p.open("r",encoding="utf-8-sig",newline="") as f:
        rd=csv.DictReader(f,delimiter="\t")
        return rd.fieldnames,list(rd)

if not master.exists():raise FileNotFoundError(master)
if not current.exists():raise FileNotFoundError(current)
fields,mrows=read_tsv(master)
bfields,brows=read_tsv(current)

idx={r["resource_id"]:r for r in mrows}
bidx={r["resource_id"]:r for r in brows}
trans={x["resource_id"]:x for x in mapping["translations"]}
if len(trans)!=36:raise RuntimeError(f"Expected 36 translations, got {len(trans)}")
if set(bidx)!=set(trans):
    raise RuntimeError(f"Current next-batch ID set mismatch: batch={len(bidx)}, mapping={len(trans)}")

before=collections.Counter(r["status"] for r in mrows if r.get("category")=="campaign")
expected_before={"VERIFIED_APPLIED":137,"TRANSLATED_PENDING_APPLY":90,"TRANSLATED_REVIEWED":227,"NEEDS_TRANSLATION":848}
for k,v in expected_before.items():
    if before[k]!=v:raise RuntimeError(f"Pre-state mismatch {k}: expected {v}, got {before[k]}")

shutil.copy2(master,out/"text_master_BEFORE.tsv")
shutil.copy2(current,out/"campaign_next_translation_BEFORE.tsv")

for rid,t in trans.items():
    mr=idx[rid];br=bidx[rid]
    if mr["status"]!="NEEDS_TRANSLATION":raise RuntimeError(f"{rid} status={mr['status']}")
    if mr["source_text"]!=t["source_text"] or br["source_text"]!=t["source_text"]:
        raise RuntimeError(f"Source mismatch {rid}")
    if t["reference_group"] not in mr.get("references",""):
        raise RuntimeError(f"Reference group missing {rid}")
    mr["ko_current"]=t["ko_current"]
    mr["ko_review"]=t["ko_review"]
    mr["status"]="TRANSLATED_REVIEWED"
    note=mr.get("notes","")
    mr["notes"]=(note+"; " if note else "")+"STEP_049 reviewed; ISO not yet applied."

tmp=master.with_suffix(".tmp")
with tmp.open("w",encoding="utf-8-sig",newline="") as f:
    w=csv.DictWriter(f,fieldnames=fields,delimiter="\t",lineterminator="\n")
    w.writeheader();w.writerows(mrows)
tmp.replace(master)

after=collections.Counter(r["status"] for r in mrows if r.get("category")=="campaign")
expected_after={"VERIFIED_APPLIED":137,"TRANSLATED_PENDING_APPLY":90,"TRANSLATED_REVIEWED":263,"NEEDS_TRANSLATION":812}
for k,v in expected_after.items():
    if after[k]!=v:raise RuntimeError(f"Post-state mismatch {k}: expected {v}, got {after[k]}")
if sum(after.values())!=1302:raise RuntimeError(f"Campaign total changed: {sum(after.values())}")

subset=[r for r in mrows if r["resource_id"] in trans]
with (out/"D3_0900_BUYINGTHEFARM_KO_reviewed.tsv").open("w",encoding="utf-8-sig",newline="") as f:
    w=csv.DictWriter(f,fieldnames=fields,delimiter="\t",lineterminator="\n")
    w.writeheader();w.writerows(subset)

# Parse all remaining campaign mission reference-group names and select chronological next group.
pat=re.compile(r'(?<![A-Z0-9])((D0?\d{1,2})_(\d{4})_[A-Z0-9_]+)(?=:)',re.I)
remaining=[r for r in mrows if r.get("category")=="campaign" and r.get("status")=="NEEDS_TRANSLATION"]
groups=collections.defaultdict(set)
for r in remaining:
    for full,day,tm in pat.findall(r.get("references","")):
        groups[full.upper()].add(r["resource_id"])

def key(g):
    m=re.match(r'D0?(\d+)_(\d{4})_',g,re.I)
    if not m:return (999,9999,g)
    return (int(m.group(1)),int(m.group(2)),g)

candidates=[g for g in groups if key(g)>(3,900,"")]
if not candidates:raise RuntimeError("No next untranslated campaign group found")
next_group=min(candidates,key=key)
next_ids=groups[next_group]
next_rows=[r for r in mrows if r["resource_id"] in next_ids and r["status"]=="NEEDS_TRANSLATION"]

with current.open("w",encoding="utf-8-sig",newline="") as f:
    w=csv.DictWriter(f,fieldnames=fields,delimiter="\t",lineterminator="\n")
    w.writeheader();w.writerows(next_rows)

shutil.copy2(master,out/"text_master_AFTER.tsv")
shutil.copy2(current,out/"campaign_next_translation.tsv")

summary=[{"reference_group":g,"remaining_unique_units":len(groups[g])} for g in sorted(groups,key=key)]
report={
    "step":"STEP_049",
    "translations_applied_to_metadata":36,
    "status_counts":dict(after),
    "next_reference_group":next_group,
    "next_unit_count":len(next_rows),
    "remaining_group_summary":summary,
    "master_sha256":hashlib.sha256(master.read_bytes()).hexdigest(),
    "next_batch_sha256":hashlib.sha256(current.read_bytes()).hexdigest(),
    "iso_modified":False,
    "movie_validation_resumed":False,
}
(out/"step049_report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(report,ensure_ascii=False))
