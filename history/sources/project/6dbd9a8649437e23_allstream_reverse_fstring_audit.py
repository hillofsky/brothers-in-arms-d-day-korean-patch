#!/usr/bin/env python3
from pathlib import Path
import csv,json,re,struct,collections,hashlib,importlib.util,sys

ROOT=Path(r"PROJECT_ROOT")
OUT=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/"log"/"STEP_066"/"outputs"
OUT.mkdir(parents=True,exist_ok=True)

ISO=ROOT/"BIA_STAGE43T_TITLE_PROMPT_FIX.iso"
MASTER=ROOT/"translation"/"text_master.tsv"
ENTRY=ROOT/"analysis"/"stage38_translation_worklist"/"stage38_entry_map.tsv"
INV=ROOT/"log"/"STEP_064"/"outputs"/"stage43t_iso_inventory.tsv"
PLAN=ROOT/"bia_stage39a_tools"/"stage39a_font_plan.json"
HELPER=ROOT/"bia_stage40i_tools"/"bia_stage40i_actual_resource_trace.py"
BASE=0x08E03020
STRIDE=0x78000
PARTS=["PSP_GAME","USRDIR","SYSTEM"]

def read_tsv(p):
    with p.open("r",encoding="utf-8-sig",newline="") as f:
        rd=csv.DictReader(f,delimiter="\t");return rd.fieldnames,list(rd)

def write_tsv(p,fields,rows):
    with p.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields,delimiter="\t",lineterminator="\n",extrasaction="ignore")
        w.writeheader();w.writerows(rows)

class Aho:
    def __init__(self, patterns):
        self.next=[{}];self.fail=[0];self.out=[[]]
        for key,pat in patterns:
            s=0
            for ch in pat:
                ns=self.next[s].get(ch)
                if ns is None:
                    ns=len(self.next);self.next[s][ch]=ns
                    self.next.append({});self.fail.append(0);self.out.append([])
                s=ns
            self.out[s].append((key,len(pat)))
        q=collections.deque()
        for ch,s in self.next[0].items():
            q.append(s);self.fail[s]=0
        while q:
            r=q.popleft()
            for ch,s in self.next[r].items():
                q.append(s);f=self.fail[r]
                while f and ch not in self.next[f]:f=self.fail[f]
                self.fail[s]=self.next[f].get(ch,0)
                self.out[s].extend(self.out[self.fail[s]])
    def scan(self,data):
        s=0
        for i,ch in enumerate(data):
            while s and ch not in self.next[s]:s=self.fail[s]
            s=self.next[s].get(ch,0)
            if self.out[s]:
                for key,n in self.out[s]:
                    yield i-n+1,key

def ptrloc(ptr,st):
    if not(BASE<=ptr<BASE+len(st)*STRIDE):return None
    si=(ptr-BASE)//STRIDE;off=(ptr-BASE)%STRIDE
    if si not in st or off>=len(st[si]):return None
    return int(si),int(off)

def decode_fstring(st,ptr,n,cap):
    loc=ptrloc(ptr,st)
    if loc is None or not(1<=n<=4096 and n<=cap<=0x100000):return None
    si,off=loc
    raw=st[si][off:off+n]
    if len(raw)!=n or raw[-1:]!=b"\0":return None
    for enc in ("utf-8","cp1252"):
        try:return raw[:-1].decode(enc)
        except UnicodeDecodeError:pass
    return None

mf,mrows=read_tsv(MASTER)
campaign=[r for r in mrows if r.get("category")=="campaign"]
counts=collections.Counter(r.get("status","") for r in campaign)
expected={"VERIFIED_APPLIED":137,"TRANSLATED_PENDING_APPLY":90,"TRANSLATED_REVIEWED":1075}
for k,v in expected.items():
    if counts[k]!=v:raise RuntimeError(f"Campaign state mismatch {k}: {counts[k]} != {v}")
if counts.get("NEEDS_TRANSLATION",0)!=0:raise RuntimeError("Campaign translation corpus incomplete")

target=[r for r in campaign if r.get("status") in ("TRANSLATED_PENDING_APPLY","TRANSLATED_REVIEWED")]
if len(target)!=1165:raise RuntimeError(f"Expected 1165 target IDs, got {len(target)}")
by_id={r["resource_id"]:r for r in target}
by_text=collections.defaultdict(list)
for r in target:by_text[r["source_text"]].append(r["resource_id"])

# This is critical: same source may represent multiple resource IDs, but it is
# safe for source-text-wide patching only if every target translation agrees.
text_ko={}
translation_conflicts=[]
for text,ids in by_text.items():
    variants={by_id[r].get("ko_review") or by_id[r].get("ko_current") for r in ids}
    if len(variants)!=1:
        translation_conflicts.append({"source_text":text,"resource_ids":";".join(ids),"variants_json":json.dumps(sorted(variants),ensure_ascii=False)})
    else:
        text_ko[text]=next(iter(variants))
if translation_conflicts:
    write_tsv(OUT/"translation_conflicts.tsv",["source_text","resource_ids","variants_json"],translation_conflicts)
    raise RuntimeError(f"Target source-text translation conflicts exist: {len(translation_conflicts)}")

ef,erows=read_tsv(ENTRY)
id_col="id" if "id" in ef else "resource_id"
global_keys={r.get("key","") for r in erows if r.get("key","")}
keys_by_text=collections.defaultdict(set)
files_by_text=collections.defaultdict(set)
for r in erows:
    rid=r.get(id_col,"")
    if rid in by_id:
        t=by_id[rid]["source_text"]
        if r.get("key"):keys_by_text[t].add(r["key"])
        if r.get("file"):files_by_text[t].add(r["file"])

ivf,inv=read_tsv(INV)
mdi_paths=[r["path"] for r in inv if r["path"].upper().endswith(".MDI")]
iso_paths={r["path"].upper() for r in inv}
if len(mdi_paths)!=57:raise RuntimeError(f"Expected 57 MDI files, got {len(mdi_paths)}")

sp=importlib.util.spec_from_file_location("biahelper",HELPER)
mod=importlib.util.module_from_spec(sp);sp.loader.exec_module(mod)
_,b=mod.load_helpers()

# Target payload automaton: one scan per decoded stream, not 1165 .find loops.
payload_patterns=[]
for text in text_ko:
    try:pay=text.encode("utf-8")+b"\0"
    except Exception:continue
    payload_patterns.append((text,pay))
payload_aho=Aho(payload_patterns)

refs=[]
raw_rows=[]
font_rows=[]
mdi_rows=[]
source_valid_refs=collections.defaultdict(list)
source_all_refs=collections.defaultdict(list)
mdi_source_refs=collections.defaultdict(set)

for mdi_path in mdi_paths:
    name=Path(mdi_path).name
    _,blob=b.iso_read_file(ISO,PARTS+[name])
    parsed=b.parse_mdi(blob)
    st={x["index"]:bytes(x["decoded"]) for x in parsed}

    # 1) Find every exact target payload and convert it to its MDI virtual ptr.
    ptr_to_text=collections.defaultdict(set)
    raw_count=0
    for si,d in st.items():
        for off,text in payload_aho.scan(d):
            ptr=BASE+si*STRIDE+off
            ptr_to_text[ptr].add(text)
            raw_rows.append({"mdi":name,"payload_stream":si,"payload_offset":hex(off),"pointer":hex(ptr),"english":text})
            raw_count+=1

    # 2) Find references to those exact payload pointers.
    #    Pointer bytes are 4 bytes; scan the streams once with Aho, then validate
    #    FString length/capacity and the preceding FString.
    ptr_patterns=[(ptr,struct.pack("<I",ptr)) for ptr in ptr_to_text]
    ptr_aho=Aho(ptr_patterns) if ptr_patterns else None
    local_high=0;local_medium=0
    local_sources=set()

    if ptr_aho:
        for si,d in st.items():
            for off,ptr in ptr_aho.scan(d):
                if off%4 or off+12>len(d):continue
                p,n,cap=struct.unpack_from("<III",d,off)
                if p!=ptr or not(1<=n<=4096 and n<=cap<=0x100000):continue
                texts=ptr_to_text.get(ptr,set())
                if not texts:continue
                value=decode_fstring(st,p,n,cap)
                if value not in texts:continue

                key=""
                key_valid_global=False
                key_matches_target=False
                if off>=12:
                    kp,kn,kc=struct.unpack_from("<III",d,off-12)
                    key=decode_fstring(st,kp,kn,kc) or ""
                    key_valid_global=key in global_keys
                    key_matches_target=key in keys_by_text[value]

                conf="HIGH" if key_valid_global else "MEDIUM"
                rec={
                    "mdi":name,"metadata_stream":si,"metadata_offset":hex(off),
                    "payload_pointer":hex(ptr),"payload_stream":ptrloc(ptr,st)[0],
                    "payload_offset":hex(ptrloc(ptr,st)[1]),
                    "english":value,"korean":text_ko[value],
                    "preceding_fstring":key,
                    "preceding_is_any_int_key":int(key_valid_global),
                    "preceding_matches_target_int_key":int(key_matches_target),
                    "confidence":conf,
                    "resource_ids":";".join(by_text[value]),
                    "source_files":";".join(sorted(files_by_text[value])),
                }
                refs.append(rec);source_all_refs[value].append(rec)
                if key_valid_global:
                    local_high+=1;source_valid_refs[value].append(rec)
                else:
                    local_medium+=1
                local_sources.add(value);mdi_source_refs[name].add(value)

    # 3) Strong font object scan in every stream.
    local_fonts=0
    for si,d in st.items():
        for count in (847,880):
            needle=struct.pack("<H",count)
            pos=0
            while True:
                pos=d.find(needle,pos)
                if pos<0:break
                obj=pos-0x50;pos+=1
                if obj<0 or obj%4 or obj+0x48C>len(d):continue
                try:
                    gptr=struct.unpack_from("<I",d,obj+0x54)[0]
                    gloc=ptrloc(gptr,st)
                    if gloc is None:continue
                    # Hangul page pointers AC..D7: demand a substantial number of valid ptrs.
                    page_ptrs=[]
                    valid_pages=0
                    for hb in range(0xAC,0xD8):
                        pp=struct.unpack_from("<I",d,obj+0x58+hb*4)[0]
                        page_ptrs.append(pp)
                        if ptrloc(pp,st) is not None:valid_pages+=1
                    if valid_pages<40:continue
                    widths=struct.unpack_from("<I",d,obj+0x474)[0]
                    heights=struct.unpack_from("<I",d,obj+0x478)[0]
                    textures=struct.unpack_from("<I",d,obj+0x488)[0]
                    if ptrloc(widths,st) is None or ptrloc(heights,st) is None or ptrloc(textures,st) is None:
                        continue
                    font_rows.append({
                        "mdi":name,"object_stream":si,"object_offset":hex(obj),
                        "glyph_count":count,"glyph_ptr":hex(gptr),
                        "glyph_stream":gloc[0],"glyph_offset":hex(gloc[1]),
                        "valid_hangul_page_ptrs":valid_pages,
                        "page_ac_ptr":hex(page_ptrs[0]),"page_d7_ptr":hex(page_ptrs[-1]),
                        "widths_ptr":hex(widths),"heights_ptr":hex(heights),"textures_ptr":hex(textures),
                    })
                    local_fonts+=1
                except Exception:
                    continue

    stem=Path(name).stem
    mdi_rows.append({
        "mdi":name,"decoded_streams":len(st),"raw_target_payloads":raw_count,
        "high_confidence_refs":local_high,"medium_confidence_refs":local_medium,
        "unique_target_sources_referenced":len(local_sources),
        "font_objects":local_fonts,
        "has_dsl":int(f"PSP_GAME/USRDIR/SYSTEM/{stem}.DSL".upper() in iso_paths),
        "has_dsx":int(f"PSP_GAME/USRDIR/SYSTEM/{stem}.DSX".upper() in iso_paths),
    })

# Coverage. HIGH is proven historical criterion; MEDIUM is structurally valid
# FString but preceding value is not an INT key (titles/icon labels often do this).
coverage=[]
high_ids=set();all_ids=set()
for text,ids in by_text.items():
    hi=source_valid_refs.get(text,[])
    al=source_all_refs.get(text,[])
    for rid in ids:
        if hi:high_ids.add(rid)
        if al:all_ids.add(rid)
        coverage.append({
            "resource_id":rid,"status":by_id[rid]["status"],"source_text":text,
            "high_confidence_refs":len(hi),"all_structural_refs":len(al),
            "high_mdis":";".join(sorted({x["mdi"] for x in hi})),
            "all_mdis":";".join(sorted({x["mdi"] for x in al})),
            "source_files":";".join(sorted(files_by_text[text])),
        })

# Canary: D0_0700 mapping is the already-known verified structural mapping.
second_ids={
    r["resource_id"] for r in target
    if r["status"]=="TRANSLATED_PENDING_APPLY" and
       any(f.startswith("D0_0700_EXIT4") for f in files_by_text[r["source_text"]])
}
# More exact fallback from master refs.
second_ids |= {r["resource_id"] for r in target if "D0_0700_EXIT4:" in r.get("references","")}
second_hi=[
    x for x in refs
    if x["mdi"]=="D0_0700_.MDI"
    and x["confidence"]=="HIGH"
    and any(rid in second_ids for rid in x["resource_ids"].split(";"))
]
second_covered=set()
for x in second_hi:
    second_covered.update(set(x["resource_ids"].split(";")) & second_ids)
canary={
    "expected_units":90,"actual_units":len(second_covered),
    "expected_refs":179,"actual_refs":len(second_hi),
    "pass":len(second_covered)==90 and len(second_hi)==179,
}

# Per-MDI character demand from every structural ref. Same source => same KO
# has already been asserted above.
plan=json.loads(PLAN.read_text(encoding="utf-8"))
basechars={x["char"] for x in plan["layout"]}
demand=[]
for mr in mdi_rows:
    name=mr["mdi"]
    texts=mdi_source_refs.get(name,set())
    needed={c for t in texts for c in text_ko[t] if ord(c)>127}
    extra=needed-basechars
    demand.append({
        "mdi":name,
        "target_source_count":len(texts),
        "unique_nonascii_needed":len(needed),
        "additional_chars_vs_stage39":len(extra),
        "additional_chars":"".join(sorted(extra)),
        "fits_stage43a_60_slots":int(len(extra)<=60),
        "font_objects_found":mr["font_objects"],
    })

write_tsv(OUT/"allstream_fstring_refs.tsv",
          ["mdi","metadata_stream","metadata_offset","payload_pointer","payload_stream","payload_offset","english","korean","preceding_fstring","preceding_is_any_int_key","preceding_matches_target_int_key","confidence","resource_ids","source_files"],refs)
write_tsv(OUT/"allstream_raw_payloads.tsv",
          ["mdi","payload_stream","payload_offset","pointer","english"],raw_rows)
write_tsv(OUT/"allstream_id_coverage.tsv",
          ["resource_id","status","source_text","high_confidence_refs","all_structural_refs","high_mdis","all_mdis","source_files"],coverage)
write_tsv(OUT/"allstream_mdi_summary.tsv",
          ["mdi","decoded_streams","raw_target_payloads","high_confidence_refs","medium_confidence_refs","unique_target_sources_referenced","font_objects","has_dsl","has_dsx"],mdi_rows)
write_tsv(OUT/"allstream_font_objects.tsv",
          ["mdi","object_stream","object_offset","glyph_count","glyph_ptr","glyph_stream","glyph_offset","valid_hangul_page_ptrs","page_ac_ptr","page_d7_ptr","widths_ptr","heights_ptr","textures_ptr"],font_rows)
write_tsv(OUT/"allstream_mdi_glyph_demand.tsv",
          ["mdi","target_source_count","unique_nonascii_needed","additional_chars_vs_stage39","additional_chars","fits_stage43a_60_slots","font_objects_found"],demand)

unresolved_high=sorted(set(by_id)-high_ids)
unresolved_all=sorted(set(by_id)-all_ids)
(OUT/"unresolved_high_confidence_ids.json").write_text(json.dumps(unresolved_high,ensure_ascii=False,indent=2),encoding="utf-8")
(OUT/"unresolved_all_structural_ids.json").write_text(json.dumps(unresolved_all,ensure_ascii=False,indent=2),encoding="utf-8")
(OUT/"d0_0700_canary.json").write_text(json.dumps(canary,ensure_ascii=False,indent=2),encoding="utf-8")

target_mdis=[m for m in mdi_rows if int(m["unique_target_sources_referenced"])>0]
report={
    "step":"STEP_066",
    "status":"VERIFIED",
    "target_ids":len(by_id),
    "target_unique_source_texts":len(by_text),
    "mdi_files_scanned":len(mdi_paths),
    "raw_payload_occurrences":len(raw_rows),
    "structural_fstring_refs":len(refs),
    "high_confidence_fstring_refs":sum(1 for x in refs if x["confidence"]=="HIGH"),
    "medium_confidence_fstring_refs":sum(1 for x in refs if x["confidence"]=="MEDIUM"),
    "ids_with_high_confidence_ref":len(high_ids),
    "ids_with_any_structural_ref":len(all_ids),
    "unresolved_high_confidence_ids":len(unresolved_high),
    "unresolved_all_structural_ids":len(unresolved_all),
    "d0_0700_canary":canary,
    "target_mdis":len(target_mdis),
    "target_mdis_without_dsl_or_dsx":sum(1 for m in target_mdis if not int(m["has_dsl"]) or not int(m["has_dsx"])),
    "font_objects_found":len(font_rows),
    "target_mdis_without_font_object":sum(1 for m in target_mdis if int(m["font_objects"])==0),
    "target_mdis_over_60_extra_chars":sum(1 for d in demand if int(d["target_source_count"])>0 and not int(d["fits_stage43a_60_slots"])),
    "source_text_translation_conflicts":0,
    "iso_modified":False,
    "movie_validation_resumed":False,
    "next_phase":"BUILD_PATCH_MANIFEST_IF_CANARY_AND_COVERAGE_PASS",
}
(OUT/"step066_report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(report,ensure_ascii=False))
