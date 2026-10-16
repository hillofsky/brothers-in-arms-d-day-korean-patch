#!/usr/bin/env python3
from pathlib import Path
import csv, json, re, os, hashlib, ast, shutil, sys, traceback, collections

ROOT=Path(r"PROJECT_ROOT")
OUT=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/"log"/"STEP_063"/"outputs"
OUT.mkdir(parents=True, exist_ok=True)

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
    with p.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields,delimiter="\t",lineterminator="\n",extrasaction="ignore")
        w.writeheader(); w.writerows(rows)

master=ROOT/"translation"/"text_master.tsv"
if not master.exists():
    raise RuntimeError(f"Missing {master}")
fields, rows=read_tsv(master)
camp=[r for r in rows if r.get("category")=="campaign"]
counts=collections.Counter(r.get("status","") for r in camp)
expected={"VERIFIED_APPLIED":137,"TRANSLATED_PENDING_APPLY":90,"TRANSLATED_REVIEWED":1075}
for k,v in expected.items():
    if counts[k]!=v:
        raise RuntimeError(f"Campaign state mismatch {k}: {counts[k]} != {v}")
if counts.get("NEEDS_TRANSLATION",0)!=0:
    raise RuntimeError(f"Campaign NEEDS_TRANSLATION is not zero: {counts.get('NEEDS_TRANSLATION',0)}")

unap=[r for r in camp if r.get("status") in ("TRANSLATED_PENDING_APPLY","TRANSLATED_REVIEWED")]
if len(unap)!=1165:
    raise RuntimeError(f"Expected 1165 unapplied units, got {len(unap)}")
write_tsv(OUT/"campaign_unapplied_ready_for_iso.tsv", fields, unap)

# Parse summarized references currently available in text_master.
ref_pat=re.compile(r'^([^:]+):([^:]+):([^@]+)@(.+)$')
ref_rows=[]
group_units=collections.defaultdict(set)
for r in unap:
    for token in [x.strip() for x in r.get("references","").split("|") if x.strip()]:
        if re.fullmatch(r'\+\d+\s+more',token,re.I):
            ref_rows.append({
                "resource_id":r["resource_id"],"reference_group":"","object":"","field":"",
                "offset":"","raw_reference":token,"kind":"TRUNCATION_MARKER"
            })
            continue
        m=ref_pat.match(token)
        if not m:
            ref_rows.append({
                "resource_id":r["resource_id"],"reference_group":"","object":"","field":"",
                "offset":"","raw_reference":token,"kind":"UNPARSED"
            })
            continue
        grp,obj,field,off=m.groups()
        group_units[grp].add(r["resource_id"])
        ref_rows.append({
            "resource_id":r["resource_id"],"reference_group":grp,"object":obj,"field":field,
            "offset":off,"raw_reference":token,"kind":"PARSED"
        })
write_tsv(OUT/"master_reference_expansion.tsv",
          ["resource_id","reference_group","object","field","offset","raw_reference","kind"],ref_rows)

# Group summary.
summary=[]
for grp,ids in sorted(group_units.items(), key=lambda kv:(kv[0])):
    summary.append({"reference_group":grp,"unapplied_unique_units":len(ids)})
write_tsv(OUT/"reference_group_summary.tsv",["reference_group","unapplied_unique_units"],summary)

# Canonical Stage38 source inspection.
canonical_dir=ROOT/"analysis"/"stage38_translation_worklist"
canonical_files=[]
canonical_matches=[]
if canonical_dir.exists():
    for p in sorted(canonical_dir.rglob("*")):
        if not p.is_file(): continue
        rel=str(p.relative_to(ROOT))
        canonical_files.append({"path":rel,"size":p.stat().st_size,"suffix":p.suffix.lower()})
        if p.suffix.lower() in (".tsv",".csv") and p.stat().st_size < 50*1024*1024:
            try:
                delim="\t" if p.suffix.lower()==".tsv" else ","
                with p.open("r",encoding="utf-8-sig",errors="replace",newline="") as f:
                    rd=csv.DictReader(f,delimiter=delim)
                    if not rd.fieldnames: continue
                    rid_col=next((c for c in rd.fieldnames if c.lower() in ("resource_id","id")),None)
                    if not rid_col: continue
                    wanted={r["resource_id"] for r in unap}
                    for row in rd:
                        if row.get(rid_col) in wanted:
                            canonical_matches.append({
                                "source_file":rel,
                                "resource_id":row.get(rid_col,""),
                                "references":row.get("references",""),
                                "source_text":row.get("source_text",row.get("text","")),
                                "all_columns_json":json.dumps(row,ensure_ascii=False),
                            })
            except Exception:
                pass
write_tsv(OUT/"stage38_file_inventory.tsv",["path","size","suffix"],canonical_files)
write_tsv(OUT/"stage38_matching_rows.tsv",
          ["source_file","resource_id","references","source_text","all_columns_json"],canonical_matches)

# Determine whether canonical rows expose more/full references than text_master.
master_by_id={r["resource_id"]:r for r in unap}
canonical_ref_stats=[]
for cm in canonical_matches:
    rid=cm["resource_id"]
    mrefs=master_by_id.get(rid,{}).get("references","")
    crefs=cm.get("references","")
    if crefs:
        canonical_ref_stats.append({
            "resource_id":rid,
            "master_ref_chars":len(mrefs),
            "canonical_ref_chars":len(crefs),
            "canonical_longer":int(len(crefs)>len(mrefs)),
            "master_has_plus_more":int(bool(re.search(r'\+\d+\s+more',mrefs,re.I))),
            "canonical_has_plus_more":int(bool(re.search(r'\+\d+\s+more',crefs,re.I))),
        })
write_tsv(OUT/"canonical_reference_comparison.tsv",
          ["resource_id","master_ref_chars","canonical_ref_chars","canonical_longer","master_has_plus_more","canonical_has_plus_more"],
          canonical_ref_stats)

# Existing known campaign mapping files.
known_paths=[
    ROOT/"work"/"campaign_first_ko.json",
    ROOT/"work"/"campaign_second_ko.json",
    ROOT/"bia_stage40i_tools"/"bia_stage40i_actual_resource_trace.py",
]
known_report=[]
copies=OUT/"known_pipeline_files"
copies.mkdir(exist_ok=True)
for p in known_paths:
    rec={"path":str(p),"exists":p.exists(),"size":p.stat().st_size if p.exists() else 0,"sha256":""}
    if p.exists():
        rec["sha256"]=sha256_file(p)
        if p.stat().st_size <= 5*1024*1024:
            dst=copies/(p.name)
            shutil.copy2(p,dst)
    known_report.append(rec)
write_tsv(OUT/"known_pipeline_file_report.tsv",["path","exists","size","sha256"],known_report)

# AST inventory for Python helper if present.
helper=ROOT/"bia_stage40i_tools"/"bia_stage40i_actual_resource_trace.py"
ast_rows=[]
if helper.exists():
    try:
        tree=ast.parse(helper.read_text(encoding="utf-8",errors="replace"))
        for node in tree.body:
            if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):
                args=[a.arg for a in node.args.args]
                ast_rows.append({"kind":"function","name":node.name,"args":",".join(args),"lineno":node.lineno})
            elif isinstance(node,ast.ClassDef):
                ast_rows.append({"kind":"class","name":node.name,"args":"","lineno":node.lineno})
    except Exception as e:
        ast_rows.append({"kind":"ERROR","name":type(e).__name__,"args":str(e),"lineno":0})
write_tsv(OUT/"stage40i_helper_ast.tsv",["kind","name","args","lineno"],ast_rows)

# Search relevant existing scripts/reports by filename and small-content tokens.
search_roots=[ROOT/"work",ROOT/"analysis",ROOT/"bia_stage40i_tools"]
tokens=[
    "campaign_first_ko","campaign_second_ko","D0_0130","D0_0700",
    "LocalizedStrings","ON_MEMU.MDI","rebuild","apply","MDI","DSL","DSX",
]
candidate_rows=[]
candidate_hits=[]
allowed={".py",".ps1",".json",".md",".txt",".tsv",".csv"}
for sroot in search_roots:
    if not sroot.exists(): continue
    for p in sroot.rglob("*"):
        try:
            if not p.is_file() or p.suffix.lower() not in allowed: continue
            size=p.stat().st_size
            if size>8*1024*1024: continue
            name_low=p.name.lower()
            score=sum(2 for t in tokens if t.lower() in name_low)
            text=None
            if score or p.suffix.lower() in (".py",".ps1",".md",".json"):
                try:
                    text=p.read_text(encoding="utf-8",errors="replace")
                    score += sum(1 for t in tokens if t.lower() in text.lower())
                except Exception:
                    text=None
            if score:
                rel=str(p.relative_to(ROOT))
                candidate_rows.append({"path":rel,"size":size,"score":score,"suffix":p.suffix.lower()})
                if text is not None:
                    lines=text.splitlines()
                    for i,line in enumerate(lines,1):
                        if any(t.lower() in line.lower() for t in tokens):
                            candidate_hits.append({"path":rel,"line":i,"text":line[:1000]})
                            if sum(1 for x in candidate_hits if x["path"]==rel)>=30:
                                break
        except Exception:
            pass
candidate_rows.sort(key=lambda r:(-r["score"],r["path"]))
write_tsv(OUT/"pipeline_candidate_files.tsv",["path","size","score","suffix"],candidate_rows[:250])
write_tsv(OUT/"pipeline_content_hits.tsv",["path","line","text"],candidate_hits[:3000])

# Copy top-ranked candidate scripts/reports, bounded.
candcopy=OUT/"candidate_files"
candcopy.mkdir(exist_ok=True)
copied=[]
total=0
for rec in candidate_rows[:80]:
    p=ROOT/rec["path"]
    if not p.exists() or p.stat().st_size>2*1024*1024: continue
    if total+p.stat().st_size>20*1024*1024: break
    safe=rec["path"].replace("\\","__").replace("/","__").replace(":","_")
    dst=candcopy/safe
    try:
        shutil.copy2(p,dst)
        copied.append({"source":rec["path"],"copy_name":safe,"size":p.stat().st_size})
        total+=p.stat().st_size
    except Exception:
        pass
write_tsv(OUT/"candidate_files_copied.tsv",["source","copy_name","size"],copied)

# Discover resource-like local files corresponding to reference groups.
resource_exts={".mdi",".dsl",".dsx",".dat",".idx",".ccs",".bin"}
found=[]
groups=set(group_units)
search_dirs=[ROOT/"work",ROOT/"analysis",ROOT/"extracted",ROOT/"extract",ROOT/"resources"]
for sroot in search_dirs:
    if not sroot.exists(): continue
    for p in sroot.rglob("*"):
        try:
            if not p.is_file(): continue
            if p.suffix.lower() not in resource_exts: continue
            stem=p.stem.upper()
            matches=[g for g in groups if stem.startswith(g.upper()) or g.upper() in p.name.upper()]
            if matches:
                for g in matches[:5]:
                    found.append({
                        "reference_group":g,
                        "path":str(p.relative_to(ROOT)),
                        "size":p.stat().st_size,
                        "suffix":p.suffix.lower(),
                    })
        except Exception:
            pass
write_tsv(OUT/"local_resource_candidates.tsv",["reference_group","path","size","suffix"],found)

# ISO baseline facts/hashes.
iso_paths=[
    ROOT/"BIA_STAGE43T_TITLE_PROMPT_FIX.iso",
    ROOT/"Brothers in Arms - D-Day (USA) (v1.01).iso",
]
iso_rows=[]
for p in iso_paths:
    rec={"path":str(p),"exists":p.exists(),"size":p.stat().st_size if p.exists() else 0,"sha256":""}
    if p.exists():
        rec["sha256"]=sha256_file(p)
    iso_rows.append(rec)
write_tsv(OUT/"iso_baseline_hashes.tsv",["path","exists","size","sha256"],iso_rows)

# First/second mapping structural summaries.
mapping_summaries=[]
for p in [ROOT/"work"/"campaign_first_ko.json",ROOT/"work"/"campaign_second_ko.json"]:
    if not p.exists(): continue
    try:
        obj=json.loads(p.read_text(encoding="utf-8-sig"))
        typ=type(obj).__name__
        if isinstance(obj,dict):
            keys=list(obj.keys())
            mapping_summaries.append({
                "path":str(p.relative_to(ROOT)),
                "json_type":typ,
                "top_keys":";".join(keys[:100]),
                "len":len(obj),
                "sample_json":json.dumps(obj,ensure_ascii=False)[:12000],
            })
        elif isinstance(obj,list):
            mapping_summaries.append({
                "path":str(p.relative_to(ROOT)),
                "json_type":typ,
                "top_keys":"",
                "len":len(obj),
                "sample_json":json.dumps(obj[:5],ensure_ascii=False)[:12000],
            })
    except Exception as e:
        mapping_summaries.append({
            "path":str(p.relative_to(ROOT)),"json_type":"ERROR","top_keys":"",
            "len":0,"sample_json":str(e)
        })
write_tsv(OUT/"known_mapping_structure.tsv",["path","json_type","top_keys","len","sample_json"],mapping_summaries)

# Summary report.
parsed=sum(1 for r in ref_rows if r["kind"]=="PARSED")
trunc=sum(1 for r in ref_rows if r["kind"]=="TRUNCATION_MARKER")
report={
    "step":"STEP_063",
    "status":"VERIFIED",
    "campaign_status_counts":dict(counts),
    "unapplied_campaign_units":len(unap),
    "reference_groups_visible_in_master":len(group_units),
    "parsed_reference_tokens":parsed,
    "truncation_markers_in_master":trunc,
    "stage38_matching_rows":len(canonical_matches),
    "pipeline_candidate_files":len(candidate_rows),
    "candidate_files_copied":len(copied),
    "local_resource_candidates":len(found),
    "iso_baselines":iso_rows,
    "iso_modified":False,
    "movie_validation_resumed":False,
    "next_phase":"BUILD_EXACT_CAMPAIGN_APPLY_MANIFEST_AND_PATCHER",
}
(OUT/"step063_report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")

(OUT/"STEP063_README.txt").write_text(
f"""STEP_063 preflight completed.

Campaign translation corpus is complete.
Unapplied units: {len(unap)}
Visible reference groups in text_master: {len(group_units)}
Parsed reference tokens: {parsed}
Truncation markers: {trunc}

This step did NOT modify any ISO.
Its purpose is to recover the exact existing MDI/DSL/DSX build/application
pipeline before mass-applying 1165 translated campaign units.

Upload the RESULT ZIP for STEP_064 patcher construction.
""",encoding="utf-8")
print(json.dumps(report,ensure_ascii=False))
