#!/usr/bin/env python3
from pathlib import Path
import argparse,csv,json,collections,shutil,hashlib

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

if len(trans)!=162:
    raise RuntimeError(f"Expected 162 translations, got {len(trans)}")
if len(brows)!=162:
    raise RuntimeError(f"Expected current final pool to contain 162 rows, got {len(brows)}")
if set(bidx)!=set(trans):
    raise RuntimeError("Final campaign pool ID set mismatch")

before=collections.Counter(r["status"] for r in mrows if r.get("category")=="campaign")
expected={
    "VERIFIED_APPLIED":137,
    "TRANSLATED_PENDING_APPLY":90,
    "TRANSLATED_REVIEWED":913,
    "NEEDS_TRANSLATION":162
}
for k,v in expected.items():
    if before[k]!=v:
        raise RuntimeError(f"STEP_062 pre-state mismatch {k}: {before[k]} != {v}")

shutil.copy2(master,out/"text_master_BEFORE.tsv")
shutil.copy2(current,out/"campaign_next_translation_BEFORE.tsv")

for rid,t in trans.items():
    mr=idx[rid];br=bidx[rid]
    if mr["status"]!="NEEDS_TRANSLATION":
        raise RuntimeError(f"{rid} status={mr['status']}")
    if mr["source_text"]!=t["source_text"] or br["source_text"]!=t["source_text"]:
        raise RuntimeError(f"Source mismatch {rid}")
    mr["ko_current"]=t["ko_current"]
    mr["ko_review"]=t["ko_review"]
    mr["status"]="TRANSLATED_REVIEWED"
    note=mr.get("notes","")
    mr["notes"]=(note+"; " if note else "")+"STEP_062 final campaign review; ISO not yet applied."

tmp=master.with_suffix(".tmp")
with tmp.open("w",encoding="utf-8-sig",newline="") as f:
    w=csv.DictWriter(f,fieldnames=fields,delimiter="\t",lineterminator="\n")
    w.writeheader();w.writerows(mrows)
tmp.replace(master)

after=collections.Counter(r["status"] for r in mrows if r.get("category")=="campaign")
expected2={
    "VERIFIED_APPLIED":137,
    "TRANSLATED_PENDING_APPLY":90,
    "TRANSLATED_REVIEWED":1075,
    "NEEDS_TRANSLATION":0
}
for k,v in expected2.items():
    if after[k]!=v:
        raise RuntimeError(f"STEP_062 post-state mismatch {k}: {after[k]} != {v}")
if sum(after.values())!=1302:
    raise RuntimeError(f"Campaign total changed: {sum(after.values())}")

still_untranslated=[
    r["resource_id"] for r in mrows
    if r.get("category")=="campaign" and r.get("status")=="NEEDS_TRANSLATION"
]
if still_untranslated:
    raise RuntimeError(f"Campaign untranslated rows remain: {still_untranslated[:20]}")

subset=[r for r in mrows if r["resource_id"] in trans]
with (out/"CAMPAIGN_FINAL_162_SKIRMISH_SYSTEM_KO_reviewed.tsv").open("w",encoding="utf-8-sig",newline="") as f:
    w=csv.DictWriter(f,fieldnames=fields,delimiter="\t",lineterminator="\n")
    w.writeheader();w.writerows(subset)

# Keep a valid header-only next-batch file: translation discovery is complete.
with current.open("w",encoding="utf-8-sig",newline="") as f:
    w=csv.DictWriter(f,fieldnames=fields,delimiter="\t",lineterminator="\n")
    w.writeheader()

shutil.copy2(master,out/"text_master_AFTER.tsv")
shutil.copy2(current,out/"campaign_next_translation.tsv")

unapplied=[
    r for r in mrows
    if r.get("category")=="campaign"
    and r.get("status") in ("TRANSLATED_PENDING_APPLY","TRANSLATED_REVIEWED")
]
with (out/"campaign_unapplied_ready_for_iso.tsv").open("w",encoding="utf-8-sig",newline="") as f:
    w=csv.DictWriter(f,fieldnames=fields,delimiter="\t",lineterminator="\n")
    w.writeheader();w.writerows(unapplied)

if len(unapplied)!=1165:
    raise RuntimeError(f"Unexpected unapplied campaign count: {len(unapplied)} != 1165")

report={
    "step":"STEP_062",
    "translations_applied_to_metadata":162,
    "status_counts":dict(after),
    "campaign_translation_corpus_complete":True,
    "campaign_untranslated_remaining":0,
    "unapplied_campaign_units_ready_for_iso":len(unapplied),
    "next_phase":"APPLY_UNAPPLIED_CAMPAIGN_TRANSLATIONS_TO_ISO",
    "master_sha256":hashlib.sha256(master.read_bytes()).hexdigest(),
    "unapplied_tsv_sha256":hashlib.sha256((out/"campaign_unapplied_ready_for_iso.tsv").read_bytes()).hexdigest(),
    "iso_modified":False,
    "movie_validation_resumed":False
}
(out/"step062_report.json").write_text(
    json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8"
)
print(json.dumps(report,ensure_ascii=False))
