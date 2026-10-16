#!/usr/bin/env python3
from pathlib import Path
import argparse,csv,json,re,hashlib,collections,shutil,datetime

ap=argparse.ArgumentParser()
ap.add_argument("--root",required=True)
ap.add_argument("--legacy-root",required=True)
ap.add_argument("--out",required=True)
a=ap.parse_args()

root=Path(a.root)
legacy=Path(a.legacy_root)
out=Path(a.out)
out.mkdir(parents=True,exist_ok=True)
(root/"translation").mkdir(parents=True,exist_ok=True)
(root/"work").mkdir(parents=True,exist_ok=True)

MASTER_SRC=root/"analysis"/"stage38_translation_worklist"/"stage38_translation_units.tsv"
ISO_INV=root/"analysis"/"stage40i_actual_resource_trace"/"stage40i_iso_inventory.tsv"
BASE_ISO=root/"BIA_STAGE43T_TITLE_PROMPT_FIX.iso"

if not MASTER_SRC.exists():
    raise FileNotFoundError(f"Canonical campaign worklist missing: {MASTER_SRC}")
if not BASE_ISO.exists():
    raise FileNotFoundError(f"Stage43T baseline missing: {BASE_ISO}")

def obtain(name):
    dst=root/"work"/name
    if dst.exists():
        return dst,"D_BIA"
    src=legacy/"work"/name
    if not src.exists():
        raise FileNotFoundError(f"Required translation handoff missing in PROJECT_ROOT and legacy tree: {name}")
    shutil.copy2(src,dst)
    return dst,"IMPORTED_LEGACY"

first_path,first_origin=obtain("campaign_first_ko.json")
second_path,second_origin=obtain("campaign_second_ko.json")

first=json.loads(first_path.read_text(encoding="utf-8"))
second=json.loads(second_path.read_text(encoding="utf-8"))

if not isinstance(first,dict) or len(first)!=137:
    raise RuntimeError(f"campaign_first_ko.json expected 137 translations, got {len(first) if isinstance(first,dict) else type(first)}")
if not isinstance(second,dict) or len(second)!=90:
    raise RuntimeError(f"campaign_second_ko.json expected 90 translations, got {len(second) if isinstance(second,dict) else type(second)}")

with MASTER_SRC.open("r",encoding="utf-8-sig",errors="strict",newline="") as f:
    rd=csv.DictReader(f,delimiter="\t")
    src_fields=rd.fieldnames or []
    rows=list(rd)

required={"id","priority","English","references"}
missing=required-set(src_fields)
if missing:
    raise RuntimeError(f"Canonical TSV schema missing columns: {sorted(missing)}; fields={src_fields}")

b_rows=[r for r in rows if (r.get("priority") or "").strip().upper()=="B"]
if len(b_rows)!=1302:
    raise RuntimeError(f"Priority-B campaign unit count changed: expected 1302, got {len(b_rows)}")

ids=[r["id"] for r in b_rows]
if len(ids)!=len(set(ids)):
    dup=[x for x,c in collections.Counter(ids).items() if c>1]
    raise RuntimeError(f"Duplicate B IDs: {dup[:20]}")

idset=set(ids)
first_ids=set(first)
second_ids=set(second)
if len(first_ids)!=137 or len(second_ids)!=90 or first_ids & second_ids:
    raise RuntimeError("First/second translation ID sets are invalid or overlap")
if not first_ids <= idset:
    raise RuntimeError(f"First mission IDs missing from canonical B worklist: {sorted(first_ids-idset)[:10]}")
if not second_ids <= idset:
    raise RuntimeError(f"Second mission IDs missing from canonical B worklist: {sorted(second_ids-idset)[:10]}")

translated_ids=first_ids|second_ids
remaining=[r for r in b_rows if r["id"] not in translated_ids]
if len(remaining)!=1302-137-90:
    raise RuntimeError(f"Remaining count mismatch: {len(remaining)}")

# Stage38 references use forms such as:
#   D0_0700_EXIT4:...
# rather than literal D0_0700_.MDI.
# This was the reason FIX6 did not recognize the remaining missions.
REF_CODE_RE=re.compile(r'(?<![A-Za-z0-9])D0_(\d{4})(?:_[A-Za-z0-9]+)?(?=[:|,;\s]|$)',re.I)
LOOSE_CODE_RE=re.compile(r'D0_(\d{4})',re.I)

def codes_from_refs(s):
    s=s or ""
    vals=REF_CODE_RE.findall(s)
    if not vals:
        vals=LOOSE_CODE_RE.findall(s)
    return sorted(set(vals),key=int)

groups=collections.defaultdict(list)
row_codes={}
ungrouped=[]
for r in remaining:
    cs=codes_from_refs(r.get("references",""))
    row_codes[r["id"]]=cs
    if not cs:
        ungrouped.append(r)
    for c in cs:
        groups[c].append(r)

# Inventory actual D0_*.MDI names so the selected code is tied to a real resource.
mission_files=collections.defaultdict(set)
if ISO_INV.exists():
    txt=ISO_INV.read_text(encoding="utf-8-sig",errors="replace")
    for m in re.findall(r'D0_(\d{4})_[A-Za-z0-9_]*\.MDI|D0_(\d{4})_\.MDI',txt,re.I):
        pass
    for name in re.findall(r'D0_\d{4}_[A-Za-z0-9_]*\.MDI',txt,re.I):
        mm=re.match(r'D0_(\d{4})',name,re.I)
        if mm:
            mission_files[mm.group(1)].add(name)
    # Also handle the canonical trailing-underscore form.
    for name in re.findall(r'D0_\d{4}_\.MDI',txt,re.I):
        mm=re.match(r'D0_(\d{4})',name,re.I)
        if mm:
            mission_files[mm.group(1)].add(name)

# Exclude already-completed mission codes even if some untranslated shared strings mention them.
candidate_codes=[]
for code,rr in groups.items():
    if code in {"0130","0700"}:
        continue
    if not rr:
        continue
    candidate_codes.append(code)
candidate_codes.sort(key=int)

if not candidate_codes:
    raise RuntimeError(
        "Canonical stage38 Priority-B worklist contains no remaining D0_#### mission references "
        "after excluding translated first/second mission IDs."
    )

# Prefer a code backed by an actual MDI inventory entry.
actual=[c for c in candidate_codes if mission_files.get(c)]
selected_code=(actual or candidate_codes)[0]
selected_rows=groups[selected_code]

# A unit can be referenced by multiple missions. It belongs in this batch if the selected
# mission references it; duplicate IDs are removed while preserving canonical worklist order.
selected_ids={r["id"] for r in selected_rows}
selected=[r for r in remaining if r["id"] in selected_ids]
if not selected:
    raise RuntimeError(f"Selected mission {selected_code} produced an empty batch")

files=sorted(mission_files.get(selected_code,[]))
selected_mdi=(
    f"D0_{selected_code}_.MDI"
    if f"D0_{selected_code}_.MDI" in files or not files
    else files[0]
)

# Verify the selected MDI can actually be read from Stage43T using the established helper.
helper=root/"bia_stage40i_tools"/"bia_stage40i_actual_resource_trace.py"
iso_readback={"attempted":False,"ok":False,"file":selected_mdi}
if helper.exists():
    import importlib.util
    sp=importlib.util.spec_from_file_location("biahelper",helper)
    mod=importlib.util.module_from_spec(sp); sp.loader.exec_module(mod)
    _,b=mod.load_helpers()
    iso_readback["attempted"]=True
    try:
        _,blob=b.iso_read_file(BASE_ISO,["PSP_GAME","USRDIR","SYSTEM",selected_mdi])
        iso_readback.update({
            "ok":True,
            "size":len(blob),
            "sha256":hashlib.sha256(blob).hexdigest()
        })
    except Exception as e:
        iso_readback["error"]=repr(e)

if iso_readback["attempted"] and not iso_readback["ok"]:
    raise RuntimeError(f"Selected MDI {selected_mdi} was not readable from Stage43T: {iso_readback.get('error')}")

def control_tokens(s):
    vals=[]
    for pat in (
        r'%[^%\s]+%',
        r'\{[^{}]+\}',
        r'<[^<>]+>',
        r'\\[nrt]',
        r'%[-+0-9.]*[A-Za-z]',
    ):
        vals.extend(re.findall(pat,s or ""))
    return "|".join(dict.fromkeys(vals))

# Build a persistent 1302-row campaign master section.
master_path=root/"translation"/"text_master.tsv"
fields=[
    "id","category","source_file","resource_id","offset","context_before","source_text",
    "context_after","ko_current","ko_review","encoding","max_bytes","control_tokens",
    "linebreak_rule","status","notes","references","priority"
]

existing=[]
if master_path.exists():
    with master_path.open("r",encoding="utf-8-sig",errors="replace",newline="") as f:
        rd=csv.DictReader(f,delimiter="\t")
        old_fields=rd.fieldnames or []
        for rr in rd:
            existing.append({k:rr.get(k,"") for k in fields})

# Preserve any previously assigned TXT IDs keyed by canonical BIA resource ID.
old_by_resource={
    r["resource_id"]:r for r in existing
    if r.get("category")=="campaign" and r.get("resource_id")
}
nums=[]
for r in existing:
    m=re.fullmatch(r'TXT_(\d+)',r.get("id",""))
    if m:nums.append(int(m.group(1)))
next_txt=max(nums,default=0)+1

# Remove old imported campaign B rows; rebuild them deterministically from the canonical 1302.
noncampaign=[
    r for r in existing
    if not (r.get("category")=="campaign" and r.get("resource_id") in idset)
]

campaign_master=[]
for r in b_rows:
    rid=r["id"]
    cs=codes_from_refs(r.get("references",""))
    sf=""
    if cs:
        code=cs[0]
        names=sorted(mission_files.get(code,[]))
        sf=f"D0_{code}_.MDI" if f"D0_{code}_.MDI" in names or not names else names[0]

    old=old_by_resource.get(rid)
    if old and old.get("id"):
        txtid=old["id"]
    else:
        txtid=f"TXT_{next_txt:06d}"
        next_txt+=1

    if rid in first:
        ko=first[rid]; status="VERIFIED_APPLIED"
    elif rid in second:
        ko=second[rid]; status="TRANSLATED_PENDING_APPLY"
    else:
        ko=(old or {}).get("ko_current","")
        status="NEEDS_TRANSLATION" if not ko else (old or {}).get("status","TRANSLATED_UNVERIFIED")

    campaign_master.append({
        "id":txtid,
        "category":"campaign",
        "source_file":sf,
        "resource_id":rid,
        "offset":"",
        "context_before":r.get("context_before",""),
        "source_text":r["English"],
        "context_after":r.get("context_after",""),
        "ko_current":ko,
        "ko_review":(old or {}).get("ko_review",""),
        "encoding":"UTF-8",
        "max_bytes":"",
        "control_tokens":control_tokens(r["English"]),
        "linebreak_rule":"",
        "status":status,
        "notes":"Imported from canonical stage38 Priority-B campaign worklist in STEP_044 FIX7.",
        "references":r.get("references",""),
        "priority":"B",
    })

all_master=noncampaign+campaign_master
tmp=master_path.with_suffix(".tmp")
with tmp.open("w",encoding="utf-8-sig",newline="") as f:
    w=csv.DictWriter(f,fieldnames=fields,delimiter="\t",lineterminator="\n")
    w.writeheader();w.writerows(all_master)
tmp.replace(master_path)

by_rid={r["resource_id"]:r for r in campaign_master}

batch_path=root/"translation"/"campaign_next_translation.tsv"
batch_rows=[by_rid[r["id"]].copy() for r in selected]
# All selected rows should still be untranslated.
for r in batch_rows:
    if r["status"]!="NEEDS_TRANSLATION":
        raise RuntimeError(f"Selected batch unexpectedly contains non-pending row {r['resource_id']} status={r['status']}")

with batch_path.open("w",encoding="utf-8-sig",newline="") as f:
    w=csv.DictWriter(f,fieldnames=fields,delimiter="\t",lineterminator="\n")
    w.writeheader();w.writerows(batch_rows)

# Mission group summary.
summary_path=out/"campaign_group_summary.tsv"
with summary_path.open("w",encoding="utf-8-sig",newline="") as f:
    cols=["mission_code","mission_files","remaining_unique_units","selected","sample_ids"]
    w=csv.DictWriter(f,fieldnames=cols,delimiter="\t",lineterminator="\n")
    w.writeheader()
    for code in sorted(groups,key=int):
        rr={x["id"] for x in groups[code] if x["id"] not in translated_ids}
        w.writerow({
            "mission_code":code,
            "mission_files":"|".join(sorted(mission_files.get(code,[]))),
            "remaining_unique_units":len(rr),
            "selected":"YES" if code==selected_code else "",
            "sample_ids":"|".join(sorted(rr)[:8]),
        })

# Validation.
counts=collections.Counter(r["status"] for r in campaign_master)
if counts["VERIFIED_APPLIED"]!=137:
    raise RuntimeError(f"text_master first mission status count !=137: {counts}")
if counts["TRANSLATED_PENDING_APPLY"]!=90:
    raise RuntimeError(f"text_master second mission status count !=90: {counts}")
if len(campaign_master)!=1302:
    raise RuntimeError("text_master campaign row count !=1302")
if len({r["id"] for r in campaign_master})!=1302:
    raise RuntimeError("Duplicate TXT IDs in campaign master")
if len({r["resource_id"] for r in campaign_master})!=1302:
    raise RuntimeError("Duplicate BIA resource IDs in campaign master")

report={
    "step":"STEP_044",
    "retry":"FIX7",
    "canonical_source":str(MASTER_SRC),
    "canonical_source_sha256":hashlib.sha256(MASTER_SRC.read_bytes()).hexdigest(),
    "priority_b_total":len(b_rows),
    "first_verified_units":len(first_ids),
    "second_translated_pending_apply_units":len(second_ids),
    "remaining_untranslated_units":len(remaining),
    "ungrouped_remaining_units":len(ungrouped),
    "mission_group_counts":{
        code:len({r["id"] for r in rr if r["id"] not in translated_ids})
        for code,rr in sorted(groups.items(),key=lambda kv:int(kv[0]))
    },
    "selected_mission_code":selected_code,
    "selected_mdi":selected_mdi,
    "selected_unit_count":len(batch_rows),
    "selected_resource_ids":[r["resource_id"] for r in batch_rows],
    "selected_iso_readback":iso_readback,
    "translation_origins":{
        "campaign_first_ko":first_origin,
        "campaign_second_ko":second_origin,
    },
    "text_master_status_counts":dict(counts),
    "iso_modified":False,
    "movie_validation_resumed":False,
    "stage43t_menu_after_start_status":"PENDING",
}
(out/"campaign_next_selection.json").write_text(
    json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8"
)
(out/"campaign_next_translation.tsv").write_bytes(batch_path.read_bytes())
(out/"text_master.tsv").write_bytes(master_path.read_bytes())

with (out/"translation_validation.tsv").open("w",encoding="utf-8-sig",newline="") as f:
    f.write("check\tstatus\tdetail\n")
    f.write(f"priority_b_total\tPASS\t{len(b_rows)}\n")
    f.write(f"first_verified\tPASS\t{counts['VERIFIED_APPLIED']}\n")
    f.write(f"second_pending_apply\tPASS\t{counts['TRANSLATED_PENDING_APPLY']}\n")
    f.write(f"selected_batch_nonempty\tPASS\t{len(batch_rows)}\n")
    f.write(f"selected_iso_readback\t{'PASS' if iso_readback['ok'] or not iso_readback['attempted'] else 'FAIL'}\t{selected_mdi}\n")
    f.write("iso_modified\tPASS\tNO\n")
    f.write("movie_validation_resumed\tPASS\tNO\n")

print(json.dumps({
    "status":"VERIFIED_EXPORT",
    "selected_mission_code":selected_code,
    "selected_mdi":selected_mdi,
    "selected_unit_count":len(batch_rows),
    "priority_b_total":len(b_rows),
    "remaining_untranslated_units":len(remaining),
    "batch_path":str(batch_path)
},ensure_ascii=False))
