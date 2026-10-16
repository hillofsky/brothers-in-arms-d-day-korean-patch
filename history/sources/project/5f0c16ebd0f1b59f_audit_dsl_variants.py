#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Exact campaign/skirmish DSL relocation audit. NO ISO WRITES."""
from __future__ import annotations
import argparse, collections, csv, hashlib, importlib.util, json, struct, time
from pathlib import Path

ROOT=Path(r'PROJECT_ROOT')
ORIGINAL=ROOT/'Brothers in Arms - D-Day (USA) (v1.01).iso'
SOURCE=ROOT/'BIA_STAGE69_FIX2_NONMDI_INT92_TEST.iso'
PARTS=['PSP_GAME','USRDIR','SYSTEM']
WIDTHS=(64,128,256,512,1024)
REFERENCE_DSL='D0_0130_.DSL'
FIRST_RELOC=(0x40055140,0x80,0x4010E9C0)
FIRST_B8=0xB8000807
EXPECTED_STRICT_UNPATCHED=31


def sha(b):return hashlib.sha256(b).hexdigest()
def hex8(x):return '0x%08X'%x
def findall(data,pattern,limit=50000):
    off=0;res=[]
    while True:
        i=data.find(pattern,off)
        if i<0:break
        res.append(i)
        if len(res)>=limit:break
        off=i+1
    return res

def signature_candidates(dsl):
    """Search raw DWORD triples by neutral data shape, not first-mission offsets."""
    candidates={}
    for width in WIDTHS:
        for off in findall(dsl,struct.pack('<I',width)):
            if off<4 or off+8>len(dsl):continue
            a,b,c=struct.unpack_from('<III',dsl,off-4)
            if (a>>28) not in (4,8,9,0xB):continue
            # No hard claim that any such triple is a texture descriptor.
            key=(off-4,a,b,c)
            candidates[key]=dict(offset=hex8(off-4),a=hex8(a),b=b,c=hex8(c),offset_int=off-4,alignment=(off-4)%4)
    return list(sorted(candidates.values(),key=lambda r:r['offset_int']))

def b8_candidates(dsl):
    # Find raw words with high byte 0xB8, at any offset alignment, then narrow
    # to likely GPU commands without claiming they are the desired binding.
    result=[]
    for index in findall(dsl,b'\xB8'):
        off=index-3
        if off<0 or off+4>len(dsl):continue
        v=struct.unpack_from('<I',dsl,off)[0]
        if v>>24 != 0xB8:continue
        low=v & 0xFFFFFF
        if low in (0x000807,0x000909) or low>>16 in (0x00,0x08,0x09) or low&0xFFFF in (0x0807,0x0909):
            result.append(dict(offset=hex8(off),offset_int=off,value=hex8(v),alignment=off%4))
    return result

def get_window(data,off,range_before=96,range_after=128):
    a=max(0,off-range_before);b=min(len(data),off+range_after)
    return dict(from_offset=hex8(a),to_offset=hex8(b),data_hex=data[a:b].hex())

def save_tsv(path, rows, fields):
    with open(path,'w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,delimiter='\t',extrasaction='ignore')
        w.writeheader();w.writerows(rows)

def get_helper(pkg):
    h=ROOT/'bia_stage40i_tools'/'bia_stage40i_actual_resource_trace.py'
    if not h.is_file():raise RuntimeError('Missing previously verified helper: '+str(h))
    spec=importlib.util.spec_from_file_location('bia_stage40i_step075',h)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    _,helper=mod.load_helpers()
    p=pkg/'evidence'/'build_compiled967_fix6.py'
    spec2=importlib.util.spec_from_file_location('step074_fix6_readonly',p)
    ref=importlib.util.module_from_spec(spec2);spec2.loader.exec_module(ref)
    return helper,ref

def font_role_textures(mdi, helper, ref, tm, tnorm):
    _,data=helper.iso_read_file(ORIGINAL,PARTS+[mdi])
    streams=ref.parse_mdi_dict(helper,data)
    mset=set(tm)
    cands=ref.scan_font_candidates(streams,tnorm,mset)
    pair=ref.choose_font_pair(cands,tm)
    if pair is None:return {'error':'NO_FONT_PAIR','candidate_count':len(cands)}
    if pair.get('ambiguous'):return {'error':'AMBIGUOUS_FONT_PAIR','candidate_count':len(cands)}
    arr=pair['selected']
    return dict(
        candidate_count=len(cands),
        template_0_font_offset=hex8(arr[0]['offset']),
        template_1_font_offset=hex8(arr[1]['offset']),
        template_0_texture=hex8(arr[0]['texture_object']),
        template_1_texture=hex8(arr[1]['texture_object']),
        template_1_texture_int=arr[1]['texture_object'],
        match_min_similarity=pair['min_template_similarity'],
    )

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--package-root',required=True)
    ap.add_argument('--outdir',required=True)
    a=ap.parse_args();pkg=Path(a.package_root);out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)
    helper,ref=get_helper(pkg)
    refs=ref.read_tsv(pkg/'evidence'/'allstream_fstring_refs.tsv')
    names=sorted({r['mdi'] for r in refs})
    if len(names)!=32 or 'D0_0130_.MDI' not in names:raise RuntimeError('Unexpected 32-MDI target inventory')
    _,first_blob=helper.iso_read_file(ORIGINAL,PARTS+['D0_0130_.MDI'])
    first_st=ref.parse_mdi_dict(helper,first_blob)
    tnorm=[];tm=[]
    for si,off in ref.KNOWN_FIRST_FONT_OFFSETS:
        d=first_st[si]
        tnorm.append(ref.normalize_font_object(d[off:off+0x490],ref.CAMPAIGN_BASE,len(first_st)))
        wp=struct.unpack_from('<I',d,off+0x474)[0]
        hp=struct.unpack_from('<I',d,off+0x478)[0]
        tm.append((ref.read_u16_ptr(first_st,wp),ref.read_u16_ptr(first_st,hp)))
    if tm!=[(128,512),(128,256)]:raise RuntimeError(f'Known font roles changed: {tm}')
    source_iso_before=dict(size=SOURCE.stat().st_size,sha256=ref.sha256_file(SOURCE))
    original_iso_sha=ref.sha256_file(ORIGINAL)
    out_records=[];candidate_rows=[];b8_rows=[];windows={}
    outputs=out/'dsl_snippets';outputs.mkdir(exist_ok=True)
    for ix,mdi in enumerate(names,1):
        stem=mdi[:-4];dslname=stem+'.DSL';dsxname=stem+'.DSX'
        print(f'[audit {ix:02d}/32] {dslname}',flush=True)
        _,src=helper.iso_read_file(SOURCE,PARTS+[dslname])
        _,org=helper.iso_read_file(ORIGINAL,PARTS+[dslname])
        _,dsx=helper.iso_read_file(SOURCE,PARTS+[dsxname])
        same_logical=(helper.dsx_logical_bytes(dsx)==src)
        font=font_role_textures(mdi,helper,ref,tm,tnorm)
        tri=signature_candidates(src)
        b8=b8_candidates(src)
        strong=findall(src,struct.pack('<III',*FIRST_RELOC))
        two=findall(src,struct.pack('<II',FIRST_RELOC[0],FIRST_RELOC[1]))
        aonly=findall(src,struct.pack('<I',FIRST_RELOC[0]))
        b8_exact=findall(src,struct.pack('<I',FIRST_B8))
        tval=font.get('template_1_texture_int')
        texptrs=[]
        if tval:
            for mode,v in [('texture_object',tval),('negative_texture_object',(-tval)&0xffffffff)]:
                for o in findall(src,struct.pack('<I',v))[:100]:
                    texptrs.append({'mode':mode,'offset':hex8(o),'value':hex8(v)})
        r=dict(
            mdi=mdi,dsl_file=dslname,dsl_bytes=len(src),dsl_sha256=sha(src),
            original_dsl_sha256=sha(org),original_equals_source=int(src==org),
            dsx_logical_equals_dsl=int(same_logical),
            first_mission_reloc_exact_count=len(strong),first_mission_reloc_prefix_count=len(two),
            first_mission_reloc_first_dword_count=len(aonly),
            first_mission_b8_exact_count=len(b8_exact),
            relocation_shape_candidate_count=len(tri),b8_candidate_count=len(b8),
            per_mdi_texture_literal_hits=len(texptrs),font_role1_texture=font.get('template_1_texture',''),
            font_pair_error=font.get('error',''),
        )
        out_records.append(r)
        for item in tri[:2000]:candidate_rows.append({'mdi':mdi,**item})
        for item in b8[:2000]:b8_rows.append({'mdi':mdi,**item})
        # Keep representative windows only, so logs remain compact.
        offsets=[0]
        offsets += strong[:6]+two[:6]+aonly[:6]+b8_exact[:6]
        offsets += [x['offset_int'] for x in tri[:16]]
        offsets += [x['offset_int'] for x in b8[:16]]
        offsets += [int(x['offset'],16) for x in texptrs[:16]]
        # Compare first-mission known raw offsets without assuming they carry over.
        for known in (0x31e2ae,0x4acee4):
            if known<len(src):offsets.append(known)
        uniq=sorted(set(offsets))
        windows[mdi]={
            'font':{k:v for k,v in font.items() if k!='template_1_texture_int'},
            'literal_texture_hits':texptrs,
            'reloc_shapes_first_30':tri[:30],
            'b8_candidates_first_30':b8[:30],
            'sample_windows':[{'anchor':hex8(k),**get_window(src,k)} for k in uniq[:65]],
        }
        (out/'per_mdi_dsl_progress.jsonl').open('a',encoding='utf-8').write(json.dumps(r,ensure_ascii=False)+'\n')
    source_iso_after=dict(size=SOURCE.stat().st_size,sha256=ref.sha256_file(SOURCE))
    if source_iso_before!=source_iso_after:raise RuntimeError('Source Stage69 SHA changed unexpectedly')
    save_tsv(out/'dsl_file_profiles.tsv',out_records,list(out_records[0]))
    save_tsv(out/'dsl_relocation_shape_candidates.tsv',candidate_rows,
             ['mdi','offset','a','b','c','offset_int','alignment'])
    save_tsv(out/'dsl_b8_command_candidates.tsv',b8_rows,
             ['mdi','offset','value','offset_int','alignment'])
    (out/'dsl_context_windows.json').write_text(json.dumps(windows,ensure_ascii=False,indent=2),encoding='utf-8')
    classified=collections.Counter()
    for r in out_records:
        cls='KNOWN_FIRST_MISSION_PATTERN' if r['first_mission_reloc_prefix_count'] else ('HAS_STRUCTURAL_TRIPLES' if r['relocation_shape_candidate_count'] else 'NO_MATCHING_TRIPLES')
        classified[cls]+=1
    report={
        'step':'STEP_075', 'status':'VERIFIED_DSL_VARIANT_AUDIT',
        'iso_modified':False,'output_iso_created':False,
        'target_mdi_count':len(names),
        'source_iso':str(SOURCE),'source_iso_sha_before':source_iso_before['sha256'],
        'source_iso_sha_after':source_iso_after['sha256'],
        'source_iso_preserved':True,
        'original_iso_sha256':original_iso_sha,
        'first_mission_reference_relocation':list(map(hex8,FIRST_RELOC)),
        'first_mission_reference_b8':hex8(FIRST_B8),
        'candidate_classification':dict(classified),
        'dsl_original_equals_stage69_count':sum(x['original_equals_source'] for x in out_records),
        'dsx_logical_equals_dsl_count':sum(x['dsx_logical_equals_dsl'] for x in out_records),
        'files_with_any_first_dword':sum(bool(x['first_mission_reloc_first_dword_count']) for x in out_records),
        'files_with_any_b8_candidates':sum(bool(x['b8_candidate_count']) for x in out_records),
        'files_with_texture_object_literal_hits':sum(bool(x['per_mdi_texture_literal_hits']) for x in out_records),
        'next_step': 'Determine validated per-MDI DSL texture binding and runtime relocation; do not patch on first-mission signature guess.',
        'compiled967_iso_built':False,'int92_runtime_status':'BUILT_UNVERIFIED',
        'movie_playback_validation_resumed':False,
    }
    (out/'step075_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'status':report['status'],'classification':report['candidate_classification']},ensure_ascii=False),flush=True)

if __name__=='__main__': main()
