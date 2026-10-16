#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BIA STEP077: independently correlate DSL relocation source/target data.

This diagnostic does not patch an ISO, DSL, DSX, or MDI.  Exact byte-data
similarity is not by itself proof of a font texture binding.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import importlib.util
import json
import struct
import traceback
from collections import Counter
from pathlib import Path

ROOT = Path(r'PROJECT_ROOT')
ORIGINAL = ROOT / 'Brothers in Arms - D-Day (USA) (v1.01).iso'
SOURCE = ROOT / 'BIA_STAGE69_FIX2_NONMDI_INT92_TEST.iso'
PARTS = ['PSP_GAME','USRDIR','SYSTEM']
REF_STEM = 'D0_0130_'
REF_OFF = 0x31E2AE
REF_TRIPLE = (0x40055140, 0x80, 0x4010E9C0)
PTR_BASE = 0x40000000
B8_WORD = struct.pack('<I', 0xB8000807)
WINDOW_SIZE = 128


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda: f.read(4*1024*1024), b''):
            h.update(b)
    return h.hexdigest()


def read_tsv(path):
    with open(path, encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f, delimiter='\t'))


def write_tsv(path, rows, columns):
    with open(path,'w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=columns,delimiter='\t',extrasaction='ignore')
        w.writeheader()
        w.writerows(rows)


def ptr_slice(blob: bytes, ptr: int, length: int):
    off=ptr-PTR_BASE
    if off<0 or off+length>len(blob):
        return None
    return blob[off:off+length]


def byte_similarity(a: bytes | None,b: bytes | None):
    if a is None or b is None or len(a)!=len(b):
        return -1.0
    return sum(x==y for x,y in zip(a,b))/len(a) if a else 0.0


def common_blocks(a: bytes | None,b: bytes | None, block=16):
    if a is None or b is None:
        return 0
    blocks=min(len(a),len(b))//block
    return sum(a[i*block:(i+1)*block]==b[i*block:(i+1)*block] for i in range(blocks))


def scan_reloc_candidates(blob):
    # 0x80 is the observed source length, not a semantic proof.  Scan all
    # matching record-shaped triples, including bytewise-unaligned records.
    pat=struct.pack('<I',REF_TRIPLE[1])
    pos=0
    found=[]
    while True:
        k=blob.find(pat,pos)
        if k<0: break
        pos=k+1
        p=k-4
        if p<0 or p+12>len(blob):continue
        a,b,c=struct.unpack_from('<III',blob,p)
        if not (0x40000000<=a<0x41000000 and b==128 and 0x40000000<=c<0x42000000):
            continue
        src=ptr_slice(blob,a,128)
        dst=ptr_slice(blob,c,128)
        found.append({'offset':p,'a':a,'b':b,'c':c,'a_data':src,'c_data':dst})
    return found


def count_occurrences(blob,needle):
    count=0;at=0
    while True:
        at=blob.find(needle,at)
        if at<0:break
        count+=1;at+=1
    return count


def analyze_one(mdi, blob, ref_a, ref_c, expected_ref=False):
    candidates=scan_reloc_candidates(blob)
    ref_a_tail=ref_a[16:] if ref_a is not None else None
    ref_c_tail=ref_c[16:] if ref_c is not None else None
    matchrows=[]
    for item in candidates:
        ca=item['a_data']; cc=item['c_data']
        a_sim=byte_similarity(ca,ref_a)
        c_sim=byte_similarity(cc,ref_c)
        a_blocks=common_blocks(ca,ref_a)
        c_blocks=common_blocks(cc,ref_c)
        a_exact16 = (ca is not None and ref_a is not None and ca[:16]==ref_a[:16])
        c_exact16 = (cc is not None and ref_c is not None and cc[:16]==ref_c[:16])
        a_exact32 = (ca is not None and ref_a is not None and ca[:32]==ref_a[:32])
        c_exact32 = (cc is not None and ref_c is not None and cc[:32]==ref_c[:32])
        a_exact64 = (ca is not None and ref_a is not None and ca[:64]==ref_a[:64])
        c_exact64 = (cc is not None and ref_c is not None and cc[:64]==ref_c[:64])
        a_full = (ca is not None and ca==ref_a)
        c_full = (cc is not None and cc==ref_c)
        # Ranking only. Do not label a patch position from these scores.
        score=(int(a_exact16)*50 + int(c_exact16)*50 + int(a_exact32)*100 +
               int(c_exact32)*100 + int(a_exact64)*200 + int(c_exact64)*200 +
               int(a_full)*400 + int(c_full)*400 + a_blocks*5 + c_blocks*5 +
               max(0,a_sim)*20 + max(0,c_sim)*20)
        matchrows.append({
            'mdi':mdi,'offset':f'0x{item["offset"]:08X}',
            'a_ptr':f'0x{item["a"]:08X}', 'c_ptr':f'0x{item["c"]:08X}',
            'a_ptr_in_file':int(ca is not None),'c_ptr_in_file':int(cc is not None),
            'a_sha256':hashlib.sha256(ca).hexdigest() if ca is not None else '',
            'c_sha256':hashlib.sha256(cc).hexdigest() if cc is not None else '',
            'a_similarity':round(a_sim,4),'c_similarity':round(c_sim,4),
            'a_matching_16byte_blocks':a_blocks,'c_matching_16byte_blocks':c_blocks,
            'a_equal_16':int(a_exact16),'c_equal_16':int(c_exact16),
            'a_equal_32':int(a_exact32),'c_equal_32':int(c_exact32),
            'a_equal_64':int(a_exact64),'c_equal_64':int(c_exact64),
            'a_equal_128':int(a_full),'c_equal_128':int(c_full),
            'data_rank_score':round(score,2),
            'known_reference_offset':int(expected_ref and item['offset']==REF_OFF),
        })
    matchrows.sort(key=lambda r:(-float(r['data_rank_score']),int(r['offset'],16)))
    for i,r in enumerate(matchrows,1):r['rank_by_payload']=i
    exact_c=[r for r in matchrows if r['c_equal_128']]
    strong=[r for r in matchrows if r['c_equal_64'] or r['a_equal_64']]
    best=matchrows[0] if matchrows else None
    second=matchrows[1] if len(matchrows)>1 else None
    summary={
        'mdi':mdi,
        'candidate_count':len(matchrows),
        'valid_both_pointers':sum(r['a_ptr_in_file'] and r['c_ptr_in_file'] for r in matchrows),
        'exact_128_c_matches':len(exact_c),
        'strong_64_matches_either':len(strong),
        'best_offset':best['offset'] if best else '',
        'best_score':best['data_rank_score'] if best else 0,
        'second_score':second['data_rank_score'] if second else 0,
        'best_a_similarity':best['a_similarity'] if best else -1,
        'best_c_similarity':best['c_similarity'] if best else -1,
        'known_first_reference_in_candidates':int(any(r['known_reference_offset'] for r in matchrows)),
        'known_first_reference_best':int(bool(best and best['known_reference_offset'])),
        'b8_0807_count':count_occurrences(blob,B8_WORD),
        'semantic_font_binding_proven':0,
        'safe_to_patch':0,
    }
    return summary,matchrows


def load_helper():
    h=ROOT/'bia_stage40i_tools'/'bia_stage40i_actual_resource_trace.py'
    if not h.exists():raise RuntimeError(f'Missing verified helper: {h}')
    sp=importlib.util.spec_from_file_location('bia_step077_helper',h)
    mod=importlib.util.module_from_spec(sp)
    assert sp.loader is not None
    sp.loader.exec_module(mod)
    _,b=mod.load_helpers()
    return b


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--package-root',required=True)
    p.add_argument('--outdir',required=True)
    a=p.parse_args()
    package=Path(a.package_root)
    out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)
    old_report=json.loads((package/'evidence'/'step076_report.json').read_text(encoding='utf-8-sig'))
    if old_report['target_mdis']!=32 or old_report['validated_per_mdi_patch_targets']!=0:
        raise RuntimeError('STEP076 evidence mismatch')
    profiles=read_tsv(package/'evidence'/'linked_dsl_profiles.tsv')
    if len(profiles)!=32:raise RuntimeError('Expected 32 STEP076 DSL profiles')
    if not ORIGINAL.exists() or not SOURCE.exists():raise RuntimeError('Missing original/Stage69 ISO')
    before=file_sha256(SOURCE)
    helper=load_helper()
    _,ref_blob=helper.iso_read_file(ORIGINAL,PARTS+[REF_STEM+'.DSL'])
    if struct.unpack_from('<III',ref_blob,REF_OFF)!=REF_TRIPLE:
        raise RuntimeError('First-mission ground-truth relocation changed')
    ref_a=ptr_slice(ref_blob,REF_TRIPLE[0],WINDOW_SIZE)
    ref_c=ptr_slice(ref_blob,REF_TRIPLE[2],WINDOW_SIZE)
    if ref_a is None or ref_c is None:
        raise RuntimeError('First-mission a/c data not present in file: cannot interpret data pointers')
    refs={
        'reference_dsl':REF_STEM+'.DSL',
        'offset':f'0x{REF_OFF:08X}',
        'triple':[f'0x{x:08X}' for x in REF_TRIPLE],
        'a_bytes_sha256':hashlib.sha256(ref_a).hexdigest(),
        'c_bytes_sha256':hashlib.sha256(ref_c).hexdigest(),
        'a_first_64_hex':ref_a[:64].hex(),
        'c_first_64_hex':ref_c[:64].hex(),
        'reference_data_window_bytes':WINDOW_SIZE,
        'semantic_note':'These bytes are linked to the known first-mission relocation, but are not proven portable font identity markers.',
    }
    (out/'known_first_relocation_payload_fingerprint.json').write_text(json.dumps(refs,indent=2),encoding='utf-8')
    records=[];details=[]
    for index,pr in enumerate(sorted(profiles,key=lambda x:x['mdi']),1):
        mdi=pr['mdi'];dsl=mdi[:-4]+'.DSL'
        print(f'[payload audit {index:02d}/32] {dsl}',flush=True)
        _,blob=helper.iso_read_file(ORIGINAL,PARTS+[dsl])
        sumrow,cands=analyze_one(mdi,blob,ref_a,ref_c,mdi==REF_STEM+'.MDI')
        # Confirm the first-mission extraction faithfully reproduces known case.
        if mdi==REF_STEM+'.MDI' and not sumrow['known_first_reference_in_candidates']:
            raise RuntimeError('Positive control: known first relocation absent from scanner')
        records.append(sumrow)
        details.extend(cands[:20])
        with (out/'step077_progress.jsonl').open('a',encoding='utf-8') as f:
            f.write(json.dumps(sumrow,ensure_ascii=False)+'\n')
    write_tsv(out/'relocation_payload_profiles.tsv',records,list(records[0]))
    detail_fields=list(details[0]) if details else []
    if details:write_tsv(out/'ranked_relocation_payload_matches.tsv',details,detail_fields)
    if len(records)!=32:raise RuntimeError('Not all 32 MDIs processed')
    first=next(x for x in records if x['mdi']==REF_STEM+'.MDI')
    report={
        'step':'STEP_077',
        'status':'VERIFIED_PAYLOAD_CORRELATION_DIAGNOSTIC',
        'iso_modified':False,'output_iso_created':False,
        'target_mdis':32,
        'positive_control_found':bool(first['known_first_reference_in_candidates']),
        'positive_control_ranked_first':bool(first['known_first_reference_best']),
        'other_mdis_with_exact_c_128_match':sum(x['exact_128_c_matches']>0 for x in records if x['mdi']!=REF_STEM+'.MDI'),
        'other_mdis_with_unique_exact_c_128_match':sum(x['exact_128_c_matches']==1 for x in records if x['mdi']!=REF_STEM+'.MDI'),
        'other_mdis_with_strong_a_or_c_64_match':sum(x['strong_64_matches_either']>0 for x in records if x['mdi']!=REF_STEM+'.MDI'),
        'validated_per_mdi_patch_targets':0,
        'why_not_verified':'Shared raw payload data or record rank alone cannot prove the MDI TMR18 font binding or identify which GPU B8 command to patch.',
        'source_iso_sha_before':before,
        'source_iso_sha_after':file_sha256(SOURCE),
        'next_action':'If cross-MDI signatures are unique, corroborate with runtime TMR18 texture binding and GPU state; otherwise inspect verified first-mission pointer semantics in decoded DSL/DSX loader. No patch until semantic linkage proven.',
    }
    report['source_iso_preserved']=report['source_iso_sha_before']==report['source_iso_sha_after']
    (out/'step077_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    if not report['source_iso_preserved']:
        raise RuntimeError('Source ISO SHA256 changed unexpectedly')
    print(json.dumps(report,ensure_ascii=False),flush=True)

if __name__=='__main__':
    main()
