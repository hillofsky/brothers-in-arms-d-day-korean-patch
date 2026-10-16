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
if not master.exists():raise FileNotFoundError(master)

with master.open("r",encoding="utf-8-sig",newline="") as f:
    rd=csv.DictReader(f,delimiter="\t"); fields=rd.fieldnames; rows=list(rd)
idx={r["resource_id"]:r for r in rows}
trans={x["resource_id"]:x for x in mapping["translations"]}
if len(trans)!=93:raise RuntimeError(f"Expected 93 translations, got {len(trans)}")

camp=[r for r in rows if r.get("category")=="campaign"]
before=collections.Counter(r["status"] for r in camp)
expected_before={"VERIFIED_APPLIED":137,"TRANSLATED_PENDING_APPLY":90,"TRANSLATED_REVIEWED":62,"NEEDS_TRANSLATION":1013}
for k,v in expected_before.items():
    if before[k]!=v:raise RuntimeError(f"Pre-state mismatch {k}: expected {v}, got {before[k]}")

# Exact-source validation and update.
shutil.copy2(master,out/"text_master_BEFORE.tsv")
for rid,t in trans.items():
    if rid not in idx:raise RuntimeError(f"Missing master ID {rid}")
    r=idx[rid]
    if r["status"]!="NEEDS_TRANSLATION":raise RuntimeError(f"{rid} status={r['status']}, expected NEEDS_TRANSLATION")
    if r["source_text"]!=t["source_text"]:raise RuntimeError(f"Source mismatch {rid}")
    if t["reference_group"] not in r.get("references",""):
        raise RuntimeError(f"Reference group missing for {rid}: {t['reference_group']}")
    r["ko_current"]=t["ko_current"]
    r["ko_review"]=t["ko_review"]
    r["status"]="TRANSLATED_REVIEWED"
    note=r.get("notes","")
    r["notes"]=(note+"; " if note else "")+"STEP_046 reviewed; ISO not yet applied."

tmp=master.with_suffix(".tmp")
with tmp.open("w",encoding="utf-8-sig",newline="") as f:
    w=csv.DictWriter(f,fieldnames=fields,delimiter="\t",lineterminator="\n");w.writeheader();w.writerows(rows)
tmp.replace(master)

after=collections.Counter(r["status"] for r in rows if r.get("category")=="campaign")
expected_after={"VERIFIED_APPLIED":137,"TRANSLATED_PENDING_APPLY":90,"TRANSLATED_REVIEWED":155,"NEEDS_TRANSLATION":920}
for k,v in expected_after.items():
    if after[k]!=v:raise RuntimeError(f"Post-state mismatch {k}: expected {v}, got {after[k]}")
if sum(after.values())!=1302:raise RuntimeError(f"Campaign total changed: {sum(after.values())}")

# Produce mission-specific reviewed TSVs.
for group in ("D1_0900_VIERVILLE","D1_1830_DEADMANSCORNER"):
    subset=[r for r in rows if r["resource_id"] in trans and trans[r["resource_id"]]["reference_group"]==group]
    p=out/f"{group}_KO_reviewed.tsv"
    with p.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields,delimiter="\t",lineterminator="\n");w.writeheader();w.writerows(subset)

# Find and export the next untranslated chronological mission group.
pat=re.compile(r'(?<![A-Z0-9])((?:D\d{1,2}|D0\d?)_(\d{4})_[A-Z0-9_]+)(?=:)',re.I)
remaining=[r for r in rows if r.get("category")=="campaign" and r.get("status")=="NEEDS_TRANSLATION"]
groups=collections.defaultdict(set)
for r in remaining:
    for full,tm in pat.findall(r.get("references","")):
        groups[full.upper()].add(r["resource_id"])

def order_key(g):
    m=re.match(r'D0?(\d+)_([0-9]{4})_',g,re.I)
    if not m:return (999,9999,g)
    return (int(m.group(1)),int(m.group(2)),g)

# D0 groups are already done; choose earliest D2+ after STEP_046's D1 groups.
candidates=[g for g in groups if order_key(g)>(1,1830,"")]
if not candidates:raise RuntimeError("No next untranslated campaign group found")
next_group=min(candidates,key=order_key)
next_ids=groups[next_group]
next_rows=[r for r in rows if r["resource_id"] in next_ids and r["status"]=="NEEDS_TRANSLATION"]

# campaign_next_translation.tsv always points to the next untranslated batch after this step.
with current.open("w",encoding="utf-8-sig",newline="") as f:
    w=csv.DictWriter(f,fieldnames=fields,delimiter="\t",lineterminator="\n");w.writeheader();w.writerows(next_rows)

shutil.copy2(master,out/"text_master_AFTER.tsv")
shutil.copy2(current,out/"campaign_next_translation.tsv")

summary=[]
for g in sorted(groups,key=order_key):
    summary.append({"reference_group":g,"remaining_unique_units":len(groups[g])})
report={
    "step":"STEP_046",
    "translations_applied_to_metadata":93,
    "status_counts":dict(after),
    "next_reference_group":next_group,
    "next_unit_count":len(next_rows),
    "remaining_group_summary":summary,
    "master_sha256":hashlib.sha256(master.read_bytes()).hexdigest(),
    "next_batch_sha256":hashlib.sha256(current.read_bytes()).hexdigest(),
    "iso_modified":False,
    "movie_validation_resumed":False,
}
(out/"step046_report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(report,ensure_ascii=False))
