#!/usr/bin/env python3
from pathlib import Path
import argparse,csv,json,re,hashlib,shutil,sys,traceback

ap=argparse.ArgumentParser()
ap.add_argument("--project-root",required=True)
ap.add_argument("--legacy-root",default="")
ap.add_argument("--out-dir",required=True)
a=ap.parse_args()

root=Path(a.project_root)
legacy=Path(a.legacy_root) if a.legacy_root else None
out=Path(a.out_dir)
trans=root/"translation"
work=root/"work"
out.mkdir(parents=True,exist_ok=True)
trans.mkdir(parents=True,exist_ok=True)
work.mkdir(parents=True,exist_ok=True)

FIRST="D0_0130_.MDI"
SECOND="D0_0700_.MDI"
MISSION_RE=re.compile(r'(D0_[0-9A-Za-z_]+\.MDI)',re.I)

EXCLUDE_DIRS={
    "log","logs","incoming",".git","cache","temp","tmp","python_deps",
    "__pycache__","stage43t_validation"
}
EXTS={".json",".tsv",".csv"}

def norm_mission(s):
    if not s:return ""
    m=MISSION_RE.search(str(s).replace("\\","/"))
    return m.group(1) if m else ""

def mission_num(s):
    m=re.search(r'D0_(\d+)',s or "",re.I)
    return int(m.group(1)) if m else 10**9

def ci(d,*names):
    if not isinstance(d,dict): return None
    low={str(k).lower():k for k in d}
    for n in names:
        k=low.get(n.lower())
        if k is not None and d[k] not in (None,"",[],{}):
            return d[k]
    return None

def infer_mission_from_obj(obj):
    if isinstance(obj,dict):
        # explicit fields first
        for n in ("source_file","file","mdi","container_file","package","asset","resource_file","mission_file"):
            v=ci(obj,n)
            m=norm_mission(v)
            if m:return m
        # then any scalar key/value containing a mission name
        for k,v in obj.items():
            m=norm_mission(k)
            if m:return m
            if isinstance(v,(str,int,float)):
                m=norm_mission(v)
                if m:return m
    elif isinstance(obj,str):
        return norm_mission(obj)
    return ""

def get_source_text(d):
    if not isinstance(d,dict):return None
    for n in (
        "english","source_text","original_text","original","text","string","source",
        "en","eng","text_en","english_text","value"
    ):
        v=ci(d,n)
        if isinstance(v,str) and len(v.strip())>=2:
            # Reject obvious paths/filenames as text.
            if MISSION_RE.search(v) and len(v)<80:
                continue
            return v
    return None

def get_offset(d):
    v=ci(d,"offset","offset_hex","file_offset","address","va","data_offset")
    if v is None:return ""
    if isinstance(v,int):return f"0x{v:X}"
    return str(v)

def get_refs(d):
    v=ci(d,"references","refs","reference","locations","uses")
    if v is None:return ""
    if isinstance(v,str):return v
    try:return json.dumps(v,ensure_ascii=False,separators=(",",":"))
    except:return str(v)

def controls(s):
    pats=(r'\\[nrt]',r'\{[^{}]+\}',r'%[-+0-9.]*[a-zA-Z]',r'<[^<>]+>',r'\^[A-Za-z0-9_]*')
    vals=[]
    for p in pats: vals.extend(re.findall(p,s))
    return "|".join(dict.fromkeys(vals))

def walk_json(obj,path=(),mission=""):
    local=mission or infer_mission_from_obj(obj)
    # path keys can carry mission context
    for part in reversed(path):
        m=norm_mission(part)
        if m:
            local=m
            break
    if isinstance(obj,dict):
        s=get_source_text(obj)
        if s and local:
            yield path,local,obj,s
        for k,v in obj.items():
            child_mission=local or norm_mission(k) or infer_mission_from_obj(v)
            yield from walk_json(v,path+(str(k),),child_mission)
    elif isinstance(obj,list):
        for i,v in enumerate(obj):
            yield from walk_json(v,path+(str(i),),local)

def should_skip(p,base):
    try:
        rel=p.relative_to(base)
    except:
        return False
    parts={x.lower() for x in rel.parts[:-1]}
    return bool(parts & EXCLUDE_DIRS)

def collect_files(base,label):
    found=[]
    if not base or not base.exists():return found
    for p in base.rglob("*"):
        if not p.is_file() or p.suffix.lower() not in EXTS:
            continue
        if should_skip(p,base):continue
        try:
            size=p.stat().st_size
        except:
            continue
        if size==0 or size>120*1024*1024:
            continue
        found.append((label,base,p,size))
    return found

files=collect_files(root,"D_BIA")
if legacy and legacy.exists():
    files += collect_files(legacy,"LEGACY_CODEX")

# Deduplicate same physical path string.
seen=set(); uniq=[]
for x in files:
    k=str(x[2]).lower()
    if k not in seen:
        seen.add(k); uniq.append(x)
files=uniq

rows=[]
file_stats=[]
parse_errors=[]
d0_text_hits=[]

for label,base,p,size in files:
    rel=str(p.relative_to(base))
    count_before=len(rows)
    missions=set()
    try:
        if p.suffix.lower()==".json":
            obj=json.loads(p.read_text(encoding="utf-8-sig"))
            # File name/path itself may carry a mission.
            file_mission=norm_mission(rel)
            for path,mission,d,s in walk_json(obj,(),file_mission):
                missions.add(mission)
                rid=ci(d,"resource_id","unit_id","id","key","text_id","index")
                rows.append({
                    "source_file":mission,
                    "resource_id":"" if rid is None else str(rid),
                    "offset":get_offset(d),
                    "context_before":str(ci(d,"context_before","before","prev") or ""),
                    "source_text":s,
                    "context_after":str(ci(d,"context_after","after","next") or ""),
                    "encoding":str(ci(d,"encoding") or "UTF-8"),
                    "max_bytes":str(ci(d,"max_bytes","field_bytes","byte_limit","size_limit") or ""),
                    "control_tokens":str(ci(d,"control_tokens") or controls(s)),
                    "linebreak_rule":str(ci(d,"linebreak_rule","wrap_rule") or ""),
                    "references":get_refs(d),
                    "origin_label":label,
                    "origin_file":str(p),
                    "origin_rel":rel,
                    "origin_path":"/".join(path),
                })
        else:
            delim="\t" if p.suffix.lower()==".tsv" else ","
            with p.open("r",encoding="utf-8-sig",errors="replace",newline="") as f:
                rd=csv.DictReader(f,delimiter=delim)
                for idx,d in enumerate(rd):
                    mission=infer_mission_from_obj(d) or norm_mission(rel)
                    s=get_source_text(d)
                    if not mission or not s:continue
                    missions.add(mission)
                    rid=ci(d,"resource_id","unit_id","id","key","text_id","index")
                    rows.append({
                        "source_file":mission,
                        "resource_id":"" if rid is None else str(rid),
                        "offset":get_offset(d),
                        "context_before":str(ci(d,"context_before","before","prev") or ""),
                        "source_text":s,
                        "context_after":str(ci(d,"context_after","after","next") or ""),
                        "encoding":str(ci(d,"encoding") or "UTF-8"),
                        "max_bytes":str(ci(d,"max_bytes","field_bytes","byte_limit","size_limit") or ""),
                        "control_tokens":str(ci(d,"control_tokens") or controls(s)),
                        "linebreak_rule":str(ci(d,"linebreak_rule","wrap_rule") or ""),
                        "references":get_refs(d),
                        "origin_label":label,
                        "origin_file":str(p),
                        "origin_rel":rel,
                        "origin_path":str(idx),
                    })
        added=len(rows)-count_before
        if added or missions:
            file_stats.append({
                "label":label,"file":str(p),"relative":rel,"size":size,
                "records":added,"missions":sorted(missions,key=lambda s:(mission_num(s),s))
            })
    except Exception as e:
        parse_errors.append({"label":label,"file":str(p),"error":repr(e)})

# Broad text/py/md/txt search only as fallback diagnostic. This is NOT parsed as translation data.
if not rows:
    scan_ext={".py",".md",".txt",".json",".tsv",".csv"}
    scan_roots=[("D_BIA",root)]
    if legacy and legacy.exists():scan_roots.append(("LEGACY_CODEX",legacy))
    for label,base in scan_roots:
        for p in base.rglob("*"):
            if not p.is_file() or p.suffix.lower() not in scan_ext or should_skip(p,base):continue
            try:
                if p.stat().st_size>20*1024*1024:continue
                txt=p.read_text(encoding="utf-8-sig",errors="ignore")
            except:continue
            ms=sorted(set(MISSION_RE.findall(txt)),key=lambda s:(mission_num(s),s))
            if ms:
                d0_text_hits.append({"label":label,"file":str(p),"missions":ms})

# Deduplicate translation records. Prefer PROJECT_ROOT over legacy and richer metadata.
def rich(r):
    score=100 if r["origin_label"]=="D_BIA" else 0
    score+=sum(5 for k in ("resource_id","offset","context_before","context_after","max_bytes","references") if r[k])
    return score

dedup={}
for r in rows:
    k=(r["source_file"].upper(),r["resource_id"],r["offset"],r["source_text"])
    if k not in dedup or rich(r)>rich(dedup[k]):
        dedup[k]=r
rows=list(dedup.values())

groups={}
for r in rows:
    if r["source_file"].upper() in {FIRST.upper(),SECOND.upper()}:
        continue
    groups.setdefault(r["source_file"],[]).append(r)

inventory={
    "step":"STEP_044_FIX3",
    "structured_files_scanned":len(files),
    "structured_files_with_records":file_stats,
    "parse_errors":parse_errors,
    "all_translation_records_after_dedup":len(rows),
    "remaining_group_counts":{k:len(v) for k,v in sorted(groups.items(),key=lambda kv:(mission_num(kv[0]),kv[0]))},
    "fallback_d0_text_hits":d0_text_hits,
}
(out/"candidate_inventory.json").write_text(json.dumps(inventory,ensure_ascii=False,indent=2),encoding="utf-8")

# Also write a compact source inventory TSV.
with (out/"candidate_inventory.tsv").open("w",encoding="utf-8-sig",newline="") as f:
    cols=["label","relative","records","missions","size","file"]
    w=csv.DictWriter(f,fieldnames=cols,delimiter="\t",lineterminator="\n")
    w.writeheader()
    for x in file_stats:
        w.writerow({
            "label":x["label"],"relative":x["relative"],"records":x["records"],
            "missions":"|".join(x["missions"]),"size":x["size"],"file":x["file"]
        })

if not groups:
    raise RuntimeError(
        "No remaining campaign D0_*.MDI translation groups found even after full structured-data scan. "
        "Inspect candidate_inventory.json/tsv in the fall_ ZIP."
    )

# Select lowest numbered mission after D0_0700, otherwise lowest remaining.
after=sorted((mission_num(k),k) for k in groups if mission_num(k)>700)
selected=after[0][1] if after else min(groups,key=lambda k:(mission_num(k),k))
batch=groups[selected]
batch.sort(key=lambda r:(r["offset"]=="",r["offset"],r["resource_id"],r["source_text"]))

# Import source datasets actually used for this batch into PROJECT_ROOT\work\imported_sources\STEP_044.
imports=root/"work"/"imported_sources"/"STEP_044"
imports.mkdir(parents=True,exist_ok=True)
used_sources=sorted({r["origin_file"] for r in batch})
import_manifest=[]
for idx,s in enumerate(used_sources,1):
    p=Path(s)
    if not p.exists():continue
    h=hashlib.sha256(p.read_bytes()).hexdigest()
    # If already under PROJECT_ROOT, do not duplicate.
    try:
        p.relative_to(root)
        copied=""
    except:
        target=imports/f"{idx:02d}_{p.name}"
        shutil.copy2(p,target)
        copied=str(target)
    import_manifest.append({
        "source":str(p),"sha256":h,"copied_to":copied,"size":p.stat().st_size
    })
(out/"source_import_manifest.json").write_text(json.dumps(import_manifest,ensure_ascii=False,indent=2),encoding="utf-8")

# Stable master TSV.
fields=[
    "id","category","source_file","resource_id","offset","context_before","source_text",
    "context_after","ko_current","ko_review","encoding","max_bytes","control_tokens",
    "linebreak_rule","status","notes"
]
master=trans/"text_master.tsv"
existing=[]
if master.exists():
    with master.open("r",encoding="utf-8-sig",errors="replace",newline="") as f:
        rd=csv.DictReader(f,delimiter="\t")
        existing=[{k:r.get(k,"") for k in fields} for r in rd]

nums=[]
for r in existing:
    m=re.fullmatch(r"TXT_(\d+)",r.get("id",""))
    if m:nums.append(int(m.group(1)))
next_id=max(nums,default=0)+1

def master_key(r):
    return "\x1f".join(r.get(k,"") for k in ("category","source_file","resource_id","offset","source_text"))

by={master_key(r):r for r in existing}
outrows=[]
for r in batch:
    item={
        "id":"",
        "category":"campaign",
        "source_file":r["source_file"],
        "resource_id":r["resource_id"],
        "offset":r["offset"],
        "context_before":r["context_before"],
        "source_text":r["source_text"],
        "context_after":r["context_after"],
        "ko_current":"",
        "ko_review":"",
        "encoding":r["encoding"],
        "max_bytes":r["max_bytes"],
        "control_tokens":r["control_tokens"],
        "linebreak_rule":r["linebreak_rule"],
        "status":"NEEDS_TRANSLATION",
        "notes":f"STEP_044 source={r['origin_label']}:{r['origin_rel']}; refs={r['references']}",
    }
    k=master_key(item)
    if k in by:
        row=by[k]
    else:
        item["id"]=f"TXT_{next_id:06d}"
        next_id+=1
        existing.append(item)
        by[k]=item
        row=item
    outrows.append(row.copy())

tmp=master.with_suffix(".tsv.tmp")
with tmp.open("w",encoding="utf-8-sig",newline="") as f:
    w=csv.DictWriter(f,fieldnames=fields,delimiter="\t",lineterminator="\n")
    w.writeheader(); w.writerows(existing)
tmp.replace(master)

next_tsv=trans/"campaign_next_translation.tsv"
with next_tsv.open("w",encoding="utf-8-sig",newline="") as f:
    w=csv.DictWriter(f,fieldnames=fields,delimiter="\t",lineterminator="\n")
    w.writeheader(); w.writerows(outrows)

ids=[r["id"] for r in existing if r["id"]]
dups=sorted({x for x in ids if ids.count(x)>1})
blank=[r["id"] for r in outrows if not r["source_text"].strip()]
report={
    "step":"STEP_044",
    "retry":"FIX3",
    "selected_source_file":selected,
    "selected_mission_number":mission_num(selected),
    "selected_unit_count":len(outrows),
    "remaining_group_counts":inventory["remaining_group_counts"],
    "used_sources":used_sources,
    "validation":{
        "batch_nonempty":bool(outrows),
        "duplicate_ids":dups,
        "blank_source_ids":blank
    },
    "known_status":{
        "D0_0130_.MDI":"VERIFIED_APPLIED_137_UNITS",
        "D0_0700_.MDI":"TRANSLATED_PENDING_APPLY_90_UNITS",
        "remaining_6_movie_playback":"DEFERRED_BY_USER",
        "stage43t_menu_after_start":"PENDING"
    }
}
(out/"campaign_discovery_report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")

with (out/"translation_validation.tsv").open("w",encoding="utf-8-sig",newline="") as f:
    f.write("check\tstatus\tdetail\n")
    f.write(f"batch_nonempty\t{'PASS' if outrows else 'FAIL'}\t{len(outrows)} rows\n")
    f.write(f"duplicate_ids\t{'PASS' if not dups else 'FAIL'}\t{'|'.join(dups)}\n")
    f.write(f"blank_source\t{'PASS' if not blank else 'FAIL'}\t{'|'.join(blank)}\n")

(out/"text_master.tsv").write_bytes(master.read_bytes())
(out/"campaign_next_translation.tsv").write_bytes(next_tsv.read_bytes())

if not outrows or dups or blank:
    raise RuntimeError("Generated translation batch failed validation")

print(json.dumps({
    "selected_source_file":selected,
    "selected_unit_count":len(outrows),
    "result_tsv":str(next_tsv),
    "structured_files_scanned":len(files),
    "remaining_groups":inventory["remaining_group_counts"]
},ensure_ascii=False,indent=2))
