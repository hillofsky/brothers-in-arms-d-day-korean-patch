#!/usr/bin/env python3
from pathlib import Path
import csv,json,re,struct,collections,hashlib,importlib.util,sys,os,shutil

ROOT=Path(r"PROJECT_ROOT")
OUT=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/"log"/"STEP_067"/"outputs"
OUT.mkdir(parents=True,exist_ok=True)

ISO=ROOT/"BIA_STAGE43T_TITLE_PROMPT_FIX.iso"
MASTER=ROOT/"translation"/"text_master.tsv"
ENTRY=ROOT/"analysis"/"stage38_translation_worklist"/"stage38_entry_map.tsv"
INV=ROOT/"log"/"STEP_064"/"outputs"/"stage43t_iso_inventory.tsv"
STEP66=ROOT/"log"/"STEP_066"/"outputs"
HELPER=ROOT/"bia_stage40i_tools"/"bia_stage40i_actual_resource_trace.py"
PARTS=["PSP_GAME","USRDIR","SYSTEM"]

def read_tsv(p):
    with p.open("r",encoding="utf-8-sig",newline="") as f:
        rd=csv.DictReader(f,delimiter="\t");return rd.fieldnames,list(rd)

def write_tsv(p,fields,rows):
    with p.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields,delimiter="\t",lineterminator="\n",extrasaction="ignore")
        w.writeheader();w.writerows(rows)

rep66=json.loads((STEP66/"step066_report.json").read_text(encoding="utf-8"))
if not rep66["d0_0700_canary"]["pass"]:
    raise RuntimeError("STEP_066 D0_0700 canary did not pass")
if rep66["unresolved_all_structural_ids"]!=198:
    raise RuntimeError(f"Expected 198 unresolved IDs, got {rep66['unresolved_all_structural_ids']}")

unresolved_ids=set(json.loads((STEP66/"unresolved_all_structural_ids.json").read_text(encoding="utf-8")))
if len(unresolved_ids)!=198:
    raise RuntimeError(f"Unresolved ID JSON count mismatch: {len(unresolved_ids)}")

mf,mrows=read_tsv(MASTER)
mby={r["resource_id"]:r for r in mrows}
missing_master=sorted(unresolved_ids-set(mby))
if missing_master: raise RuntimeError(f"Missing master IDs: {missing_master[:10]}")
targets=[mby[rid] for rid in sorted(unresolved_ids)]
texts={r["source_text"] for r in targets}
if len(texts)!=198:
    raise RuntimeError("Unexpected duplicate source texts among unresolved IDs")

ef,erows=read_tsv(ENTRY)
id_col="id" if "id" in ef else "resource_id"
keys_by_id=collections.defaultdict(set)
files_by_id=collections.defaultdict(set)
for r in erows:
    rid=r.get(id_col,"")
    if rid in unresolved_ids:
        if r.get("key"):keys_by_id[rid].add(r["key"])
        if r.get("file"):files_by_id[rid].add(r["file"])

# -------------------------------------------------------------------
# 1. Search all decoded MDI streams for the unresolved INT keys.
# This tells us whether the MDI references the localization key even though
# the English value itself is not stored as an FString there.
# -------------------------------------------------------------------
ivf,inv=read_tsv(INV)
mdi_paths=[r["path"] for r in inv if r["path"].upper().endswith(".MDI")]
sp=importlib.util.spec_from_file_location("biahelper",HELPER)
mod=importlib.util.module_from_spec(sp);sp.loader.exec_module(mod)
_,b=mod.load_helpers()

key_to_ids=collections.defaultdict(set)
for rid,ks in keys_by_id.items():
    for k in ks:key_to_ids[k].add(rid)
all_keys=sorted(key_to_ids,key=len,reverse=True)
key_regex=None
if all_keys:
    key_regex=re.compile(b"|".join(re.escape(k.encode("utf-8")+b"\0") for k in all_keys))
key_bytes_to_key={k.encode("utf-8")+b"\0":k for k in all_keys}

mdi_key_hits=[]
ids_key_in_mdi=set()
for mdi_path in mdi_paths:
    name=Path(mdi_path).name
    _,blob=b.iso_read_file(ISO,PARTS+[name])
    st={x["index"]:bytes(x["decoded"]) for x in b.parse_mdi(blob)}
    for si,d in st.items():
        if not key_regex:continue
        for m in key_regex.finditer(d):
            raw=m.group(0)
            key=key_bytes_to_key.get(raw)
            if not key:continue
            rids=sorted(key_to_ids[key])
            ids_key_in_mdi.update(rids)
            mdi_key_hits.append({
                "mdi":name,"stream":si,"offset":hex(m.start()),
                "key":key,"resource_ids":";".join(rids),
            })

write_tsv(OUT/"unresolved_mdi_key_hits.tsv",
          ["mdi","stream","offset","key","resource_ids"],mdi_key_hits)

# -------------------------------------------------------------------
# 2. Search ISO9660 files directly for the unresolved English text.
# The MDI decoder already covered compressed MDI payloads; this catches raw
# .INT, movie-side tables, menu/config assets, PRX/BIN, etc.
# -------------------------------------------------------------------
file_rows=[r for r in inv if r.get("is_dir")=="0"]
ascii_map={t.encode("utf-8"):t for t in texts if t}
utf16_map={t.encode("utf-16le"):t for t in texts if t}
ascii_regex=re.compile(b"|".join(re.escape(x) for x in sorted(ascii_map,key=len,reverse=True)))
utf16_regex=re.compile(b"|".join(re.escape(x) for x in sorted(utf16_map,key=len,reverse=True)))
maxpat=max([len(x) for x in list(ascii_map)+list(utf16_map)] or [1])
chunk_size=8*1024*1024

raw_hits=[]
raw_seen=set()
ids_raw_non_int=set()
ids_raw_movieish=set()
ids_raw_int=set()

def scan_region(f,base,size,path,encoding,rx,pmap):
    overlap=maxpat+8
    pos=0;tail=b""
    while pos<size:
        n=min(chunk_size,size-pos)
        f.seek(base+pos)
        block=f.read(n)
        if not block:break
        data=tail+block
        data_base=pos-len(tail)
        for m in rx.finditer(data):
            # Ignore duplicate matches fully contained in previous overlap.
            start=data_base+m.start()
            if start<0 or start>=size:continue
            pat=m.group(0);text=pmap.get(pat)
            if text is None:continue
            key=(path,start,encoding,text)
            if key in raw_seen:continue
            raw_seen.add(key)
            ext=Path(path).suffix.upper()
            ids=[r["resource_id"] for r in targets if r["source_text"]==text]
            if ext==".INT":ids_raw_int.update(ids)
            else:ids_raw_non_int.update(ids)
            up=path.upper()
            if ext==".BIK" or re.search(r"\.ST[1-5]$",up) or "MOV" in up or "SUB" in up:
                ids_raw_movieish.update(ids)
            raw_hits.append({
                "path":path,"extension":ext,"encoding":encoding,
                "file_offset":hex(start),"iso_absolute_offset":hex(base+start),
                "source_text":text,"resource_ids":";".join(ids),
            })
        tail=data[-overlap:] if len(data)>overlap else data
        pos+=len(block)

with ISO.open("rb") as f:
    for rec in file_rows:
        path=rec["path"];size=int(rec["size"]);base=int(rec["byte_offset"])
        # Audio-only raw files cannot contain game text in a meaningful form.
        ext=Path(path).suffix.upper()
        if ext in (".AT3",".RAW",".SB4"):
            continue
        scan_region(f,base,size,path,"UTF8/ASCII",ascii_regex,ascii_map)
        # UTF-16 scan is valuable mainly in executables/config binaries.
        if ext in (".PRX",".BIN",".ELF",".INI",".INT",".BAK",""):
            scan_region(f,base,size,path,"UTF16LE",utf16_regex,utf16_map)

write_tsv(OUT/"unresolved_iso_raw_hits.tsv",
          ["path","extension","encoding","file_offset","iso_absolute_offset","source_text","resource_ids"],raw_hits)

# -------------------------------------------------------------------
# 3. Search historical textual evidence, especially movie/subtitle stages.
# Also inventory movie/subtitle related project files even if exact English
# payload is not present in the report itself.
# -------------------------------------------------------------------
history_roots=[ROOT/"work",ROOT/"analysis",ROOT/"log"]
text_exts={".json",".tsv",".csv",".txt",".md",".py",".ps1"}
movie_name_re=re.compile(r"(movie|subtitle|sub_|stage41|stage42|bik|caption|st[1-5])",re.I)
english_regex=re.compile("|".join(re.escape(t) for t in sorted(texts,key=len,reverse=True)))
id_regex=re.compile("|".join(re.escape(x) for x in sorted(unresolved_ids)))

history_hits=[]
movie_inventory=[]
evidence_dir=OUT/"history_evidence_files"
evidence_dir.mkdir(exist_ok=True)
copied_hash=set();copied_rows=[];copied_bytes=0
ids_history=set();ids_movie_history=set()

def maybe_copy(p,data):
    global copied_bytes
    h=hashlib.sha256(data).hexdigest()
    if h in copied_hash or len(data)>5*1024*1024 or copied_bytes+len(data)>30*1024*1024:
        return
    copied_hash.add(h);copied_bytes+=len(data)
    rel=str(p.relative_to(ROOT))
    safe=re.sub(r'[^A-Za-z0-9._\-가-힣]+','_',rel)
    if len(safe)>220:safe=safe[-220:]
    (evidence_dir/safe).write_bytes(data)
    copied_rows.append({"source":rel,"copy_name":safe,"size":len(data),"sha256":h})

for sroot in history_roots:
    if not sroot.exists():continue
    for p in sroot.rglob("*"):
        try:
            if not p.is_file():continue
            rel=str(p.relative_to(ROOT))
            if movie_name_re.search(rel):
                movie_inventory.append({"path":rel,"size":p.stat().st_size,"suffix":p.suffix.lower()})
            if p.suffix.lower() not in text_exts or p.stat().st_size>20*1024*1024:
                continue
            data=p.read_bytes()
            text=data.decode("utf-8-sig",errors="replace")
            matched_ids=set(id_regex.findall(text))
            matched_texts=set(english_regex.findall(text))
            if not matched_ids and not matched_texts:
                continue
            for rid in matched_ids:
                if rid in unresolved_ids:
                    ids_history.add(rid)
                    if movie_name_re.search(rel):ids_movie_history.add(rid)
            for t in matched_texts:
                for r in targets:
                    if r["source_text"]==t:
                        ids_history.add(r["resource_id"])
                        if movie_name_re.search(rel):ids_movie_history.add(r["resource_id"])
            history_hits.append({
                "path":rel,
                "movie_related_name":int(bool(movie_name_re.search(rel))),
                "matched_resource_ids":";".join(sorted(x for x in matched_ids if x in unresolved_ids)),
                "matched_source_count":len(matched_texts),
                "matched_sources_json":json.dumps(sorted(matched_texts),ensure_ascii=False)[:20000],
            })
            if movie_name_re.search(rel):
                maybe_copy(p,data)
        except Exception:
            pass

write_tsv(OUT/"unresolved_history_hits.tsv",
          ["path","movie_related_name","matched_resource_ids","matched_source_count","matched_sources_json"],history_hits)
write_tsv(OUT/"movie_subtitle_file_inventory.tsv",
          ["path","size","suffix"],movie_inventory)
write_tsv(OUT/"history_evidence_files.tsv",
          ["source","copy_name","size","sha256"],copied_rows)

# -------------------------------------------------------------------
# 4. Per-ID classification for next patch stage.
# -------------------------------------------------------------------
raw_by_id=collections.defaultdict(list)
for h in raw_hits:
    for rid in h["resource_ids"].split(";"):
        if rid:raw_by_id[rid].append(h)

keyhit_by_id=collections.defaultdict(list)
for h in mdi_key_hits:
    for rid in h["resource_ids"].split(";"):
        if rid:keyhit_by_id[rid].append(h)

classes=collections.Counter()
class_rows=[]
for r in targets:
    rid=r["resource_id"];hits=raw_by_id[rid];kh=keyhit_by_id[rid]
    exts=sorted({h["extension"] for h in hits})
    non_int=[h for h in hits if h["extension"]!=".INT"]
    movie_raw=[h for h in hits if h["extension"]==".BIK" or re.search(r"\.ST[1-5]$",h["path"],re.I)]
    movie_hist=rid in ids_movie_history

    # This is an evidence class, not a claim about runtime behavior.
    if movie_raw or movie_hist:
        cls="MOVIE_SUBTITLE_EVIDENCE"
    elif non_int:
        cls="RAW_NON_INT_ASSET"
    elif kh:
        cls="MDI_KEY_REFERENCE_BUT_VALUE_EXTERNAL"
    elif hits:
        cls="INT_RAW_ONLY"
    else:
        cls="NO_RAW_OR_MDI_KEY_EVIDENCE"
    classes[cls]+=1
    class_rows.append({
        "resource_id":rid,
        "source_files":";".join(sorted(files_by_id[rid])),
        "source_text":r["source_text"],
        "korean":r.get("ko_review") or r.get("ko_current"),
        "classification":cls,
        "mdi_key_hit_count":len(kh),
        "mdi_key_mdis":";".join(sorted({x["mdi"] for x in kh})),
        "raw_hit_count":len(hits),
        "raw_extensions":";".join(exts),
        "raw_non_int_paths":";".join(sorted({x["path"] for x in non_int})),
        "history_evidence":int(rid in ids_history),
        "movie_history_evidence":int(movie_hist),
    })

write_tsv(OUT/"unresolved_198_classification.tsv",
          ["resource_id","source_files","source_text","korean","classification","mdi_key_hit_count","mdi_key_mdis","raw_hit_count","raw_extensions","raw_non_int_paths","history_evidence","movie_history_evidence"],class_rows)

# Source group summary.
group_rows=[]
by_file=collections.defaultdict(list)
for r in class_rows:
    for f in r["source_files"].split(";"):
        if f:by_file[f].append(r)
for f,rr in sorted(by_file.items()):
    cc=collections.Counter(x["classification"] for x in rr)
    group_rows.append({
        "source_file":f,"unresolved_ids":len({x["resource_id"] for x in rr}),
        "class_counts_json":json.dumps(cc,ensure_ascii=False),
    })
write_tsv(OUT/"unresolved_source_group_summary.tsv",
          ["source_file","unresolved_ids","class_counts_json"],group_rows)

report={
    "step":"STEP_067",
    "status":"VERIFIED",
    "input_unresolved_ids":len(unresolved_ids),
    "mdi_key_hits":len(mdi_key_hits),
    "ids_with_mdi_key_evidence":len(ids_key_in_mdi),
    "iso_raw_hits":len(raw_hits),
    "ids_with_raw_int_hit":len(ids_raw_int),
    "ids_with_raw_non_int_hit":len(ids_raw_non_int),
    "ids_with_raw_movieish_hit":len(ids_raw_movieish),
    "history_files_with_hits":len(history_hits),
    "ids_with_history_evidence":len(ids_history),
    "ids_with_movie_history_evidence":len(ids_movie_history),
    "classification_counts":dict(classes),
    "movie_related_files_in_project":len(movie_inventory),
    "movie_evidence_files_copied":len(copied_rows),
    "iso_modified":False,
    "movie_validation_resumed":False,
    "next_phase":"RECONCILE_MOVIE_ALREADY_APPLIED_AND_NON_MDI_LOCALIZATION_CLASSES",
}
(OUT/"step067_report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(report,ensure_ascii=False))
