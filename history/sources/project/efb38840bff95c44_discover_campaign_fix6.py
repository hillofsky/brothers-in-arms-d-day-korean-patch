#!/usr/bin/env python3
from pathlib import Path
import argparse,csv,json,re,hashlib,shutil,sys

ap=argparse.ArgumentParser()
ap.add_argument("--project-root",required=True)
ap.add_argument("--legacy-root",required=True)
ap.add_argument("--out-dir",required=True)
a=ap.parse_args()

root=Path(a.project_root)
legacy=Path(a.legacy_root)
out=Path(a.out_dir)
trans=root/"translation"
out.mkdir(parents=True,exist_ok=True)
trans.mkdir(parents=True,exist_ok=True)

FIRST="D0_0130_.MDI"
SECOND="D0_0700_.MDI"
MISSION_RE=re.compile(r'D0_[0-9A-Za-z_]+\.MDI',re.I)
STRUCT_EXT={".json",".tsv",".csv",".jsonl",".ndjson"}
TEXT_EXT={".py",".ps1",".md",".txt",".json",".tsv",".csv"}
SKIP_DIRS={"log","logs","incoming",".git","__pycache__","cache","temp","tmp","python_deps"}
MARKERS=[
    "first_campaign_units","campaign_first_units","campaign_second_units",
    "campaign_first_reference_audit","campaign_second_reference_audit",
    "D0_0130_.MDI","D0_0700_.MDI","1302","priority-b","priority_b",
    "campaign_units","reference_audit"
]

def mission_num(s):
    m=re.search(r'D0_(\d+)',s or "",re.I)
    return int(m.group(1)) if m else 10**9

def norm_mission(v):
    if v is None:return ""
    m=MISSION_RE.search(str(v).replace("\\","/"))
    return m.group(0) if m else ""

def ci(d,*names):
    if not isinstance(d,dict): return None
    low={str(k).lower():k for k in d}
    for n in names:
        k=low.get(n.lower())
        if k is not None:
            v=d[k]
            if v not in (None,"",[],{}): return v
    return None

def source_text(d):
    for n in ("english","source_text","original_text","original","text","string",
              "source","eng","en","text_en","english_text"):
        v=ci(d,n)
        if isinstance(v,str) and len(v.strip())>=2:
            if MISSION_RE.fullmatch(v.strip()):continue
            return v
    return None

def infer_mission(d,path=()):
    if isinstance(d,dict):
        for n in ("source_file","file","mdi","container_file","mission_file","asset","package"):
            m=norm_mission(ci(d,n))
            if m:return m
        for k,v in d.items():
            m=norm_mission(k)
            if m:return m
            if isinstance(v,str):
                m=norm_mission(v)
                if m:return m
    for p in reversed(path):
        m=norm_mission(p)
        if m:return m
    return ""

def get_offset(d):
    v=ci(d,"offset","offset_hex","file_offset","data_offset","address","va")
    if v is None:return ""
    return f"0x{v:X}" if isinstance(v,int) else str(v)

def get_refs(d):
    v=ci(d,"references","refs","reference","locations","uses")
    if v is None:return ""
    if isinstance(v,str):return v
    try:return json.dumps(v,ensure_ascii=False,separators=(",",":"))
    except:return str(v)

def control_tokens(s):
    vals=[]
    for pat in (r'\\[nrt]',r'\{[^{}]+\}',r'%[-+0-9.]*[A-Za-z]',r'<[^<>]+>',r'\^[A-Za-z0-9_]*'):
        vals.extend(re.findall(pat,s))
    return "|".join(dict.fromkeys(vals))

def walk(obj,path=(),mission=""):
    local=mission or infer_mission(obj,path)
    if isinstance(obj,dict):
        s=source_text(obj)
        if s and local:
            yield path,local,obj,s
        for k,v in obj.items():
            child=local or norm_mission(k) or infer_mission(v,path+(str(k),))
            yield from walk(v,path+(str(k),),child)
    elif isinstance(obj,list):
        for i,v in enumerate(obj):
            yield from walk(v,path+(str(i),),local)

def skipped(p,base):
    try: parts=p.relative_to(base).parts[:-1]
    except: return False
    return bool({x.lower() for x in parts}&SKIP_DIRS)

def structured_files(base,label):
    if not base.exists():return []
    arr=[]
    for p in base.rglob("*"):
        if not p.is_file() or p.suffix.lower() not in STRUCT_EXT or skipped(p,base):continue
        try:size=p.stat().st_size
        except:continue
        if not (0<size<=150*1024*1024):continue
        arr.append((label,base,p,size))
    return arr

sources=structured_files(root,"D_BIA")+structured_files(legacy,"LEGACY_CODEX")
records=[]
stats=[]
errors=[]

for label,base,p,size in sources:
    before=len(records); missions=set()
    try:
        if p.suffix.lower()==".json":
            obj=json.loads(p.read_text(encoding="utf-8-sig"))
            fm=norm_mission(str(p.relative_to(base)))
            for path,m,d,s in walk(obj,(),fm):
                missions.add(m)
                records.append({
                    "source_file":m,
                    "resource_id":str(ci(d,"resource_id","unit_id","id","key","text_id","index") or ""),
                    "offset":get_offset(d),
                    "context_before":str(ci(d,"context_before","before","prev") or ""),
                    "source_text":s,
                    "context_after":str(ci(d,"context_after","after","next") or ""),
                    "encoding":str(ci(d,"encoding") or "UTF-8"),
                    "max_bytes":str(ci(d,"max_bytes","field_bytes","byte_limit","size_limit") or ""),
                    "control_tokens":str(ci(d,"control_tokens") or control_tokens(s)),
                    "linebreak_rule":str(ci(d,"linebreak_rule","wrap_rule") or ""),
                    "references":get_refs(d),
                    "origin_label":label,"origin_file":str(p),
                    "origin_rel":str(p.relative_to(base)),
                })
        elif p.suffix.lower() in (".jsonl",".ndjson"):
            with p.open("r",encoding="utf-8-sig",errors="replace") as f:
                for line_no,line in enumerate(f,1):
                    line=line.strip()
                    if not line:continue
                    try: obj=json.loads(line)
                    except:continue
                    for path,m,d,s in walk(obj,(str(line_no),),norm_mission(str(p))):
                        missions.add(m)
                        records.append({
                            "source_file":m,
                            "resource_id":str(ci(d,"resource_id","unit_id","id","key","text_id","index") or ""),
                            "offset":get_offset(d),
                            "context_before":str(ci(d,"context_before","before","prev") or ""),
                            "source_text":s,
                            "context_after":str(ci(d,"context_after","after","next") or ""),
                            "encoding":str(ci(d,"encoding") or "UTF-8"),
                            "max_bytes":str(ci(d,"max_bytes","field_bytes","byte_limit","size_limit") or ""),
                            "control_tokens":str(ci(d,"control_tokens") or control_tokens(s)),
                            "linebreak_rule":str(ci(d,"linebreak_rule","wrap_rule") or ""),
                            "references":get_refs(d),
                            "origin_label":label,"origin_file":str(p),
                            "origin_rel":str(p.relative_to(base)),
                        })
        else:
            delim="\t" if p.suffix.lower()==".tsv" else ","
            with p.open("r",encoding="utf-8-sig",errors="replace",newline="") as f:
                rd=csv.DictReader(f,delimiter=delim)
                for d in rd:
                    m=infer_mission(d) or norm_mission(str(p.relative_to(base)))
                    s=source_text(d)
                    if not m or not s:continue
                    missions.add(m)
                    records.append({
                        "source_file":m,
                        "resource_id":str(ci(d,"resource_id","unit_id","id","key","text_id","index") or ""),
                        "offset":get_offset(d),
                        "context_before":str(ci(d,"context_before","before","prev") or ""),
                        "source_text":s,
                        "context_after":str(ci(d,"context_after","after","next") or ""),
                        "encoding":str(ci(d,"encoding") or "UTF-8"),
                        "max_bytes":str(ci(d,"max_bytes","field_bytes","byte_limit","size_limit") or ""),
                        "control_tokens":str(ci(d,"control_tokens") or control_tokens(s)),
                        "linebreak_rule":str(ci(d,"linebreak_rule","wrap_rule") or ""),
                        "references":get_refs(d),
                        "origin_label":label,"origin_file":str(p),
                        "origin_rel":str(p.relative_to(base)),
                    })
        if len(records)>before or missions:
            stats.append({"label":label,"file":str(p),"size":size,
                          "records":len(records)-before,
                          "missions":sorted(missions,key=lambda x:(mission_num(x),x))})
    except Exception as e:
        errors.append({"label":label,"file":str(p),"error":repr(e)})

# Deduplicate; PROJECT_ROOT wins over legacy.
def score(r):
    return (100 if r["origin_label"]=="D_BIA" else 0)+sum(
        bool(r[k]) for k in ("resource_id","offset","context_before","context_after","max_bytes","references")
    )
ded={}
for r in records:
    k=(r["source_file"].upper(),r["resource_id"],r["offset"],r["source_text"])
    if k not in ded or score(r)>score(ded[k]):ded[k]=r
records=list(ded.values())

groups={}
for r in records:
    if r["source_file"].upper() in {FIRST.upper(),SECOND.upper()}:continue
    groups.setdefault(r["source_file"],[]).append(r)

# Always gather source-code evidence about how first/second campaign extraction was built.
evidence_dir=out/"source_evidence"
evidence_dir.mkdir(exist_ok=True)
source_hits=[]
roots=[("D_BIA",root),("LEGACY_CODEX",legacy)]
for label,base in roots:
    if not base.exists():continue
    for p in base.rglob("*"):
        if not p.is_file() or p.suffix.lower() not in TEXT_EXT or skipped(p,base):continue
        try:
            if p.stat().st_size>8*1024*1024:continue
            txt=p.read_text(encoding="utf-8-sig",errors="ignore")
        except:continue
        low=txt.lower()
        hits=[m for m in MARKERS if m.lower() in low]
        missions=sorted(set(MISSION_RE.findall(txt)),key=lambda x:(mission_num(x),x))
        if hits or len(missions)>=2:
            source_hits.append({
                "label":label,"file":str(p),"size":p.stat().st_size,
                "markers":hits,"missions":missions[:100]
            })

# Rank and copy the most useful source files into result ZIP.
def hit_rank(h):
    return (-len(h["markers"]),-len(h["missions"]),h["size"],h["file"])
source_hits.sort(key=hit_rank)
copied=[]
for i,h in enumerate(source_hits[:40],1):
    p=Path(h["file"])
    ext=p.suffix.lower()
    # Do not copy large JSON datasets here; only source/text evidence <=2MiB.
    if p.stat().st_size>2*1024*1024:continue
    safe=re.sub(r'[^A-Za-z0-9_.-]+','_',p.name)
    dst=evidence_dir/f"{i:02d}_{safe}"
    try:
        shutil.copy2(p,dst)
        copied.append({"source":str(p),"copied":str(dst.name),
                       "markers":h["markers"],"missions":h["missions"]})
    except Exception:pass

inventory={
    "step":"STEP_044_FIX6",
    "structured_files_scanned":len(sources),
    "structured_files_with_records":stats,
    "parse_errors":errors,
    "deduplicated_records":len(records),
    "remaining_group_counts":{k:len(v) for k,v in sorted(groups.items(),key=lambda kv:(mission_num(kv[0]),kv[0]))},
    "source_code_hits":source_hits[:100],
    "source_evidence_copied":copied,
}
(out/"candidate_inventory.json").write_text(json.dumps(inventory,ensure_ascii=False,indent=2),encoding="utf-8")

with (out/"source_code_hits.tsv").open("w",encoding="utf-8-sig",newline="") as f:
    cols=["label","file","size","markers","missions"]
    w=csv.DictWriter(f,fieldnames=cols,delimiter="\t",lineterminator="\n")
    w.writeheader()
    for h in source_hits[:200]:
        w.writerow({"label":h["label"],"file":h["file"],"size":h["size"],
                    "markers":"|".join(h["markers"]),"missions":"|".join(h["missions"])})

if not groups:
    raise RuntimeError(
        "No remaining campaign group exists in current structured datasets. "
        "Source-code evidence for the campaign extractor was collected into source_evidence/ "
        "and source_code_hits.tsv."
    )

# Select next mission.
after=sorted((mission_num(k),k) for k in groups if mission_num(k)>700)
selected=after[0][1] if after else min(groups,key=lambda k:(mission_num(k),k))
batch=groups[selected]
batch.sort(key=lambda r:(r["offset"]=="",r["offset"],r["resource_id"],r["source_text"]))

fields=["id","category","source_file","resource_id","offset","context_before","source_text",
        "context_after","ko_current","ko_review","encoding","max_bytes","control_tokens",
        "linebreak_rule","status","notes"]
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

def mkey(r):return "\x1f".join(r.get(k,"") for k in ("category","source_file","resource_id","offset","source_text"))
by={mkey(r):r for r in existing}
batch_rows=[]
for r in batch:
    x={
        "id":"","category":"campaign","source_file":r["source_file"],"resource_id":r["resource_id"],
        "offset":r["offset"],"context_before":r["context_before"],"source_text":r["source_text"],
        "context_after":r["context_after"],"ko_current":"","ko_review":"","encoding":r["encoding"],
        "max_bytes":r["max_bytes"],"control_tokens":r["control_tokens"],
        "linebreak_rule":r["linebreak_rule"],"status":"NEEDS_TRANSLATION",
        "notes":f"STEP_044 source={r['origin_label']}:{r['origin_rel']}; refs={r['references']}",
    }
    k=mkey(x)
    if k in by: row=by[k]
    else:
        x["id"]=f"TXT_{next_id:06d}";next_id+=1
        existing.append(x);by[k]=x;row=x
    batch_rows.append(row.copy())

tmp=master.with_suffix(".tmp")
with tmp.open("w",encoding="utf-8-sig",newline="") as f:
    w=csv.DictWriter(f,fieldnames=fields,delimiter="\t",lineterminator="\n");w.writeheader();w.writerows(existing)
tmp.replace(master)

batch_tsv=trans/"campaign_next_translation.tsv"
with batch_tsv.open("w",encoding="utf-8-sig",newline="") as f:
    w=csv.DictWriter(f,fieldnames=fields,delimiter="\t",lineterminator="\n");w.writeheader();w.writerows(batch_rows)

ids=[r["id"] for r in existing if r["id"]]
dups=sorted({x for x in ids if ids.count(x)>1})
blanks=[r["id"] for r in batch_rows if not r["source_text"].strip()]
report={
    "step":"STEP_044_FIX6","selected_source_file":selected,
    "selected_unit_count":len(batch_rows),
    "remaining_group_counts":inventory["remaining_group_counts"],
    "validation":{"duplicate_ids":dups,"blank_source_ids":blanks,"batch_nonempty":bool(batch_rows)}
}
(out/"campaign_discovery_report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
(out/"campaign_next_translation.tsv").write_bytes(batch_tsv.read_bytes())
(out/"text_master.tsv").write_bytes(master.read_bytes())
if dups or blanks or not batch_rows:raise RuntimeError("Generated batch validation failed")
print(json.dumps({"selected":selected,"units":len(batch_rows)},ensure_ascii=False))
