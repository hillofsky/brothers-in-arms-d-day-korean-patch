import json,importlib.util,struct,collections
from pathlib import Path
s=importlib.util.spec_from_file_location('m','PROJECT_ROOT/bia_stage40i_tools/bia_stage40i_actual_resource_trace.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);_,b=m.load_helpers();out=Path('outputs/step105');r=json.loads((out/'build_report.json').read_text(encoding='utf-8'));a=json.loads((out/'reference_audit.json').read_text(encoding='utf-8'));iso=Path(r['output']);groups=collections.defaultdict(list)
for x in a['refs']:
 if x['key_verified']:groups[x['mdi']].append(x)
checks=[]
for name,rr in groups.items():
 _,blob=b.iso_read_file(iso,['PSP_GAME','USRDIR','SYSTEM',name]);st={x['index']:bytes(x['decoded']) for x in b.parse_mdi(blob)};base=0x08e03020;stride=0x78000
 for x in rr:
  ptr,n,cap=struct.unpack_from('<III',st[x['stream']],x['offset']);i,o=divmod(ptr-base,stride);assert st[i][o:o+n]==x['korean'].encode()+b'\0' and n==cap
 checks.append({'mdi':name,'refs_verified':len(rr),'translations':sorted({x['korean'] for x in rr})})
assert sum(x['refs_verified'] for x in checks)==94;(out/'iso_translation_check.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf-8');print('VERIFIED 94 MORTAR AND PICKUP REFERENCES')
