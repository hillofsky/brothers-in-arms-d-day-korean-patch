#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BIA STEP076 - diagnostic ONLY: compare actual relocation record runs and GPU
TEXSIZE command contexts. No ISO or game resource mutation.

Candidates are ranked as hypotheses, never patch locations, until a unique
semantic binding to the font texture has been established.
"""
from __future__ import annotations
import argparse, csv, hashlib, importlib.util, json, struct
from collections import Counter, defaultdict
from pathlib import Path

ROOT=Path(r'PROJECT_ROOT')
ORIGINAL=ROOT/'Brothers in Arms - D-Day (USA) (v1.01).iso'
SOURCE=ROOT/'BIA_STAGE69_FIX2_NONMDI_INT92_TEST.iso'
PARTS=['PSP_GAME','USRDIR','SYSTEM']
FIRST='D0_0130_.MDI'
REF_RELOC_OFF=0x31E2AE
REF_B8_OFF=0x4ACEE4
REF_RELOC=(0x40055140,0x80,0x4010E9C0)
REF_B8=0xB8000807
MOD_RELOC=(0x40055140,512,0xF620CFE0)
MOD_B8=0xB8000909
SIZE_SET={0x10,0x20,0x40,0x80,0x100,0x200,0x400,0x800}


def read_tsv(path):
    with open(path,encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f,delimiter='\t'))

def save_tsv(path,rows,fields):
    with open(path,'w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,delimiter='\t',extrasaction='ignore')
        w.writeheader();w.writerows(rows)

def sha(data):return hashlib.sha256(data).hexdigest()

def hexdump(data,off,before=96,after=128):
    a=max(0,off-before);e=min(len(data),off+after)
    return {'anchor':f'0x{off:08X}','from':f'0x{a:08X}','to':f'0x{e:08X}','hex':data[a:e].hex()}

def parse_triple(data,p):
    if p<0 or p+12>len(data):return None
    a,b,c=struct.unpack_from('<III',data,p)
    # This is a deliberately strict descriptor RECORD shape. It is a diagnostic
    # filter only and DOES NOT establish a texture linkage.
    ok=(0x40000000<=a<0x41000000 and b in SIZE_SET and 0x40000000<=c<0x42000000)
    return (a,b,c) if ok else None

def contiguous_context(data, p, left=12, right=12):
    out=[]; strict_count=0
    for delta in range(-left,right+1):
        at=p+delta*12
        if at<0 or at+12>len(data):continue
        a,b,c=struct.unpack_from('<III',data,at)
        valid=parse_triple(data,at) is not None
        if valid:strict_count+=1
        out.append({'delta':delta,'off':hex(at),'a':hex(a),'b':b,'c':hex(c),'shape':bool(valid)})
    # Maximum uninterrupted strict chain containing the central anchor.
    run=1
    for direction in (-1,1):
        step=1
        while parse_triple(data,p+direction*step*12) is not None and step<=300:
            run+=1;step+=1
    return out,run,strict_count

def ref_signature(data,off):
    # Relative sizes + pointer-delta structure (not absolute addresses).
    records=[]
    for i in range(-7,8):
        p=off+i*12
        if p<0 or p+12>len(data):return None
        records.append(struct.unpack_from('<III',data,p))
    return records

def relativity_score(cand,ref):
    if ref is None:return 0
    valid=0; matched_sizes=0; matched_a_delta=0;matched_c_delta=0
    for i in range(-7,8):
        p=i*12
        if p==0:continue
        # The caller passes only the available neighborhood for this candidate.
    return 0

def rank_relocations(data,ref):
    # Search the distinctive one-page 128-byte copy-size field, then recover
    # the surrounding 12-byte relocation-record run.
    anchor=b'\x80\x00\x00\x00'
    cand=[];start=0
    while True:
        k=data.find(anchor,start)
        if k<0:break
        start=k+1
        p=k-4
        t=parse_triple(data,p)
        if t is None:continue
        records,run,strict=contiguous_context(data,p,7,7)
        if run<3:continue
        ref_quality=0
        if ref:
            for item in records:
                i=item['delta'];at=p+i*12
                if abs(i)>7 or at<0 or at+12>len(data):continue
                a,b,c=struct.unpack_from('<III',data,at)
                ra,rb,rc=ref[i+7]
                if b==rb:ref_quality+=2
                if i and 0x40000000<=a<0x41000000 and 0x40000000<=ra<0x41000000:
                    ca,cb,cc=t;r0=ref[7]
                    if abs((a-ca)-(ra-r0[0]))<=0x40:ref_quality+=2
                    if abs((c-cc)-(rc-r0[2]))<=0x400:ref_quality+=1
        score=run*5+strict*2+ref_quality
        cand.append({'offset_int':p,'offset':f'0x{p:08X}',
                     'a':f'0x{t[0]:08X}','b':t[1],'c':f'0x{t[2]:08X}',
                     'run_len':run,'window_shape_count':strict,
                     'reference_neighborhood_score':ref_quality,
                     'ranking_score':score,
                     'neighbor_records':records})
    cand.sort(key=lambda x:(-x['ranking_score'],-x['run_len'],x['offset_int']))
    return cand

def all_texsize(data):
    pattern=struct.pack('<I',REF_B8);out=[];pos=0
    while True:
        p=data.find(pattern,pos)
        if p<0:break
        pos=p+1
        out.append(p)
    return out

def gpu_context_score(data,pos,first,first_pos):
    # Compare invariant four-byte GPU/script commands, masking address payloads.
    score=0;matches=[]
    for delta in range(-80,81,4):
        if delta==0:continue
        a=pos+delta;b=first_pos+delta
        if min(a,b)<0 or a+4>len(data) or b+4>len(first):continue
        wa=struct.unpack_from('<I',data,a)[0]
        wb=struct.unpack_from('<I',first,b)[0]
        if wa==wb:
            score+=3;matches.append(delta)
        elif wa>>24==wb>>24:
            score+=1
    return score,matches

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--package-root',required=True)
    ap.add_argument('--outdir',required=True)
    a=ap.parse_args()
    pkg=Path(a.package_root);out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)
    iso_helper=ROOT/'bia_stage40i_tools'/'bia_stage40i_actual_resource_trace.py'
    if not iso_helper.exists():raise RuntimeError('Missing verified BIA helper '+str(iso_helper))
    spec=importlib.util.spec_from_file_location('bia_step076_helper',iso_helper)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    _,helper=mod.load_helpers()

    profiles=read_tsv(pkg/'evidence'/'dsl_file_profiles.tsv')
    if len(profiles)!=32:raise RuntimeError(f'Expected 32 profiles, got {len(profiles)}')
    for p in (ORIGINAL,SOURCE):
        if not p.is_file():raise RuntimeError('Missing ISO '+str(p))
    source_sha_before=hashlib.sha256()
    # Full streaming SHA, one read pass.
    with SOURCE.open('rb') as f:
        for ch in iter(lambda:f.read(4*1024*1024),b''):source_sha_before.update(ch)
    source_sha_before=source_sha_before.hexdigest()

    _,first_org=helper.iso_read_file(ORIGINAL,PARTS+[FIRST[:-4]+'.DSL'])
    _,first_src=helper.iso_read_file(SOURCE,PARTS+[FIRST[:-4]+'.DSL'])
    if struct.unpack_from('<III',first_org,REF_RELOC_OFF)!=REF_RELOC:
        raise RuntimeError('Original D0 relocation reference drift')
    if struct.unpack_from('<III',first_src,REF_RELOC_OFF)!=MOD_RELOC:
        raise RuntimeError('Stage69 first-mission patched relocation drift')
    if struct.unpack_from('<I',first_org,REF_B8_OFF)[0]!=REF_B8:
        raise RuntimeError('Original D0 reference TEXSIZE drift')
    if struct.unpack_from('<I',first_src,REF_B8_OFF)[0]!=MOD_B8:
        raise RuntimeError('Stage69 first-mission TEXSIZE drift')
    reference_records=ref_signature(first_org,REF_RELOC_OFF)
    if reference_records is None:raise RuntimeError('No reference relocation neighborhood')

    results=[];rrows=[];grows=[];detail={}
    for i,rec in enumerate(sorted(profiles,key=lambda r:r['mdi']),1):
        mdi=rec['mdi'];name=mdi[:-4]+'.DSL'
        print(f'[linked audit {i:02d}/32] {name}',flush=True)
        _,data=helper.iso_read_file(SOURCE,PARTS+[name])
        _,original=helper.iso_read_file(ORIGINAL,PARTS+[name])
        if mdi!=FIRST and data!=original:raise RuntimeError(f'{mdi}: unexpected source/original DSL drift')
        candidates=rank_relocations(original,reference_records)
        texsize=all_texsize(original)
        g=[]
        for pos in texsize:
            s,matched=gpu_context_score(original,pos,first_org,REF_B8_OFF)
            row={'mdi':mdi,'offset':f'0x{pos:08X}','gpu_reference_score':s,
                 'matched_exact_deltas':','.join(map(str,matched))}
            g.append(row)
        g.sort(key=lambda x:(-x['gpu_reference_score'],int(x['offset'],16)))
        for rank,c in enumerate(candidates[:10],1):
            rrows.append({k:c[k] for k in ('offset','a','b','c','run_len','window_shape_count','reference_neighborhood_score','ranking_score')}|{'mdi':mdi,'rank':rank})
        for rank,row in enumerate(g,1):grows.append(row|{'rank':rank})
        unique_reloc= len(candidates)>=1 and (len(candidates)==1 or candidates[0]['ranking_score']>candidates[1]['ranking_score']+10)
        unique_texsize=len(g)>=1 and (len(g)==1 or g[0]['gpu_reference_score']>g[1]['gpu_reference_score']+10)
        result={'mdi':mdi,'dsl':name,'dsl_size':len(data),'dsl_sha256':sha(data),
                'source_equals_original':int(original==data),
                'one_page_relocation_candidates':len(candidates),
                'highest_rank_reloc':candidates[0]['offset'] if candidates else '',
                'highest_rank_reloc_score':candidates[0]['ranking_score'] if candidates else 0,
                'rank_margin_reloc':candidates[0]['ranking_score']-candidates[1]['ranking_score'] if len(candidates)>1 else -1,
                'b8_texsize_count':len(g),
                'best_b8':g[0]['offset'] if g else '',
                'best_b8_score':g[0]['gpu_reference_score'] if g else 0,
                'rank_margin_b8':g[0]['gpu_reference_score']-g[1]['gpu_reference_score'] if len(g)>1 else -1,
                'reloc_unique_by_heuristic_only':int(unique_reloc),
                'b8_unique_by_heuristic_only':int(unique_texsize),
                'semantic_texture_binding_proven':0}
        results.append(result)
        detail[mdi]={
            'reference':mdi==FIRST,
            'source_vs_original_changed':data!=original,
            'top_relocation_hypotheses':candidates[:8],
            'gpu_texsize_hypotheses':g,
            'top_reloc_raw_context':[hexdump(original,c['offset_int'],60,120) for c in candidates[:4]],
            'gpu_texsize_raw_context':[hexdump(original,int(c['offset'],16),64,96) for c in g],
        }
        (out/'step076_progress.jsonl').open('a',encoding='utf-8').write(json.dumps(result,ensure_ascii=False)+'\n')

    source_sha_after=hashlib.sha256()
    with SOURCE.open('rb') as f:
        for ch in iter(lambda:f.read(4*1024*1024),b''):source_sha_after.update(ch)
    source_sha_after=source_sha_after.hexdigest()
    if source_sha_before!=source_sha_after:raise RuntimeError('Source ISO SHA changed')
    save_tsv(out/'linked_dsl_profiles.tsv',results,list(results[0]))
    save_tsv(out/'ranked_relocation_groups.tsv',rrows,
      ['mdi','rank','offset','a','b','c','run_len','window_shape_count','reference_neighborhood_score','ranking_score'])
    save_tsv(out/'ranked_texsize_commands.tsv',grows,
      ['mdi','rank','offset','gpu_reference_score','matched_exact_deltas'])
    (out/'dsl_linked_contexts.json').write_text(json.dumps(detail,ensure_ascii=False,indent=2),encoding='utf-8')
    report={'step':'STEP_076','status':'VERIFIED_TARGETED_DSL_DIAGNOSTIC',
            'target_mdis':32,'original_first_reloc_confirmed':True,
            'stage69_first_reloc_confirmed':True,
            'original_first_texsize_confirmed':True,
            'stage69_first_texsize_confirmed':True,
            'source_iso_sha_before':source_sha_before,
            'source_iso_sha_after':source_sha_after,
            'source_iso_preserved':True,
            'original_unchanged_dsl_count':sum(r['source_equals_original'] for r in results),
            'files_with_reloc_hypotheses':sum(bool(r['one_page_relocation_candidates']) for r in results),
            'files_with_b8_hypotheses':sum(bool(r['b8_texsize_count']) for r in results),
            'uniquely_ranked_reloc_not_verified':sum(r['reloc_unique_by_heuristic_only'] for r in results),
            'uniquely_ranked_b8_not_verified':sum(r['b8_unique_by_heuristic_only'] for r in results),
            'validated_per_mdi_patch_targets':0,
            'iso_modified':False,'output_iso_created':False,
            'next_action':'Correlate ranked run/B8 contexts to actual TMR18 texture through runtime or documented Magma DSL descriptor structure before any non-first-mission patch.'}
    (out/'step076_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
