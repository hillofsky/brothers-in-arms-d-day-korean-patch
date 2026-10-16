#!/usr/bin/env python3
from __future__ import annotations
import argparse, csv, hashlib, importlib.util, json, os, re, shutil, struct, sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(r"PROJECT_ROOT")
SOURCE_ISO = ROOT / "BIA_STAGE69_FIX2_NONMDI_INT92_TEST.iso"
OUTPUT_ISO = ROOT / "BIA_STAGE74_COMPILED967_BULK_TEST.iso"
PARTS = ["PSP_GAME","USRDIR","SYSTEM"]
BASE = 0x08E03020
STRIDE = 0x78000

def read_tsv(p):
    with Path(p).open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))

def write_tsv(p, fields, rows):
    with Path(p).open("w", encoding="utf-8-sig", newline="") as f:
        w=csv.DictWriter(f, fieldnames=fields, delimiter="\t", lineterminator="\n", extrasaction="ignore")
        w.writeheader(); w.writerows(rows)

def sha256_file(p):
    h=hashlib.sha256()
    with Path(p).open("rb") as f:
        for b in iter(lambda:f.read(1024*1024), b""):
            h.update(b)
    return h.hexdigest()

def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()

def ptrloc(ptr, st):
    if not (BASE <= ptr < BASE + len(st)*STRIDE):
        return None
    si=(ptr-BASE)//STRIDE
    off=(ptr-BASE)%STRIDE
    if si not in st or off >= len(st[si]):
        return None
    return int(si), int(off)

def read_fstring(st, si, off):
    if si not in st or off < 0 or off+12 > len(st[si]):
        return None
    p,n,cap=struct.unpack_from("<III", st[si], off)
    if not (1 <= n <= 0x100000 and n <= cap <= 0x100000):
        return None
    loc=ptrloc(p, st)
    if loc is None:
        return None
    ps,po=loc
    raw=st[ps][po:po+n]
    if len(raw)!=n or raw[-1:]!=b"\0":
        return None
    for enc in ("utf-8","cp1252"):
        try:
            return {"ptr":p,"n":n,"cap":cap,"text":raw[:-1].decode(enc),"payload_stream":ps,"payload_offset":po}
        except UnicodeDecodeError:
            pass
    return None

def payload_text(st, p, n):
    loc=ptrloc(p,st)
    if loc is None: return None
    si,off=loc
    raw=st[si][off:off+n]
    if len(raw)!=n or raw[-1:]!=b"\0": return None
    for enc in ("utf-8","cp1252"):
        try:return raw[:-1].decode(enc)
        except UnicodeDecodeError:pass
    return None

def align4(n): return (n+3)&~3

def trim_caps(slots):
    # Clamp allocation capacity to the next known payload start in the same stream.
    by_stream=defaultdict(list)
    for s in slots:
        by_stream[s["stream"]].append(s)
    for si,arr in by_stream.items():
        arr.sort(key=lambda x:x["offset"])
        for i,s in enumerate(arr):
            end=s["offset"]+s["cap"]
            if i+1 < len(arr):
                end=min(end, arr[i+1]["offset"])
            end=min(end, s["stream_size"])
            s["effective_cap"]=max(0,end-s["offset"])
    return slots

def scan_all_refs_to_ptr(st, ptr, english):
    needle=struct.pack("<I",ptr)
    out=[]
    for si,d in st.items():
        pos=0
        while True:
            pos=d.find(needle,pos)
            if pos<0: break
            cur=pos; pos+=1
            if cur%4 or cur+12>len(d): continue
            rec=read_fstring(st,si,cur)
            if rec is None or rec["ptr"]!=ptr or rec["text"]!=english:
                continue
            out.append((si,cur,rec["n"],rec["cap"]))
    return sorted(set(out))

def is_key_like_ref(st, si, off, english, global_keys):
    if english not in global_keys:
        return False
    nxt=read_fstring(st,si,off+12)
    return nxt is not None

def find_production_font_candidates(st, font_rows, plan_layout, required_chars):
    out=[]
    by_expected={int(x["codepoint"]):int(x["glyph_index"]) for x in plan_layout}
    for fr in font_rows:
        try:
            osi=int(fr["object_stream"]); oo=int(fr["object_offset"],16)
            if osi not in st or oo+0x48C>len(st[osi]): continue
            obj=st[osi]
            count=struct.unpack_from("<H",obj,oo+0x50)[0]
            gptr=struct.unpack_from("<I",obj,oo+0x54)[0]
            if count < 880: continue
            gloc=ptrloc(gptr,st)
            if gloc is None: continue
            gs,go=gloc

            def lookup(cp):
                pp=struct.unpack_from("<I",obj,oo+0x58+(cp>>8)*4)[0]
                pl=ptrloc(pp,st)
                if pl is None:return None
                ps,po=pl
                eoff=po+(cp&255)*2
                if eoff+2>len(st[ps]): return None
                gi=struct.unpack_from("<H",st[ps],eoff)[0]
                ro=go+gi*24
                if gi>=count or ro+24>len(st[gs]): return None
                rcp=struct.unpack_from("<H",st[gs],ro)[0]
                if rcp!=cp:return None
                return gi

            base_ok=0
            for cp,expected in by_expected.items():
                gi=lookup(cp)
                if gi==expected: base_ok+=1
            if base_ok < 690:
                continue

            missing=[]
            mapped={}
            for ch in sorted(required_chars):
                cp=ord(ch); gi=lookup(cp)
                if gi is None: missing.append(ch)
                else:mapped[ch]=gi

            out.append({
                "object_stream":osi,
                "object_offset":oo,
                "glyph_count":count,
                "glyph_ptr":gptr,
                "base_plan_exact":base_ok,
                "missing_chars":"".join(missing),
                "required_count":len(required_chars),
                "mapped_count":len(mapped),
            })
        except Exception:
            continue
    return out

def build_one_mdi(b, source_iso, mdi_name, refs, font_rows, plan_layout, global_keys, outdir):
    _,blob=b.iso_read_file(source_iso, PARTS+[mdi_name])
    parsed=b.parse_mdi(blob)
    st={x["index"]:bytes(x["decoded"]) for x in parsed}
    mu={i:bytearray(d) for i,d in st.items()}

    # Group exact target evidence by English text.
    by_eng=defaultdict(list)
    for r in refs:
        by_eng[r["english"]].append(r)

    required_chars={c for eng,rr in by_eng.items() for c in rr[0]["korean"] if 0xAC00<=ord(c)<=0xD7A3}
    candidates=find_production_font_candidates(st,font_rows,plan_layout,required_chars)
    full_candidates=[x for x in candidates if not x["missing_chars"]]
    font_summary={
        "mdi":mdi_name,
        "required_hangul_count":len(required_chars),
        "production_candidates":len(candidates),
        "full_coverage_candidates":len(full_candidates),
        "candidate_missing_json":json.dumps(
            [{"stream":x["object_stream"],"offset":hex(x["object_offset"]),"missing":x["missing_chars"],"base_exact":x["base_plan_exact"]}
             for x in candidates], ensure_ascii=False
        ),
    }
    if required_chars and not full_candidates:
        return None, None, font_summary, {
            "mdi":mdi_name,
            "reason":"FONT_COVERAGE_MISSING",
            "required_chars":"".join(sorted(required_chars)),
            "candidate_count":len(candidates),
        }

    # Build slot records from exact target pointers.
    ptr_rows=defaultdict(list)
    for r in refs:
        p=int(r["payload_pointer"],16)
        ptr_rows[p].append(r)

    slots=[]
    all_target_locations=set()
    for p,rr in ptr_rows.items():
        english=rr[0]["english"]
        if any(x["english"]!=english for x in rr):
            raise RuntimeError(f"{mdi_name}: pointer maps multiple English texts")
        target_locs={(int(x["metadata_stream"]),int(x["metadata_offset"],16)) for x in rr}
        all_target_locations |= target_locs

        # Validate every evidence ref against the source ISO.
        caps=[]; ns=[]
        for si,off in sorted(target_locs):
            rec=read_fstring(st,si,off)
            if rec is None:
                raise RuntimeError(f"{mdi_name}: invalid FString at stream {si} + {off:#x}")
            if rec["ptr"]!=p or rec["text"]!=english:
                raise RuntimeError(f"{mdi_name}: evidence drift at stream {si}+{off:#x}: {rec}")
            caps.append(rec["cap"]); ns.append(rec["n"])

        loc=ptrloc(p,st)
        if loc is None: raise RuntimeError(f"{mdi_name}: invalid target pointer {p:#x}")
        ps,po=loc
        all_refs=scan_all_refs_to_ptr(st,p,english)
        key_like=[(si,off) for si,off,n,c in all_refs if is_key_like_ref(st,si,off,english,global_keys)]

        slots.append({
            "ptr":p,"stream":ps,"offset":po,"stream_size":len(st[ps]),
            "english":english,"korean":rr[0]["korean"],
            "original_n":min(ns),"cap":min(caps),
            "target_locs":sorted(target_locs),
            "all_refs":all_refs,
            "key_like_refs":key_like,
        })

    trim_caps(slots)

    # Make a lookup so texts with duplicate payload copies can use the best one.
    slots_by_eng=defaultdict(list)
    for s in slots: slots_by_eng[s["english"]].append(s)

    allocation_rows=[]
    assigned={}
    tail_regions=[]

    # First pass: patch in place when safe. We never overwrite a slot that appears
    # to serve as a localization lookup key.
    for english,ss in slots_by_eng.items():
        korean=ss[0]["korean"]
        payload=korean.encode("utf-8")+b"\0"
        chosen=None
        for s in sorted(ss,key=lambda x:x["effective_cap"],reverse=True):
            if s["key_like_refs"]: continue
            if len(payload) <= s["effective_cap"]:
                chosen=s; break
        if chosen is not None:
            start=chosen["offset"]; cap=chosen["effective_cap"]
            mu[chosen["stream"]][start:start+len(payload)] = payload
            # Zero only the remaining allocated capacity of this target slot.
            if cap>len(payload):
                mu[chosen["stream"]][start+len(payload):start+cap]=b"\0"*(cap-len(payload))
            assigned[english]=(chosen["ptr"],len(payload),"IN_PLACE",chosen)
            # Update every structurally valid non-key ref that points to this exact
            # English payload. This preserves semantic aliases without changing keys.
            for si,off,n,c in chosen["all_refs"]:
                if (si,off) in chosen["key_like_refs"]: continue
                struct.pack_into("<III",mu[si],off,chosen["ptr"],len(payload),len(payload))

    # Tail slack from every known target allocation is safe after its preserved
    # current string terminator. If the slot was patched in-place, slack starts
    # after the new payload; otherwise after the original payload.
    for s in slots:
        used=s["original_n"]
        if s["english"] in assigned and assigned[s["english"]][3] is s:
            used=assigned[s["english"]][1]
        start=align4(s["offset"]+used)
        end=s["offset"]+s["effective_cap"]
        if end-start >= 4:
            tail_regions.append({
                "stream":s["stream"],
                "start":start,
                "end":end,
                "cursor":start,
                "owner_english":s["english"],
            })

    # Remaining translations are placed only into tail slack of existing FString
    # allocations; no arbitrary zero stream or runtime scratch region is used.
    remaining=[]
    for english,ss in slots_by_eng.items():
        if english in assigned: continue
        korean=ss[0]["korean"]
        remaining.append((len(korean.encode("utf-8"))+1,english,korean))
    remaining.sort(reverse=True)

    for need,english,korean in remaining:
        payload=korean.encode("utf-8")+b"\0"
        placed=None
        # best fit minimizes leftover.
        options=[]
        for reg in tail_regions:
            cur=align4(reg["cursor"])
            avail=reg["end"]-cur
            if avail>=len(payload):
                options.append((avail-len(payload),reg,cur))
        if options:
            _,reg,cur=min(options,key=lambda x:x[0])
            mu[reg["stream"]][cur:cur+len(payload)]=payload
            reg["cursor"]=cur+len(payload)
            ptr=BASE+reg["stream"]*STRIDE+cur
            assigned[english]=(ptr,len(payload),"TAIL_SLACK",reg)
            allocation_rows.append({
                "mdi":mdi_name,"english":english,"korean":korean,"method":"TAIL_SLACK",
                "payload_ptr":hex(ptr),"payload_stream":reg["stream"],"payload_offset":hex(cur),
                "payload_bytes":len(payload),"owner_english":reg["owner_english"],
            })
        else:
            return None,None,font_summary,{
                "mdi":mdi_name,
                "reason":"FSTRING_STORAGE_CAPACITY_EXHAUSTED",
                "unplaced_english":english,
                "unplaced_korean":korean,
                "payload_bytes":len(payload),
                "tail_regions":len(tail_regions),
            }

    # Point every exact target metadata ref to its assigned Korean payload.
    patch_rows=[]
    for english,rr in by_eng.items():
        ptr,n,method,srcinfo=assigned[english]
        for r in rr:
            si=int(r["metadata_stream"]);off=int(r["metadata_offset"],16)
            before=bytes(mu[si][off:off+12])
            struct.pack_into("<III",mu[si],off,ptr,n,n)
            patch_rows.append({
                "mdi":mdi_name,
                "metadata_stream":si,
                "metadata_offset":hex(off),
                "resource_ids":r["resource_ids"],
                "english":english,
                "korean":r["korean"],
                "payload_ptr":hex(ptr),
                "payload_bytes":n,
                "allocation_method":method,
                "before_hex":before.hex(),
                "after_hex":bytes(mu[si][off:off+12]).hex(),
            })

    # Ensure all evidence locations now decode to exact Korean.
    for p in patch_rows:
        si=int(p["metadata_stream"]);off=int(p["metadata_offset"],16)
        rec=read_fstring({i:bytes(d) for i,d in mu.items()},si,off)
        if rec is None or rec["text"]!=p["korean"]:
            raise RuntimeError(f"{mdi_name}: post-patch FString verify failed {si}+{off:#x}")

    changed={i:bytes(d) for i,d in mu.items() if bytes(d)!=st[i]}
    patched=b.rebuild_mdi(blob,changed)
    rb={x["index"]:bytes(x["decoded"]) for x in b.parse_mdi(patched)}
    if any(rb[i]!=bytes(mu[i]) for i in mu):
        raise RuntimeError(f"{mdi_name}: rebuilt MDI decoded readback mismatch")

    report={
        "mdi":mdi_name,
        "target_reference_rows":len(refs),
        "unique_english":len(by_eng),
        "patched_reference_rows":len(patch_rows),
        "in_place_translations":sum(1 for x in assigned.values() if x[2]=="IN_PLACE"),
        "tail_slack_translations":sum(1 for x in assigned.values() if x[2]=="TAIL_SLACK"),
        "changed_streams":";".join(map(str,sorted(changed))),
        "original_mdi_size":len(blob),
        "patched_mdi_size":len(patched),
        "original_sha256":sha256_bytes(blob),
        "patched_sha256":sha256_bytes(patched),
        "font_full_coverage_candidates":len(full_candidates),
    }
    return patched,(report,patch_rows,allocation_rows),font_summary,None

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--package-root",required=True)
    ap.add_argument("--outdir",required=True)
    a=ap.parse_args()
    pkg=Path(a.package_root); out=Path(a.outdir); out.mkdir(parents=True,exist_ok=True)

    refs=read_tsv(pkg/"evidence"/"allstream_fstring_refs.tsv")
    split=read_tsv(pkg/"evidence"/"campaign_final_apply_split.tsv")
    font_rows=read_tsv(pkg/"evidence"/"allstream_font_objects.tsv")
    entry=read_tsv(pkg/"evidence"/"stage38_entry_map.tsv")
    plan=json.loads((pkg/"evidence"/"stage39a_font_plan.json").read_text(encoding="utf-8-sig"))

    compiled_ids={r["resource_id"] for r in split if r["final_apply_class"]=="COMPILED_MDI_PATCH"}
    if len(compiled_ids)!=967:
        raise RuntimeError(f"compiled ID count {len(compiled_ids)} != 967")

    # Restrict refs exactly to compiled IDs.
    target_refs=[]
    matched_ids=set()
    for r in refs:
        ids={x for x in r["resource_ids"].split(";") if x}
        if ids & compiled_ids:
            target_refs.append(r)
            matched_ids |= ids & compiled_ids
    if len(target_refs)!=2333 or len(matched_ids)!=967:
        raise RuntimeError(f"evidence mismatch refs={len(target_refs)} ids={len(matched_ids)}")

    target_mdis=sorted({r["mdi"] for r in target_refs})
    if len(target_mdis)!=32:
        raise RuntimeError(f"target MDI count {len(target_mdis)} != 32")

    global_keys={r["key"] for r in entry if r.get("key")}

    # Helper from local verified BIA tree.
    helper=ROOT/"bia_stage40i_tools"/"bia_stage40i_actual_resource_trace.py"
    if not helper.exists():
        raise RuntimeError(f"helper missing: {helper}")
    sp=importlib.util.spec_from_file_location("biahelper",helper)
    mod=importlib.util.module_from_spec(sp);sp.loader.exec_module(mod)
    _,b=mod.load_helpers()

    if not SOURCE_ISO.exists():
        raise RuntimeError(f"source ISO missing: {SOURCE_ISO}")
    if OUTPUT_ISO.exists():
        OUTPUT_ISO.unlink()

    source_sha_before=sha256_file(SOURCE_ISO)

    refs_by=defaultdict(list)
    for r in target_refs: refs_by[r["mdi"]].append(r)
    fonts_by=defaultdict(list)
    for r in font_rows:
        if r["mdi"] in target_mdis: fonts_by[r["mdi"]].append(r)

    # Full dry-run analysis first. No output ISO is created unless every MDI
    # passes storage + font coverage.
    prepared={}
    mdi_reports=[];patch_rows=[];alloc_rows=[];font_reports=[];blocked=[]
    for idx,mdi in enumerate(target_mdis,1):
        print(f"[dry-run {idx:02d}/32] {mdi}",flush=True)
        patched,detail,fontrep,err=build_one_mdi(
            b,SOURCE_ISO,mdi,refs_by[mdi],fonts_by[mdi],plan["layout"],global_keys,out
        )
        font_reports.append(fontrep)
        if err:
            blocked.append(err)
        else:
            rep,pr,ar=detail
            prepared[mdi]=patched
            mdi_reports.append(rep);patch_rows.extend(pr);alloc_rows.extend(ar)

    write_tsv(out/"font_coverage.tsv",
              ["mdi","required_hangul_count","production_candidates","full_coverage_candidates","candidate_missing_json"],
              font_reports)
    if blocked:
        (out/"blocked_mdis.json").write_text(json.dumps(blocked,ensure_ascii=False,indent=2),encoding="utf-8")
        report={
            "step":"STEP_074","status":"BLOCKED_PREBUILD","iso_built":False,
            "compiled_ids":967,"target_refs":2333,"target_mdis":32,
            "blocked_count":len(blocked),"blocked":blocked,
            "source_iso":str(SOURCE_ISO),"source_sha256":source_sha_before,
            "output_iso":str(OUTPUT_ISO),
            "runtime_verified":False,"movie_playback_validation_resumed":False,
        }
        (out/"step074_report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
        raise SystemExit(6)

    # Only after all 32 MDIs pass dry-run do we create the actual ISO.
    shutil.copy2(SOURCE_ISO,OUTPUT_ISO)

    for idx,mdi in enumerate(target_mdis,1):
        print(f"[apply {idx:02d}/32] {mdi}",flush=True)
        b.append_iso_file_and_repoint(OUTPUT_ISO,PARTS+[mdi],prepared[mdi])
        _,rb=b.iso_read_file(OUTPUT_ISO,PARTS+[mdi])
        if rb!=prepared[mdi]:
            raise RuntimeError(f"ISO readback mismatch: {mdi}")

    # Preserve Stage69 INT files exactly.
    int_report=read_tsv(pkg/"evidence"/"int_file_patch_report.tsv")
    int_pres=[]
    for r in int_report:
        name=r["file"]
        _,s=b.iso_read_file(SOURCE_ISO,PARTS+[name])
        _,d=b.iso_read_file(OUTPUT_ISO,PARTS+[name])
        int_pres.append({"file":name,"source_sha256":sha256_bytes(s),"output_sha256":sha256_bytes(d),"preserved":int(s==d)})
    if not all(x["preserved"] for x in int_pres):
        raise RuntimeError("Stage69 INT preservation failed")
    write_tsv(out/"int92_preservation.tsv",["file","source_sha256","output_sha256","preserved"],int_pres)

    # Preserve all 8 already-patched movie ST1 files.
    movie=read_tsv(pkg/"evidence"/"movie_st1_lineage_verified.tsv")
    mov_pres=[]
    for r in movie:
        name=r["file"]
        _,s=b.iso_read_file(SOURCE_ISO,PARTS+[name])
        _,d=b.iso_read_file(OUTPUT_ISO,PARTS+[name])
        mov_pres.append({"file":name,"source_sha256":sha256_bytes(s),"output_sha256":sha256_bytes(d),"preserved":int(s==d)})
    if not all(x["preserved"] for x in mov_pres):
        raise RuntimeError("Movie ST1 preservation failed")
    write_tsv(out/"movie_st1_preservation.tsv",["file","source_sha256","output_sha256","preserved"],mov_pres)

    # Title/menu resources not part of the 32 target MDIs must remain unchanged.
    base_names=["ON_MEMU_O.MDI","ON_MEMU.DSL","ON_MEMU.DSX"]
    base_pres=[]
    for name in base_names:
        _,s=b.iso_read_file(SOURCE_ISO,PARTS+[name])
        _,d=b.iso_read_file(OUTPUT_ISO,PARTS+[name])
        base_pres.append({"file":name,"source_sha256":sha256_bytes(s),"output_sha256":sha256_bytes(d),"preserved":int(s==d)})
    if not all(x["preserved"] for x in base_pres):
        raise RuntimeError("Title/menu baseline preservation failed")
    write_tsv(out/"baseline_preservation.tsv",["file","source_sha256","output_sha256","preserved"],base_pres)

    source_sha_after=sha256_file(SOURCE_ISO)
    if source_sha_after!=source_sha_before:
        raise RuntimeError("Source ISO changed during build")

    write_tsv(out/"mdi_build_report.tsv",
              ["mdi","target_reference_rows","unique_english","patched_reference_rows","in_place_translations",
               "tail_slack_translations","changed_streams","original_mdi_size","patched_mdi_size",
               "original_sha256","patched_sha256","font_full_coverage_candidates"],mdi_reports)
    write_tsv(out/"compiled967_patch_refs.tsv",
              ["mdi","metadata_stream","metadata_offset","resource_ids","english","korean","payload_ptr",
               "payload_bytes","allocation_method","before_hex","after_hex"],patch_rows)
    write_tsv(out/"tail_slack_allocations.tsv",
              ["mdi","english","korean","method","payload_ptr","payload_stream","payload_offset",
               "payload_bytes","owner_english"],alloc_rows)

    if len(patch_rows)!=2333:
        raise RuntimeError(f"patched ref count {len(patch_rows)} != 2333")
    patched_ids=set()
    for r in patch_rows:
        patched_ids.update(x for x in r["resource_ids"].split(";") if x in compiled_ids)
    if len(patched_ids)!=967:
        raise RuntimeError(f"patched ID count {len(patched_ids)} != 967")

    report={
        "step":"STEP_074",
        "status":"BUILT_UNVERIFIED",
        "source_iso":str(SOURCE_ISO),
        "source_sha256_before":source_sha_before,
        "source_sha256_after":source_sha_after,
        "source_iso_preserved":source_sha_before==source_sha_after,
        "output_iso":str(OUTPUT_ISO),
        "output_sha256":sha256_file(OUTPUT_ISO),
        "compiled_mdi_ids_static_applied":len(patched_ids),
        "compiled_mdi_reference_rows_patched":len(patch_rows),
        "target_mdis_patched":len(target_mdis),
        "all_target_mdis_iso_readback_verified":True,
        "font_coverage_gate_passed":True,
        "int92_files_preserved":len(int_pres),
        "movie_st1_files_preserved":len(mov_pres),
        "title_menu_baseline_files_preserved":len(base_pres),
        "int92_runtime_status":"BUILT_UNVERIFIED",
        "compiled967_runtime_verified":False,
        "movie_106_repatched":False,
        "movie_playback_validation_resumed":False,
        "new_objective_title_fixed":False,
    }
    (out/"step074_report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    (out/"BUILD_COMPLETE.txt").write_text(
        "STEP_074 BUILT_UNVERIFIED\n"
        f"compiled IDs: {len(patched_ids)}\n"
        f"FString refs: {len(patch_rows)}\n"
        f"MDIs: {len(target_mdis)}\n"
        f"output: {OUTPUT_ISO}\n"
        "runtime verification: NO\n",
        encoding="utf-8"
    )
    print(json.dumps(report,ensure_ascii=False),flush=True)

if __name__=="__main__":
    main()
