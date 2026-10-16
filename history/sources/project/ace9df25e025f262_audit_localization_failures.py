#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""STEP082: read-only exact ISO evidence and font/English-source audit."""
import argparse, zipfile, json, csv, hashlib, struct, re, importlib.util
from pathlib import Path
from collections import defaultdict

ROOT=Path(r"PROJECT_ROOT")
SOURCE=ROOT/"BIA_STAGE69_FIX2_NONMDI_INT92_TEST.iso"
BUILD=ROOT/"BIA_STAGE79_COMPILED967_STRUCTURAL_TEST.iso"
ORIGINAL=ROOT/"Brothers in Arms - D-Day (USA) (v1.01).iso"
PARTS=["PSP_GAME","USRDIR","SYSTEM"]
EXPECT={
    "stage69":"5683ad64d2ca2764fc05bb5a690402ae17c47398298878ca1bfc5e04ecb514b8",
    "stage79":"ca320d514c32d34767e7255ea3079f7449783cdb2b98ec49797a87bdd69544d9",
}
KEYWORDS={
    "MISSION1_PICKUP":"You got the German K98 Rifle.",
    "MISSION1_MOVE":"Keep moving Leggett!",
    "MISSION1_SATCHEL":"plant a satchel charge",
    "MISSION2_TITLE":"Ambush at Exit 4",
    "MISSION2_DATE":"June 6, 1944",
}
BIA_MDIS=["D0_0130_.MDI","D0_0700_.MDI"]
ASCII_REGEX=re.compile(rb"[\x20-\x7e]{4,350}\x00")

def hashfile(p):
    h=hashlib.sha256()
    with open(p,"rb") as f:
        for b in iter(lambda:f.read(4*1024*1024),b""):
            h.update(b)
    return h.hexdigest()

def sha(b): return hashlib.sha256(b).hexdigest()
def jwrite(p,v):
    p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding="utf-8")
def use_module(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
def iso_extract(b,p,name):
    rec,data=b.iso_read_file(p,PARTS+[name])
    return rec,bytes(data)
def get_st(b,blob):
    return {x["index"]:bytes(x["decoded"]) for x in b.parse_mdi(blob)}
def iso_ints(b,iso):
    rec=b.iso_find_record(iso,PARTS)
    with open(iso,"rb") as f:
        return sorted(x["name"] for x in b.iso_list_dir(f,rec["extent"],rec["size"])
            if x["name"].endswith(".INT"))
def keyword_hits(block,name,where):
    found=[]
    lower=block.lower()
    for id,kw in KEYWORDS.items():
        k=kw.encode("ascii").lower()
        off=0
        while True:
            loc=lower.find(k,off)
            if loc<0: break
            window=block[max(0,loc-32):min(len(block),loc+len(k)+96)]
            found.append({
                "key":id,"english":kw,"file":name,"location":where,
                "offset":hex(loc),"window_ascii":window.decode("latin1",errors="replace"),
            })
            off=loc+1
    return found

def object_info(mod,st,si,offset):
    d=st.get(si)
    if d is None or offset<0 or offset+0x490>len(d):
        return {"error":"missing_font_object"}
    n=struct.unpack_from("<H",d,offset+0x50)[0]
    p=struct.unpack_from("<I",d,offset+0x54)[0]
    result={"font_stream":si,"font_offset":hex(offset),
            "glyph_count":n,"glyph_ptr":hex(p)}
    for k,c in {
        "one_syllable_je":"제",
        "mission2_chars":"프랑스 유타 해변 인근",
        "mission2_chars2":"독일군 박격포반",
        "user_fallback_char":">",
    }.items():
        mapping={}
        for ch in dict.fromkeys(c):
            gi=mod.font_lookup(st,si,offset,ord(ch))
            mapping[ch]=gi
        result[k]=mapping
    for key,ptr_off in [("width_ptr",0x474),("height_ptr",0x478),("textures_ptr",0x488)]:
        ptr=struct.unpack_from("<I",d,offset+ptr_off)[0]
        result[key]=hex(ptr)
        raw=mod.resolve_ptr_bytes(st,ptr,16)
        result[key+"_first_16_hex"]=raw.hex() if raw is not None else "not_mapped"
    return result

def main():
    a=argparse.ArgumentParser()
    a.add_argument("--pkg",required=True)
    a.add_argument("--out",required=True)
    q=a.parse_args()
    pkg=Path(q.pkg);out=Path(q.out);out.mkdir(parents=True,exist_ok=True)
    buildsrc=use_module(pkg/"reference"/"build_compiled967_step079.py","stage79_reference")
    b=buildsrc.load_helper()

    before={"stage69":hashfile(SOURCE),"stage79":hashfile(BUILD)}
    if before != EXPECT:
        raise RuntimeError("SOURCE ISO HASH CHECK FAILED: "+json.dumps(before))
    report={
        "step":"STEP_082",
        "status":"IN_PROGRESS",
        "iso_modified":False,
        "source_iso_sha256_before":before,
        "capture_kind":"exact D0_0700 source+patched MDI/DSL/DSX, first-mission patched MDI for cross-comparison",
        "source_mdi_font_logical_integrity_only":True,
        "runtime_font_visual_verified":False,
    }
    jwrite(out/"step082_report_partial.json",report)

    capture=out/"mission1_2_exact_binary_evidence.zip"
    manifest=[]
    parsed={}
    word_hits=[]
    with zipfile.ZipFile(capture,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=7,allowZip64=True) as zz:
        for build_name,iso,fnames in [
            ("stage69",SOURCE,["D0_0700_.MDI","D0_0700_.DSL","D0_0700_.DSX"]),
            ("stage79",BUILD,["D0_0700_.MDI","D0_0700_.DSL","D0_0700_.DSX",
                              "D0_0130_.MDI"]),
        ]:
            for name in fnames:
                _,d=iso_extract(b,iso,name)
                member=f"{build_name}/{name}"
                zz.writestr(member,d)
                row={"resource":member,"size":len(d),"sha256":sha(d)}
                manifest.append(row)
                print("EXTRACT",member,len(d),flush=True)
                if name.endswith(".MDI"):
                    streams=get_st(b,d)
                    parsed[(build_name,name)]=streams
                    for si,blob in sorted(streams.items()):
                        word_hits.extend(keyword_hits(blob,name,f"{build_name}/stream{si}"))

        for n in ("D0_0700_",):
            for prefix,iso in [("stage69",SOURCE),("stage79",BUILD)]:
                _,dsl=iso_extract(b,iso,n+".DSL")
                _,dsx=iso_extract(b,iso,n+".DSX")
                if b.dsx_logical_bytes(dsx)!=dsl:
                    raise RuntimeError(f"{prefix} DSL/DSX logical mismatch {n}")

        # Copy the exact source evidence needed for offline cross-comparison.
        for rel in ["evidence/allstream_fstring_refs.tsv",
                    "evidence/mdi_build_report.tsv","evidence/user_observations.json"]:
            path=pkg/rel
            zz.write(path,"references/"+Path(rel).name)

    # First mission currently verified; second has corrupted text glyphs.
    font_audit={
        "stage79_first_mission":[],
        "stage69_second_mission":[],
        "stage79_second_mission":[],
    }
    stfirst=parsed[("stage79","D0_0130_.MDI")]
    for si,off in buildsrc.KNOWN_FIRST_FONT_OFFSETS:
        font_audit["stage79_first_mission"].append(object_info(buildsrc,stfirst,si,off))

    _,orig_blob=iso_extract(b,ORIGINAL,"D0_0700_.MDI")
    orig_st=get_st(b,orig_blob)
    _,first_orig_blob=iso_extract(b,ORIGINAL,"D0_0130_.MDI")
    first_orig_st=get_st(b,first_orig_blob)
    templates=[];template_metrics=[];signatures=set()
    for si,off in buildsrc.KNOWN_FIRST_FONT_OFFSETS:
        obj=first_orig_st[si][off:off+0x490]
        templates.append(buildsrc.normalize_font_object(obj,buildsrc.CAMPAIGN_BASE,len(first_orig_st)))
        d=first_orig_st[si]
        wp=struct.unpack_from("<I",d,off+0x474)[0]
        hp=struct.unpack_from("<I",d,off+0x478)[0]
        ww=buildsrc.read_u16_ptr(first_orig_st,wp)
        hh=buildsrc.read_u16_ptr(first_orig_st,hp)
        template_metrics.append((ww,hh))
        signatures.add((ww,hh))

    candidates=buildsrc.scan_font_candidates(orig_st,templates,signatures)
    pair=buildsrc.choose_font_pair(candidates,template_metrics)
    font_audit["second_mission_original_candidate_count"]=len(candidates)
    font_audit["second_mission_pair_confidence"]={
        "best_score":pair.get("pair_score") if pair else None,
        "ambiguous":pair.get("ambiguous") if pair else None,
    }
    if not pair or pair.get("ambiguous"):
        raise RuntimeError("Cannot identify unique production fonts for second mission")
    selected=pair["selected"]
    for target,src in [
        ("stage69_second_mission",parsed[("stage69","D0_0700_.MDI")]),
        ("stage79_second_mission",parsed[("stage79","D0_0700_.MDI")]),
    ]:
        for c in selected:
            font_audit[target].append(object_info(buildsrc,src,c["stream"],c["offset"]))

    # Record what is actually different. Do not assume the 967 patched fields
    # correspond to the on-screen movie intro.
    first_streams=parsed[("stage69","D0_0700_.MDI")]
    second_streams=parsed[("stage79","D0_0700_.MDI")]
    comparison=[]
    for si in sorted(set(first_streams)|set(second_streams)):
        old=first_streams.get(si,b"")
        new=second_streams.get(si,b"")
        comparison.append({
            "stream":si,"old_size":len(old),"new_size":len(new),
            "old_sha256":sha(old),"new_sha256":sha(new),
            "different":old!=new,
        })

    # Scan all INT text resources for the specifically observed English phrases.
    # This complements exact MDI stream scanning without blind ISO byte search.
    int_names=iso_ints(b,BUILD)
    int_scan=[]
    for name in int_names:
        try:
            _,d=iso_extract(b,BUILD,name)
            hits=keyword_hits(d,name,"stage79/INT")
            word_hits.extend(hits)
            int_scan.append({"name":name,"bytes":len(d),"hit_count":len(hits)})
        except Exception as ex:
            int_scan.append({"name":name,"error":repr(ex)})
    jwrite(out/"english_phrase_exact_hits.json",word_hits)
    jwrite(out/"int_files_scanned.json",int_scan)
    jwrite(out/"second_mission_font_audit.json",font_audit)
    jwrite(out/"second_mission_decoded_stream_diff.json",comparison)
    jwrite(out/"sample_manifest.json",manifest)

    # Check compiled targets actually referenced the Korean text that appears
    # as '>' in user's scene, to distinguish storage from rendering.
    subset=parsed[("stage79","D0_0700_.MDI")]
    examples=["프랑스 유타 해변 인근","독일군 박격포반",
              "제4보병사단과 합류"]
    ko_hits=[]
    for ko in examples:
        needle=ko.encode("utf-8")
        locations=[]
        for si,s in subset.items():
            start=0
            while True:
                i=s.find(needle,start)
                if i<0:break
                locations.append({"stream":si,"offset":hex(i)})
                start=i+1
        ko_hits.append({"korean":ko,"utf8_hex":needle.hex(),"locations":locations,
                        "in_mdi":bool(locations)})
    jwrite(out/"second_mission_korean_storage_checks.json",ko_hits)

    after={"stage69":hashfile(SOURCE),"stage79":hashfile(BUILD)}
    if after!=before: raise RuntimeError("READ_ONLY_ISO_SHA_CHANGED")
    with zipfile.ZipFile(capture) as z:
        if z.testzip() is not None:raise RuntimeError("Captured evidence CRC failed")
    report.update({
        "status":"VERIFIED_BINARY_EVIDENCE_EXPORTED",
        "source_iso_sha256_after":after,
        "source_isos_preserved":True,
        "resource_count":len(manifest),
        "int_files_checked":len(int_scan),
        "ascii_keyword_hits_in_decoded_MDI_and_INT":len(word_hits),
        "korean_test_strings_found_in_stage79_mission2":sum(x["in_mdi"] for x in ko_hits),
        "captured_zip":str(capture),
        "captured_zip_bytes":capture.stat().st_size,
        "compiled967_visual_runtime_verified":False,
        "second_mission_rendering": "BROKEN_ANGLE_BRACKET_FALLBACK_USER_SCREENSHOT",
        "next_action":"Inspect exact Stage79 MDI/DSL/DSX binary difference and resolved English-source locations to construct a narrowly scoped runtime-safe fix. Do not promote Stage79 as visually verified.",
    })
    jwrite(out/"step082_report.json",report)
    print(json.dumps({k:report[k] for k in [
        "status","resource_count","int_files_checked","ascii_keyword_hits_in_decoded_MDI_and_INT",
        "korean_test_strings_found_in_stage79_mission2","captured_zip_bytes"]},ensure_ascii=False),flush=True)

if __name__=="__main__":
    main()
