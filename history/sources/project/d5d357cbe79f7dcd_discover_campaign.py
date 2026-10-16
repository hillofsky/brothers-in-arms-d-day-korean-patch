#!/usr/bin/env python3
from pathlib import Path
import argparse,csv,json,re

ap=argparse.ArgumentParser()
ap.add_argument('--project-root',required=True)
ap.add_argument('--out-dir',required=True)
a=ap.parse_args()
root=Path(a.project_root); work=root/'work'; trans=root/'translation'; out=Path(a.out_dir)
trans.mkdir(parents=True,exist_ok=True); out.mkdir(parents=True,exist_ok=True)
FIRST='D0_0130_.MDI'; SECOND='D0_0700_.MDI'

def loadj(p): return json.loads(p.read_text(encoding='utf-8'))
def ci(d,*names):
    low={str(k).lower():k for k in d}
    for n in names:
        k=low.get(n.lower())
        if k is not None and d[k] not in (None,'',[],{}): return d[k]
    return None

def recs(obj,path=()):
    if isinstance(obj,dict):
        keys={str(k).lower() for k in obj}
        if len(keys & {'english','source_text','text','original','string','source','references','offset','source_file','file','mdi','unit_id','id'})>=2:
            yield path,obj
        for k,v in obj.items(): yield from recs(v,path+(str(k),))
    elif isinstance(obj,list):
        for i,v in enumerate(obj): yield from recs(v,path+(str(i),))

def source_text(d):
    for n in ('english','source_text','original_text','original','text','string','source'):
        v=ci(d,n)
        if isinstance(v,str) and len(v.strip())>=2: return v
    return None

def source_file(d,hint=''):
    v=ci(d,'source_file','file','mdi','container_file','package','asset')
    if isinstance(v,str) and v.strip(): return Path(v.replace('\\','/')).name
    m=re.search(r'(D0_[0-9A-Za-z_]+\.MDI)',hint,re.I)
    return m.group(1) if m else ''

def off(d):
    v=ci(d,'offset','offset_hex','file_offset','address')
    if v is None:return ''
    return f'0x{v:X}' if isinstance(v,int) else str(v)

def ctrls(s):
    out=[]
    for p in (r'\\[nrt]',r'\{[^{}]+\}',r'%[-+0-9.]*[a-zA-Z]',r'<[^<>]+>'):
        out += re.findall(p,s)
    return '|'.join(dict.fromkeys(out))

def mission_num(s):
    m=re.search(r'D0_(\d+)',s,re.I); return int(m.group(1)) if m else 10**9

def refs(v):
    if v is None:return ''
    if isinstance(v,str):return v
    return json.dumps(v,ensure_ascii=False,separators=(',',':'))

# Required handoff inputs.
required=['campaign_first_ko.json','first_campaign_units.json','campaign_first_reference_audit.json',
          'campaign_second_ko.json','campaign_second_units.json','campaign_second_reference_audit.json']
for n in required:
    p=work/n
    if not p.exists(): raise FileNotFoundError(f'Required handoff file missing: {p}')

# Inventory likely campaign datasets.
cands=[]
for base in (work,root/'outputs'):
    if not base.exists(): continue
    for p in base.rglob('*'):
        if not p.is_file() or p.suffix.lower() not in ('.json','.tsv','.csv') or p.stat().st_size>60*1024*1024: continue
        n=p.name.lower(); score=0
        if 'campaign' in n: score+=5
        if 'unit' in n: score+=4
        if 'priority' in n: score+=3
        if 'audit' in n or 'reference' in n: score+=2
        if 'text' in n: score+=1
        if score: cands.append((score,p))
cands.sort(key=lambda x:(-x[0],str(x[1])))

rows=[]; errors=[]
for score,p in cands:
    try:
        if p.suffix.lower()=='.json':
            items=((d,path) for path,d in recs(loadj(p)))
        else:
            delim='\t' if p.suffix.lower()=='.tsv' else ','
            with p.open('r',encoding='utf-8-sig',errors='replace',newline='') as f: data=list(csv.DictReader(f,delimiter=delim))
            items=((d,()) for d in data)
        for d,path in items:
            s=source_text(d)
            if not s: continue
            sf=source_file(d,str(p)+' '+'/'.join(path))
            if not sf or not re.match(r'D0_.*\.MDI$',sf,re.I): continue
            rid=ci(d,'resource_id','unit_id','id','key')
            rr={
                'source_file':sf,'resource_id':'' if rid is None else str(rid),'offset':off(d),
                'context_before':str(ci(d,'context_before','before') or ''),'source_text':s,
                'context_after':str(ci(d,'context_after','after') or ''),'encoding':str(ci(d,'encoding') or 'UTF-8'),
                'max_bytes':str(ci(d,'max_bytes','field_bytes','byte_limit') or ''),
                'control_tokens':str(ci(d,'control_tokens') or ctrls(s)),'linebreak_rule':str(ci(d,'linebreak_rule') or ''),
                'references':refs(ci(d,'references','refs')),'origin_file':str(p.relative_to(root)),'score':score,
            }
            rows.append(rr)
    except Exception as e: errors.append({'file':str(p),'error':repr(e)})

# Deduplicate.
def rich(r): return r['score']*100+sum(bool(r[k]) for k in ('resource_id','offset','context_before','context_after','max_bytes','references'))
d={}
for r in rows:
    k=(r['source_file'].upper(),r['resource_id'],r['offset'],r['source_text'])
    if k not in d or rich(r)>rich(d[k]): d[k]=r
rows=list(d.values())
remaining=[r for r in rows if r['source_file'].upper() not in {FIRST.upper(),SECOND.upper()}]
groups={}
for r in remaining: groups.setdefault(r['source_file'],[]).append(r)
if not groups:
    (out/'candidate_inventory.json').write_text(json.dumps({'candidates':[str(p.relative_to(root)) for _,p in cands],'errors':errors},ensure_ascii=False,indent=2),encoding='utf-8')
    raise RuntimeError('No remaining D0_*.MDI campaign groups discovered')
after=[(mission_num(k),k) for k in groups if mission_num(k)>700]
selected=min(after)[1] if after else min(groups,key=lambda k:(mission_num(k),k))
batch=groups[selected]
batch.sort(key=lambda r:(r['offset']=='',r['offset'],r['resource_id'],r['source_text']))

fields=['id','category','source_file','resource_id','offset','context_before','source_text','context_after','ko_current','ko_review','encoding','max_bytes','control_tokens','linebreak_rule','status','notes']
master=trans/'text_master.tsv'; existing=[]
if master.exists():
    with master.open('r',encoding='utf-8-sig',errors='replace',newline='') as f:
        rd=csv.DictReader(f,delimiter='\t')
        existing=[{k:r.get(k,'') for k in fields} for r in rd]
nums=[]
for r in existing:
    m=re.fullmatch(r'TXT_(\d+)',r.get('id',''))
    if m: nums.append(int(m.group(1)))
next_id=max(nums,default=0)+1

def key(r): return '\x1f'.join(r.get(k,'') for k in ('category','source_file','resource_id','offset','source_text'))
by={key(r):r for r in existing}
outrows=[]
for r in batch:
    sk={'id':'','category':'campaign','source_file':r['source_file'],'resource_id':r['resource_id'],'offset':r['offset'],
        'context_before':r['context_before'],'source_text':r['source_text'],'context_after':r['context_after'],'ko_current':'','ko_review':'',
        'encoding':r['encoding'],'max_bytes':r['max_bytes'],'control_tokens':r['control_tokens'],'linebreak_rule':r['linebreak_rule'],
        'status':'NEEDS_TRANSLATION','notes':f"STEP_044 source={r['origin_file']}; refs={r['references']}"}
    k=key(sk)
    if k in by: row=by[k]
    else:
        sk['id']=f'TXT_{next_id:06d}'; next_id+=1; existing.append(sk); by[k]=sk; row=sk
    outrows.append(row.copy())

with master.with_suffix('.tmp').open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=fields,delimiter='\t',lineterminator='\n'); w.writeheader(); w.writerows(existing)
master.with_suffix('.tmp').replace(master)
next_tsv=trans/'campaign_next_translation.tsv'
with next_tsv.open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=fields,delimiter='\t',lineterminator='\n'); w.writeheader(); w.writerows(outrows)
ids=[r['id'] for r in existing if r['id']]; dup=sorted({x for x in ids if ids.count(x)>1}); blank=[r['id'] for r in outrows if not r['source_text'].strip()]
report={'step':'STEP_044','selected_source_file':selected,'selected_unit_count':len(outrows),'selected_mission_number':mission_num(selected),
        'candidate_group_counts':{k:len(v) for k,v in sorted(groups.items(),key=lambda kv:(mission_num(kv[0]),kv[0]))},
        'candidate_source_files':[str(p.relative_to(root)) for _,p in cands],'source_parse_errors':errors,'master_rows':len(existing),
        'validation':{'duplicate_ids':dup,'blank_source_ids':blank,'batch_nonempty':bool(outrows)},
        'known_status':{'first_mission':{'source_file':FIRST,'units':137,'status':'VERIFIED_APPLIED'},'second_mission':{'source_file':SECOND,'units':90,'status':'TRANSLATED_PENDING_APPLY'},'remaining_movie_validation':'DEFERRED_BY_USER','stage43t_menu_after_start':'PENDING'}}
(out/'campaign_discovery_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
(out/'translation_validation.tsv').write_text('check\tstatus\tdetail\n'+f"batch_nonempty\t{'PASS' if outrows else 'FAIL'}\t{len(outrows)} rows\n"+f"duplicate_ids\t{'PASS' if not dup else 'FAIL'}\t{','.join(dup)}\n"+f"blank_source\t{'PASS' if not blank else 'FAIL'}\t{','.join(blank)}\n",encoding='utf-8-sig')
(out/'text_master.tsv').write_bytes(master.read_bytes()); (out/'campaign_next_translation.tsv').write_bytes(next_tsv.read_bytes())
if dup or blank or not outrows: raise RuntimeError('Translation TSV validation failed')
print(json.dumps({'selected_source_file':selected,'selected_unit_count':len(outrows),'next_translation_tsv':str(next_tsv)},ensure_ascii=False,indent=2))
