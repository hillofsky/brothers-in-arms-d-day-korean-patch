#!/usr/bin/env python3
from pathlib import Path
import argparse,csv,json,hashlib,datetime,re,shutil,collections

ap=argparse.ArgumentParser()
ap.add_argument("--root",required=True)
ap.add_argument("--mapping",required=True)
ap.add_argument("--out",required=True)
a=ap.parse_args()

root=Path(a.root)
mapping=json.loads(Path(a.mapping).read_text(encoding="utf-8"))
out=Path(a.out);out.mkdir(parents=True,exist_ok=True)

batch=root/"translation"/"campaign_next_translation.tsv"
master=root/"translation"/"text_master.tsv"
if not batch.exists():raise FileNotFoundError(batch)
if not master.exists():raise FileNotFoundError(master)

def read_tsv(p):
    with p.open("r",encoding="utf-8-sig",newline="") as f:
        rd=csv.DictReader(f,delimiter="\t")
        return rd.fieldnames,list(rd)

bf,brows=read_tsv(batch)
mf,mrows=read_tsv(master)
trans={x["resource_id"]:x for x in mapping["translations"]}

if len(trans)!=62:raise RuntimeError(f"mapping count != 62: {len(trans)}")
bi={r["resource_id"]:r for r in brows}
mi={r["resource_id"]:r for r in mrows}
missing_batch=sorted(set(trans)-set(bi))
missing_master=sorted(set(trans)-set(mi))
if missing_batch or missing_master:
    raise RuntimeError(f"missing IDs batch={missing_batch} master={missing_master}")

# Validate exact English source before modifying anything.
for rid,t in trans.items():
    if bi[rid]["source_text"]!=t["source_text"]:
        raise RuntimeError(f"batch source mismatch {rid}")
    if mi[rid]["source_text"]!=t["source_text"]:
        raise RuntimeError(f"master source mismatch {rid}")
    if bi[rid].get("source_file")!="D0_1015_.MDI":
        raise RuntimeError(f"unexpected mission for {rid}: {bi[rid].get('source_file')}")

# Back up current tables into log output.
shutil.copy2(batch,out/"campaign_next_translation_BEFORE.tsv")
shutil.copy2(master,out/"text_master_BEFORE.tsv")

for rid,t in trans.items():
    for table in (bi,mi):
        table[rid]["ko_current"]=t["ko_current"]
        table[rid]["ko_review"]=t["ko_review"]
        table[rid]["status"]="TRANSLATED_REVIEWED"

def atomic_write(p,fields,rows):
    tmp=p.with_suffix(p.suffix+".tmp")
    with tmp.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields,delimiter="\t",lineterminator="\n")
        w.writeheader();w.writerows(rows)
    tmp.replace(p)

atomic_write(batch,bf,brows)
atomic_write(master,mf,mrows)

# Re-read and verify after write.
_,b2=read_tsv(batch); _,m2=read_tsv(master)
b2i={r["resource_id"]:r for r in b2};m2i={r["resource_id"]:r for r in m2}
for rid,t in trans.items():
    for table in (b2i,m2i):
        if table[rid]["ko_current"]!=t["ko_current"] or table[rid]["ko_review"]!=t["ko_review"]:
            raise RuntimeError(f"write verification failed {rid}")
        if table[rid]["status"]!="TRANSLATED_REVIEWED":
            raise RuntimeError(f"status verification failed {rid}")

counts=collections.Counter(r.get("status","") for r in m2 if r.get("category")=="campaign")
expected={
    "VERIFIED_APPLIED":137,
    "TRANSLATED_PENDING_APPLY":90,
    "TRANSLATED_REVIEWED":62,
    "NEEDS_TRANSLATION":1013,
}
for k,v in expected.items():
    if counts[k]!=v:raise RuntimeError(f"status count {k}: expected {v}, got {counts[k]}")

shutil.copy2(batch,out/"campaign_D0_1015_KO_reviewed.tsv")
shutil.copy2(master,out/"text_master_AFTER.tsv")

report={
    "step":"STEP_045",
    "mission":"D0_1015_.MDI",
    "translation_rows_applied":62,
    "status_counts":dict(counts),
    "batch_sha256":hashlib.sha256(batch.read_bytes()).hexdigest(),
    "master_sha256":hashlib.sha256(master.read_bytes()).hexdigest(),
    "iso_modified":False,
    "movie_validation_resumed":False,
}
(out/"step045_apply_report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(report,ensure_ascii=False))
