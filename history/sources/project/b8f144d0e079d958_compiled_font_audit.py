#!/usr/bin/env python3
from pathlib import Path
import csv,json,re,struct,collections,hashlib,importlib.util,sys,traceback

ROOT=Path(r"PROJECT_ROOT")
OUT=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/"log"/"STEP_065"/"outputs"
OUT.mkdir(parents=True,exist_ok=True)
ISO=ROOT/"BIA_STAGE43T_TITLE_PROMPT_FIX.iso"
MASTER=ROOT/"translation"/"text_master.tsv"
ENTRY=ROOT/"analysis"/"stage38_translation_worklist"/"stage38_entry_map.tsv"
INV=ROOT/"log"/"STEP_064"/"outputs"/"stage43t_iso_inventory.tsv"
PLAN=ROOT/"bia_stage39a_tools"/"stage39a_font_plan.json"
HELPER=ROOT/"bia_stage40i_tools"/"bia_stage40i_actual_resource_trace.py"
BASE=0x08E03020
STRIDE=0x78000

def read_tsv(p):
    with p.open("r",encoding="utf-8-sig",newline="") as f:
        rd=csv.DictReader(f,delimiter="\t");return rd.fieldnames,list(rd)

def write_tsv(p,fields,rows):
    with p.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields,delimiter="\t",lineterminator="\n",extrasaction="ignore")
        w.writeheader();w.writerows(rows)

mf,mrows=read_tsv(MASTER)
campaign=[r for r in mrows if r.get("category")=="campaign"]
counts=collections.Counter(r.get("status","") for r in campaign)
expected={"VERIFIED_APPLIED":137,"TRANSLATED_PENDING_APPLY":90,"TRANSLATED_REVIEWED":1075}
for k,v in expected.items():
    if counts[k]!=v: raise RuntimeError(f"Campaign state mismatch {k}: {counts[k]} != {v}")
if counts.get("NEEDS_TRANSLATION",0)!=0: raise RuntimeError("Campaign translation corpus is not complete")
unap=[r for r in campaign if r.get("status") in ("TRANSLATED_PENDING_APPLY","TRANSLATED_REVIEWED")]
if len(unap)!=1165: raise RuntimeError(f"Expected 1165 unapplied IDs, got {len(unap)}")
by_id={r["resource_id"]:r for r in unap}

ef,erows=read_tsv(ENTRY)
id_col="id" if "id" in ef else "resource_id"
keys_by_id=collections.defaultdict(set)
files_by_id=collections.defaultdict(set)
for r in erows:
    rid=r.get(id_col,"")
    if rid in by_id:
        if r.get("key"):keys_by_id[rid].add(r["key"])
        if r.get("file"):files_by_id[rid].add(r["file"])

by_text=collections.defaultdict(list)
for r in unap:
    by_text[r["source_text"]].append(r["resource_id"])
target_texts=set(by_text)

# Existing baseline glyph plan used by proven Stage43A patcher.
plan=json.loads(PLAN.read_text(encoding="utf-8"))
oldchars={x["char"] for x in plan["layout"]}
if len(oldchars)<100:
    raise RuntimeError(f"Unexpected Stage39 font plan size {len(oldchars)}")

# Helper / ISO functions.
sp=importlib.util.spec_from_file_location("biahelper",HELPER)
mod=importlib.util.module_from_spec(sp);sp.loader.exec_module(mod)
_,b=mod.load_helpers()

ivf,inv=read_tsv(INV)
mdi_paths=[r["path"] for r in inv if r["path"].upper().endswith(".MDI")]
iso_pathset={r["path"].upper() for r in inv}
if len(mdi_paths)<50: raise RuntimeError(f"Unexpected MDI inventory count {len(mdi_paths)}")
parts=["PSP_GAME","USRDIR","SYSTEM"]

def ptr_text(st,ptr,n,cap):
    if not(BASE<=ptr<BASE+len(st)*STRIDE and 1<=n<=4096 and n<=cap<=0x100000):
        return None
    i=(ptr-BASE)//STRIDE;o=(ptr-BASE)%STRIDE
    if i not in st:return None
    raw=st[i][o:o+n]
    if len(raw)!=n or raw[-1:]!=b"\0":return None
    for enc in ("utf-8","cp1252"):
        try:return raw[:-1].decode(enc)
        except UnicodeDecodeError:pass
    return None

def int_mdi_compat(intfile,mdiname):
    a=Path(intfile).stem.upper();m=Path(mdiname).stem.upper()
    # Standard story day/time prefix.
    ma=re.match(r"(D0?\d+_\d{4})",a)
    mm=re.match(r"(D0?\d+_\d{4})",m)
    if ma and mm:
        if ma.group(1)==mm.group(1):return 5
        # Known Bloody Gulch runtime asset naming offset.
        if a.startswith("D07_1500_") and m.startswith("D07_1501"):return 5
        # Victory in Carentan interstitial is adjacent to Close Quarters.
        if a.startswith("D8_0930_") and m.startswith("D08_1030"):return 2
        # Bookends can be carried by late/campaign shell assets; no forced match.
        return 0
    if a.startswith("S_SKR_"):
        core=a[2:] # SKR_...
        # truncate map names similarly to PSP asset naming
        toks=core.split("_")
        if len(toks)>=4:
            pref="_".join(toks[:3])+"_"+toks[3][:4]
            if pref in m:return 5
        if core[:11] in m:return 3
        if a in ("S_SKR_HINTS","S_SKR_MENU_MAP") and m=="ON_MEMU_O":return 2
    if a=="D3DRVR" or a=="D3DRV":
        if m=="ON_MEMU_O":return 2
    return 0

refs=[]
ambiguous=[]
mdi_summary=[]
font_candidates=[]
raw_presence=[]
id_candidate_mdis=collections.defaultdict(set)
id_resolved_refs=collections.defaultdict(list)

# Scan only the streams proven/observed to carry localization FStrings, then
# raw-check all streams for IDs still missing later.
scan_streams=(13,26,27,35)

for mdi_path in mdi_paths:
    name=Path(mdi_path).name
    _,blob=b.iso_read_file(ISO,parts+[name])
    parsed=b.parse_mdi(blob)
    st={x["index"]:bytes(x["decoded"]) for x in parsed}
    local_refs=[]
    local_ids=set()

    for si in scan_streams:
        d=st.get(si)
        if not d: continue
        # FVector/FString metadata is 4-byte aligned; look for pointer triples.
        for off in range(12,len(d)-11,4):
            ptr,n,cap=struct.unpack_from("<III",d,off)
            if not(BASE<=ptr<BASE+len(st)*STRIDE and 1<=n<=4096 and n<=cap<=0x100000):
                continue
            value=ptr_text(st,ptr,n,cap)
            if value not in target_texts: continue
            kp,kn,kc=struct.unpack_from("<III",d,off-12)
            key=ptr_text(st,kp,kn,kc)
            cands=[rid for rid in by_text[value] if key in keys_by_id[rid]]
            scored=[]
            for rid in cands:
                score=max([int_mdi_compat(f,name) for f in files_by_id[rid]] or [0])
                scored.append((score,rid))
            best=max([x[0] for x in scored],default=-1)
            chosen=[rid for score,rid in scored if score==best] if scored else []
            differing=len({by_id[r]["ko_review"] or by_id[r]["ko_current"] for r in chosen})>1 if chosen else False
            rec={
                "mdi":name,"stream":si,"offset":hex(off),"key":key or "",
                "english":value,"candidate_ids":";".join(cands),
                "best_score":best,"chosen_ids":";".join(chosen),
                "ambiguous_different_ko":int(differing),
            }
            refs.append(rec);local_refs.append(rec)
            if chosen:
                for rid in chosen:
                    id_candidate_mdis[rid].add(name)
            if len(chosen)==1 and not differing:
                rid=chosen[0];local_ids.add(rid);id_resolved_refs[rid].append(rec)
            elif chosen:
                ambiguous.append(rec)

    # Basic font object inventory from stream 30.
    fcs=[]
    d30=st.get(30,b"")
    for off in range(0,max(0,len(d30)-0x48C),4):
        cnt=struct.unpack_from("<H",d30,off+0x50)[0]
        if cnt not in (151,847,880): continue
        gptr=struct.unpack_from("<I",d30,off+0x54)[0]
        if not(BASE<=gptr<BASE+len(st)*STRIDE): continue
        widths=struct.unpack_from("<I",d30,off+0x474)[0]
        heights=struct.unpack_from("<I",d30,off+0x478)[0]
        tex=struct.unpack_from("<I",d30,off+0x488)[0]
        rec={"mdi":name,"stream":30,"offset":hex(off),"glyph_count":cnt,
             "glyph_ptr":hex(gptr),"widths_ptr":hex(widths),"heights_ptr":hex(heights),"textures_ptr":hex(tex)}
        font_candidates.append(rec);fcs.append(rec)

    # Pair inventory.
    stem=Path(name).stem
    dsl=f"PSP_GAME/USRDIR/SYSTEM/{stem}.DSL".upper()
    dsx=f"PSP_GAME/USRDIR/SYSTEM/{stem}.DSX".upper()
    mdi_summary.append({
        "mdi":name,"decoded_streams":len(st),
        "stream34_len":len(st.get(34,b"")),"stream35_len":len(st.get(35,b"")),
        "compiled_refs_found":len(local_refs),"resolved_ids_found":len(local_ids),
        "font_candidate_count":len(fcs),
        "font_counts":";".join(str(x["glyph_count"]) for x in fcs),
        "has_dsl":int(dsl in iso_pathset),"has_dsx":int(dsx in iso_pathset),
    })

# Coverage and ambiguity by ID.
coverage=[]
missing_ids=[]
for rid in sorted(by_id):
    r=by_id[rid]
    refs_for=id_resolved_refs.get(rid,[])
    mdilist=sorted({x["mdi"] for x in refs_for})
    additions=sorted({c for c in (r.get("ko_review") or r.get("ko_current") or "") if ord(c)>127 and c not in oldchars})
    rec={
        "resource_id":rid,"status":r["status"],"source_text":r["source_text"],
        "resolved_compiled_refs":len(refs_for),
        "resolved_mdis":";".join(mdilist),
        "source_files":";".join(sorted(files_by_id[rid])),
        "additional_chars_vs_stage39":"".join(additions),
        "additional_char_count_vs_stage39":len(additions),
    }
    coverage.append(rec)
    if not refs_for: missing_ids.append(rid)

# Per-MDI glyph demand from uniquely resolved refs.
demand=[]
for ms in mdi_summary:
    name=ms["mdi"]
    ids={rid for rid,rr in id_resolved_refs.items() if any(x["mdi"]==name for x in rr)}
    trtexts=[by_id[r].get("ko_review") or by_id[r].get("ko_current") or "" for r in ids]
    needed_nonascii={c for t in trtexts for c in t if ord(c)>127}
    extra=needed_nonascii-oldchars
    demand.append({
        "mdi":name,"resolved_target_ids":len(ids),
        "unique_nonascii_needed":len(needed_nonascii),
        "additional_chars_vs_stage39":len(extra),
        "additional_chars":"".join(sorted(extra)),
        "stage43a_free_slot_limit":60,
        "fits_stage43a_60_slots":int(len(extra)<=60),
    })

# Raw byte presence for unresolved IDs to distinguish "not compiled" from scan-stream misses.
# Search all streams, but only for unresolved texts and only byte-level exact source payload.
missing_text_to_ids=collections.defaultdict(list)
for rid in missing_ids:
    missing_text_to_ids[by_id[rid]["source_text"]].append(rid)
missing_payloads=[(text,text.encode("utf-8")+b"\0") for text in missing_text_to_ids]
for mdi_path in mdi_paths:
    name=Path(mdi_path).name
    _,blob=b.iso_read_file(ISO,parts+[name])
    st={x["index"]:bytes(x["decoded"]) for x in b.parse_mdi(blob)}
    for text,pay in missing_payloads:
        for si,d in st.items():
            pos=d.find(pay)
            if pos>=0:
                raw_presence.append({
                    "mdi":name,"stream":si,"offset":hex(pos),"english":text,
                    "resource_ids":";".join(missing_text_to_ids[text])
                })

raw_ids=set()
for x in raw_presence:
    raw_ids.update(x["resource_ids"].split(";"))

# Duplicate source/key cases that can lead to context conflicts.
conflict_rows=[]
for text,ids in by_text.items():
    if len(ids)<2: continue
    ko={rid:(by_id[rid].get("ko_review") or by_id[rid].get("ko_current")) for rid in ids}
    if len(set(ko.values()))>1:
        shared_keys=set.intersection(*(keys_by_id[r] for r in ids)) if ids else set()
        conflict_rows.append({
            "source_text":text,"resource_ids":";".join(ids),
            "korean_variants_json":json.dumps(ko,ensure_ascii=False),
            "shared_keys":";".join(sorted(shared_keys)),
        })

write_tsv(OUT/"compiled_fstring_refs.tsv",
          ["mdi","stream","offset","key","english","candidate_ids","best_score","chosen_ids","ambiguous_different_ko"],refs)
write_tsv(OUT/"compiled_id_coverage.tsv",
          ["resource_id","status","source_text","resolved_compiled_refs","resolved_mdis","source_files","additional_chars_vs_stage39","additional_char_count_vs_stage39"],coverage)
write_tsv(OUT/"compiled_ambiguous_refs.tsv",
          ["mdi","stream","offset","key","english","candidate_ids","best_score","chosen_ids","ambiguous_different_ko"],ambiguous)
write_tsv(OUT/"unresolved_raw_presence.tsv",
          ["mdi","stream","offset","english","resource_ids"],raw_presence)
write_tsv(OUT/"mdi_summary.tsv",
          ["mdi","decoded_streams","stream34_len","stream35_len","compiled_refs_found","resolved_ids_found","font_candidate_count","font_counts","has_dsl","has_dsx"],mdi_summary)
write_tsv(OUT/"font_candidates.tsv",
          ["mdi","stream","offset","glyph_count","glyph_ptr","widths_ptr","heights_ptr","textures_ptr"],font_candidates)
write_tsv(OUT/"mdi_glyph_demand.tsv",
          ["mdi","resolved_target_ids","unique_nonascii_needed","additional_chars_vs_stage39","additional_chars","stage43a_free_slot_limit","fits_stage43a_60_slots"],demand)
write_tsv(OUT/"duplicate_source_translation_conflicts.tsv",
          ["source_text","resource_ids","korean_variants_json","shared_keys"],conflict_rows)

resolved_ids={r["resource_id"] for r in coverage if int(r["resolved_compiled_refs"])>0}
unresolved=set(by_id)-resolved_ids
unresolved_raw=unresolved & raw_ids
unresolved_not_raw=unresolved-raw_ids

# Save focused JSON sets for next-stage generator.
(OUT/"resolved_compiled_ids.json").write_text(json.dumps(sorted(resolved_ids),ensure_ascii=False,indent=2),encoding="utf-8")
(OUT/"unresolved_compiled_ids.json").write_text(json.dumps(sorted(unresolved),ensure_ascii=False,indent=2),encoding="utf-8")

report={
    "step":"STEP_065",
    "status":"VERIFIED",
    "target_unapplied_ids":len(by_id),
    "mdi_files_scanned":len(mdi_paths),
    "compiled_fstring_refs_found":len(refs),
    "uniquely_resolved_ids":len(resolved_ids),
    "unresolved_ids":len(unresolved),
    "unresolved_with_raw_payload_in_some_mdi":len(unresolved_raw),
    "unresolved_without_raw_payload_in_any_mdi":len(unresolved_not_raw),
    "ambiguous_ref_records":len(ambiguous),
    "ambiguous_refs_with_different_korean":sum(int(x["ambiguous_different_ko"]) for x in ambiguous),
    "duplicate_source_different_translation_groups":len(conflict_rows),
    "mdi_with_resolved_targets":sum(1 for d in demand if int(d["resolved_target_ids"])>0),
    "mdi_over_stage43a_60_extra_char_slots":sum(1 for d in demand if int(d["resolved_target_ids"])>0 and not int(d["fits_stage43a_60_slots"])),
    "font_candidates_found":len(font_candidates),
    "mdi_without_dsl_or_dsx_among_targets":sum(
        1 for m in mdi_summary
        if int(m["resolved_ids_found"])>0 and (not int(m["has_dsl"]) or not int(m["has_dsx"]))
    ),
    "iso_modified":False,
    "movie_validation_resumed":False,
    "next_phase":"BULK_PATCHER_IF_COVERAGE_SAFE_ELSE_TARGETED_RECOVERY",
}
(OUT/"step065_report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(report,ensure_ascii=False))
