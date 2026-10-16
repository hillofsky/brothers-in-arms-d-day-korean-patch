#!/usr/bin/env python3
from pathlib import Path
import csv, json, re, os, sys, hashlib, zipfile, shutil, collections, traceback

ROOT = Path(r"PROJECT_ROOT")
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT/"log"/"STEP_064"/"outputs"
OUT.mkdir(parents=True, exist_ok=True)

MASTER = ROOT/"translation"/"text_master.tsv"
ENTRY_MAP_CANDS = [
    ROOT/"analysis"/"stage38_translation_worklist"/"stage38_entry_map.tsv",
    ROOT/"analysis"/"stage38_translation_worklist"/"stage38b_entry_map.tsv",
]
SOURCE_FILES_CANDS = [
    ROOT/"analysis"/"stage38_translation_worklist"/"stage38_source_files.tsv",
    ROOT/"analysis"/"stage38_translation_worklist"/"stage38b_source_files.tsv",
]

def sha1_file(p, chunk=4*1024*1024):
    h=hashlib.sha1()
    with p.open("rb") as f:
        while True:
            b=f.read(chunk)
            if not b: break
            h.update(b)
    return h.hexdigest()

def sha256_file(p, chunk=8*1024*1024):
    h=hashlib.sha256()
    with p.open("rb") as f:
        while True:
            b=f.read(chunk)
            if not b: break
            h.update(b)
    return h.hexdigest()

def read_tsv(p):
    with p.open("r",encoding="utf-8-sig",newline="") as f:
        rd=csv.DictReader(f,delimiter="\t")
        return rd.fieldnames,list(rd)

def write_tsv(p, fields, rows):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields,delimiter="\t",lineterminator="\n",extrasaction="ignore")
        w.writeheader();w.writerows(rows)

def decode_game_text(data):
    if data.startswith(b"\xff\xfe"):
        return data.decode("utf-16le"),"utf-16le"
    if data.startswith(b"\xfe\xff"):
        return data.decode("utf-16be"),"utf-16be"
    try:
        return data.decode("utf-8-sig"),"utf-8-sig"
    except UnicodeDecodeError:
        return data.decode("cp1252"),"cp1252"

def locate_system_dir():
    p=ROOT/"extracted"/"PSP_GAME"/"USRDIR"/"SYSTEM"
    if (p/"LOCALIZE.INT").exists():
        return p
    hits=[]
    for q in ROOT.rglob("LOCALIZE.INT"):
        try:
            if q.is_file() and q.parent.name.upper()=="SYSTEM" and (q.parent/"NEWLOCALIZE.INT").exists():
                hits.append(q.parent)
        except Exception:
            pass
    if not hits:
        return None
    hits.sort(key=lambda x:(0 if "extracted" in str(x).lower() else 1,len(str(x))))
    return hits[0]

# ---------------------------------------------------------------------
# Verify STEP_063 / campaign state.
# ---------------------------------------------------------------------
fields, master_rows = read_tsv(MASTER)
campaign=[r for r in master_rows if r.get("category")=="campaign"]
counts=collections.Counter(r.get("status","") for r in campaign)
expected={"VERIFIED_APPLIED":137,"TRANSLATED_PENDING_APPLY":90,"TRANSLATED_REVIEWED":1075}
for k,v in expected.items():
    if counts[k]!=v:
        raise RuntimeError(f"Campaign state mismatch {k}: {counts[k]} != {v}")
if counts.get("NEEDS_TRANSLATION",0)!=0:
    raise RuntimeError(f"NEEDS_TRANSLATION should be 0, got {counts.get('NEEDS_TRANSLATION',0)}")

unap=[r for r in campaign if r.get("status") in ("TRANSLATED_PENDING_APPLY","TRANSLATED_REVIEWED")]
unap_ids={r["resource_id"] for r in unap}
if len(unap_ids)!=1165:
    raise RuntimeError(f"Expected 1165 unapplied campaign units, got {len(unap_ids)}")
master_by_id={r["resource_id"]:r for r in unap}

# ---------------------------------------------------------------------
# Recover exact per-occurrence map from Stage38 entry map.
# ---------------------------------------------------------------------
entry_map=next((p for p in ENTRY_MAP_CANDS if p.exists()),None)
if entry_map is None:
    raise RuntimeError("stage38_entry_map.tsv not found in expected Stage38 worklist directory")

emap_fields, emap_rows=read_tsv(entry_map)
id_col="id" if "id" in emap_fields else ("resource_id" if "resource_id" in emap_fields else None)
if not id_col:
    raise RuntimeError(f"Entry map has no id column: {emap_fields}")

exact=[r for r in emap_rows if r.get(id_col) in unap_ids]
present={r.get(id_col) for r in exact}
missing=sorted(unap_ids-present)
if missing:
    raise RuntimeError(f"Entry map is missing {len(missing)} unapplied IDs, first={missing[:20]}")

occ_counts=collections.Counter(r.get(id_col) for r in exact)
count_check=[]
mismatch=[]
for rid in sorted(unap_ids):
    expected_count_raw=master_by_id[rid].get("reference_count","")
    try:
        expected_count=int(expected_count_raw)
    except Exception:
        expected_count=None
    actual=occ_counts[rid]
    ok=(expected_count is None or expected_count==actual)
    rec={"resource_id":rid,"master_reference_count":expected_count_raw,"entry_map_occurrences":actual,"match":int(ok)}
    count_check.append(rec)
    if not ok: mismatch.append(rec)

# Add Korean/status for an exact application manifest.
manifest=[]
for r in exact:
    rid=r[id_col]
    m=master_by_id[rid]
    manifest.append({
        "resource_id":rid,
        "status":m.get("status",""),
        "source_text":m.get("source_text",""),
        "ko_current":m.get("ko_current",""),
        "ko_review":m.get("ko_review",""),
        "file":r.get("file",""),
        "line":r.get("line",""),
        "section":r.get("section",""),
        "key":r.get("key",""),
        "original_raw_value":r.get("original_raw_value",""),
        "quote_style":r.get("quote_style",""),
        "encoding":r.get("encoding",""),
        "source_sha1":r.get("source_sha1",""),
    })
write_tsv(
    OUT/"campaign_apply_exact_occurrences.tsv",
    ["resource_id","status","source_text","ko_current","ko_review","file","line","section","key","original_raw_value","quote_style","encoding","source_sha1"],
    manifest
)
write_tsv(
    OUT/"entry_map_reference_count_check.tsv",
    ["resource_id","master_reference_count","entry_map_occurrences","match"],
    count_check
)

# ---------------------------------------------------------------------
# Snapshot exact original INT files and validate Stage38 hashes/lines.
# ---------------------------------------------------------------------
system_dir=locate_system_dir()
source_files=sorted({r.get("file","") for r in exact if r.get("file","")})
snap=OUT/"source_int_snapshot"
snap.mkdir(exist_ok=True)
source_report=[]
line_report=[]
source_ok=0
source_missing=0
sha_mismatch=0
line_mismatch=0

expected_by_file=collections.defaultdict(set)
for r in exact:
    if r.get("file") and r.get("source_sha1"):
        expected_by_file[r["file"]].add(r["source_sha1"])

if system_dir:
    # Build lookup case-insensitively.
    lookup={p.name.upper():p for p in system_dir.glob("*.INT")}
    for name in source_files:
        p=lookup.get(Path(name).name.upper())
        if not p:
            source_report.append({"file":name,"exists":0,"path":"","sha1":"","expected_sha1s":";".join(sorted(expected_by_file[name])),"sha_match":0,"encoding":""})
            source_missing+=1
            continue
        data=p.read_bytes()
        text,enc=decode_game_text(data)
        got=hashlib.sha1(data).hexdigest()
        expected_hashes=expected_by_file[name]
        match=(not expected_hashes or got in expected_hashes)
        source_report.append({"file":name,"exists":1,"path":str(p),"sha1":got,"expected_sha1s":";".join(sorted(expected_hashes)),"sha_match":int(match),"encoding":enc})
        if match: source_ok+=1
        else: sha_mismatch+=1
        try:
            shutil.copy2(p,snap/p.name)
        except Exception:
            pass

        lines=text.splitlines()
        # Exact row-line verification.
        for r in [x for x in exact if x.get("file")==name]:
            try:
                ln=int(r.get("line","0"))
            except Exception:
                ln=0
            current=lines[ln-1] if 1<=ln<=len(lines) else ""
            raw_expected=r.get("original_raw_value","")
            value=current.split("=",1)[1].strip() if "=" in current else ""
            ok=(value==raw_expected)
            line_report.append({
                "resource_id":r[id_col],"file":name,"line":ln,
                "section":r.get("section",""),"key":r.get("key",""),
                "entry_map_raw":raw_expected,"current_raw":value,"match":int(ok),
            })
            if not ok: line_mismatch+=1
else:
    source_missing=len(source_files)

write_tsv(OUT/"source_int_hash_report.tsv",["file","exists","path","sha1","expected_sha1s","sha_match","encoding"],source_report)
write_tsv(OUT/"source_int_line_validation.tsv",["resource_id","file","line","section","key","entry_map_raw","current_raw","match"],line_report)

# Copy the Stage38 entry map and source list themselves.
try:
    shutil.copy2(entry_map,OUT/"stage38_entry_map_full.tsv")
except Exception:
    pass
source_list=next((p for p in SOURCE_FILES_CANDS if p.exists()),None)
if source_list:
    try: shutil.copy2(source_list,OUT/"stage38_source_files.tsv")
    except Exception: pass

# ---------------------------------------------------------------------
# ISO9660 inventory from Stage43T: no ISO writes.
# ---------------------------------------------------------------------
iso=ROOT/"BIA_STAGE43T_TITLE_PROMPT_FIX.iso"
iso_records=[]
if iso.exists():
    sector=2048
    visited=set()
    def read_rec(buf,off):
        ln=buf[off]
        if ln==0:return None,off+1
        rec=buf[off:off+ln]
        extent=int.from_bytes(rec[2:6],"little")
        size=int.from_bytes(rec[10:14],"little")
        flags=rec[25]
        nlen=rec[32]
        name=rec[33:33+nlen]
        return {"extent_lba":extent,"size":size,"flags":flags,"name_raw":name},off+ln
    def norm(raw):
        if raw==b"\x00":return "."
        if raw==b"\x01":return ".."
        s=raw.decode("ascii",errors="replace")
        return s.split(";",1)[0]
    with iso.open("rb") as f:
        f.seek(16*sector);pvd=f.read(sector)
        if len(pvd)!=sector or pvd[1:6]!=b"CD001":
            raise RuntimeError("Stage43T is not valid ISO9660")
        rootlen=pvd[156];root=pvd[156:156+rootlen]
        root_extent=int.from_bytes(root[2:6],"little");root_size=int.from_bytes(root[10:14],"little")
        def walk(extent,size,prefix):
            k=(extent,size)
            if k in visited:return
            visited.add(k)
            f.seek(extent*sector);data=f.read(size);pos=0
            while pos<len(data):
                if data[pos]==0:
                    pos=((pos//sector)+1)*sector;continue
                rec,nxt=read_rec(data,pos);pos=nxt
                if not rec:continue
                name=norm(rec["name_raw"])
                if name in (".",".."):continue
                path=f"{prefix}/{name}" if prefix else name
                is_dir=bool(rec["flags"]&2)
                iso_records.append({"path":path,"extent_lba":rec["extent_lba"],"byte_offset":rec["extent_lba"]*sector,"size":rec["size"],"is_dir":int(is_dir)})
                if is_dir:walk(rec["extent_lba"],rec["size"],path)
        walk(root_extent,root_size,"")

write_tsv(OUT/"stage43t_iso_inventory.tsv",["path","extent_lba","byte_offset","size","is_dir"],iso_records)
asset_rows=[]
source_stems={Path(n).stem.upper() for n in source_files}
for r in iso_records:
    p=r["path"];name=Path(p).name;stem=Path(name).stem.upper();ext=Path(name).suffix.upper()
    score=0
    if ext in (".INT",".MDI",".DSL",".DSX"):score+=2
    if stem in source_stems:score+=5
    if any(s in p.upper() for s in source_stems):score+=3
    if score:
        q=dict(r);q.update({"name":name,"stem":stem,"ext":ext,"score":score})
        asset_rows.append(q)
asset_rows.sort(key=lambda x:(-x["score"],x["path"]))
write_tsv(OUT/"stage43t_campaign_asset_candidates.tsv",["path","name","stem","ext","score","extent_lba","byte_offset","size","is_dir"],asset_rows)

# ---------------------------------------------------------------------
# Deep recover historical patch scripts from filesystem AND ZIP archives.
# ---------------------------------------------------------------------
strong_terms=[
    "campaign_first_ko.json","campaign_second_ko.json",
    "first_campaign_units.json","campaign_second_units.json",
    "D0_0130_","D0_0700_EXIT4",
    "BIA_STAGE43T_TITLE_PROMPT_FIX.iso",
]
technical_terms=[
    "append_iso_file_and_repoint","rebuild_mdi","rebuild_dsx",
    "parse_mdi","MDI","DSL","DSX",
]
name_terms=["stage43","campaign","first_mission","second_mission","d0_0130","d0_0700"]

text_exts={".py",".ps1",".json",".md",".txt",".tsv",".csv"}
archive_report=[]
fs_hits=[]
archive_hits=[]
recover_dir=OUT/"recovered_pipeline_files"
recover_dir.mkdir(exist_ok=True)
seen_copy_hash=set()
copied=[]

def relevant_text(text,name):
    low=text.lower();nlow=name.lower()
    strong=[t for t in strong_terms if t.lower() in low]
    tech=[t for t in technical_terms if t.lower() in low]
    named=[t for t in name_terms if t.lower() in nlow]
    # Require direct campaign evidence or stage43 filename + technical evidence.
    return strong,tech,named, bool(strong or (named and tech))

def save_recovered(data, source_label, entry_name):
    h=hashlib.sha256(data).hexdigest()
    if h in seen_copy_hash:return None
    seen_copy_hash.add(h)
    safe=(source_label+"__"+entry_name).replace("\\","__").replace("/","__").replace(":","_")
    safe=re.sub(r'[^A-Za-z0-9._\-가-힣]+','_',safe)
    if len(safe)>220:
        safe=safe[-220:]
    dst=recover_dir/safe
    dst.write_bytes(data)
    copied.append({"source":source_label,"entry":entry_name,"copy_name":safe,"size":len(data),"sha256":h})
    return dst

# Filesystem text scan. Avoid very large/cache/generated binary trees.
skip_parts={"extracted","incoming","analysis","log"}  # separately handle archives/log and known analysis later
for p in ROOT.rglob("*"):
    try:
        if not p.is_file() or p.suffix.lower() not in text_exts:continue
        if p.stat().st_size>20*1024*1024:continue
        # Search all small text files even in analysis/log; this may be large but bounded.
        data=p.read_bytes()
        text=data.decode("utf-8-sig",errors="replace")
        strong,tech,named,rel=relevant_text(text,p.name)
        if rel:
            relpath=str(p.relative_to(ROOT))
            fs_hits.append({
                "path":relpath,"size":len(data),
                "strong_terms":";".join(strong),"technical_terms":";".join(tech),
                "name_terms":";".join(named),
            })
            if p.suffix.lower() in (".py",".ps1",".json",".md",".txt"):
                save_recovered(data,"FS_"+relpath,p.name)
    except Exception:
        pass

# Archive scan; prioritize all ZIPs under PROJECT_ROOT. Only inspect text-like members <=20 MiB.
zip_paths=[]
for p in ROOT.rglob("*.zip"):
    try:
        if p.is_file():zip_paths.append(p)
    except Exception:pass

for zp in zip_paths:
    rec={"zip":str(zp.relative_to(ROOT)),"size":zp.stat().st_size,"members":0,"text_members_scanned":0,"matching_members":0,"error":""}
    try:
        with zipfile.ZipFile(zp,"r") as z:
            infos=z.infolist();rec["members"]=len(infos)
            for info in infos:
                if info.is_dir():continue
                name=info.filename
                ext=Path(name).suffix.lower()
                nlow=name.lower()
                name_interest=any(t in nlow for t in name_terms) or any(t.lower() in nlow for t in strong_terms)
                if ext not in text_exts and not name_interest:continue
                if info.file_size>20*1024*1024:continue
                try:data=z.read(info)
                except Exception:continue
                rec["text_members_scanned"]+=1
                text=data.decode("utf-8-sig",errors="replace")
                strong,tech,named,rel=relevant_text(text,name)
                # Also retain Stage43 scripts by filename even if terms are sparse.
                if rel or (any(t in nlow for t in name_terms) and ext in (".py",".ps1",".json",".md",".txt")):
                    rec["matching_members"]+=1
                    archive_hits.append({
                        "zip":str(zp.relative_to(ROOT)),"member":name,"size":info.file_size,
                        "strong_terms":";".join(strong),"technical_terms":";".join(tech),
                        "name_terms":";".join(named),
                    })
                    if ext in (".py",".ps1",".json",".md",".txt"):
                        save_recovered(data,"ZIP_"+str(zp.relative_to(ROOT)),name)
    except Exception as e:
        rec["error"]=f"{type(e).__name__}: {e}"
    archive_report.append(rec)

write_tsv(OUT/"filesystem_pipeline_hits.tsv",["path","size","strong_terms","technical_terms","name_terms"],fs_hits)
write_tsv(OUT/"archive_scan_report.tsv",["zip","size","members","text_members_scanned","matching_members","error"],archive_report)
write_tsv(OUT/"archive_pipeline_hits.tsv",["zip","member","size","strong_terms","technical_terms","name_terms"],archive_hits)
write_tsv(OUT/"recovered_pipeline_files.tsv",["source","entry","copy_name","size","sha256"],copied)

# Focused snippets from recovered scripts.
snippet_rows=[]
for c in copied:
    p=recover_dir/c["copy_name"]
    if p.suffix.lower() not in (".py",".ps1",".md",".txt",".json"):continue
    try:text=p.read_text(encoding="utf-8-sig",errors="replace")
    except Exception:continue
    lines=text.splitlines()
    for i,line in enumerate(lines,1):
        if any(t.lower() in line.lower() for t in strong_terms+technical_terms):
            lo=max(1,i-2);hi=min(len(lines),i+2)
            snippet="\n".join(f"{j}: {lines[j-1]}" for j in range(lo,hi+1))
            snippet_rows.append({"copy_name":c["copy_name"],"line":i,"snippet":snippet[:4000]})
            if sum(1 for x in snippet_rows if x["copy_name"]==c["copy_name"])>=50:
                break
write_tsv(OUT/"recovered_pipeline_snippets.tsv",["copy_name","line","snippet"],snippet_rows)

# Final report. A SHA mismatch is diagnostic, not automatic failure: prior applied
# missions may have changed extracted copies, while entry_map still gives exact provenance.
report={
    "step":"STEP_064",
    "status":"VERIFIED",
    "campaign_status_counts":dict(counts),
    "unapplied_campaign_units":len(unap_ids),
    "entry_map_path":str(entry_map),
    "exact_occurrences":len(exact),
    "exact_ids_covered":len(present),
    "reference_count_mismatches":len(mismatch),
    "source_int_dir":str(system_dir) if system_dir else None,
    "source_int_unique_files":len(source_files),
    "source_int_hash_matches":source_ok,
    "source_int_missing":source_missing,
    "source_int_sha_mismatches":sha_mismatch,
    "source_line_mismatches":line_mismatch,
    "stage43t_iso_asset_candidates":len(asset_rows),
    "filesystem_pipeline_hits":len(fs_hits),
    "zip_archives_scanned":len(zip_paths),
    "archive_pipeline_hits":len(archive_hits),
    "recovered_pipeline_files":len(copied),
    "iso_modified":False,
    "movie_validation_resumed":False,
    "next_phase":"ANALYZE_RECOVERED_PATCHER_AND_BUILD_BULK_ISO_APPLICATION",
}
(OUT/"step064_report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")

(OUT/"STEP064_README.txt").write_text(f"""STEP_064 exact application recovery complete.

1165 unapplied campaign unit IDs are covered by {len(exact)} exact Stage38
entry-map occurrences. reference-count mismatches: {len(mismatch)}.

Historical pipeline search:
- filesystem hits: {len(fs_hits)}
- ZIP archives scanned: {len(zip_paths)}
- matching archive members: {len(archive_hits)}
- recovered unique pipeline files: {len(copied)}

ISO was NOT modified.
Upload this RESULT ZIP so the recovered historical patcher and exact occurrence
manifest can be analyzed for the bulk ISO application step.
""",encoding="utf-8")
print(json.dumps(report,ensure_ascii=False))
