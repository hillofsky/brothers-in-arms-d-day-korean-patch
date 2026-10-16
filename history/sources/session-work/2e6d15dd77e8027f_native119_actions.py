import json,struct,importlib.util
from pathlib import Path
s=importlib.util.spec_from_file_location('m','PROJECT_ROOT/bia_stage40i_tools/bia_stage40i_actual_resource_trace.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);_,b=m.load_helpers()
p=Path('outputs/step119/reference_audit.json')
if not p.exists():raise SystemExit('Audit still running')
j=json.loads(p.read_text(encoding='utf-8'));refs=j['refs'];native=0
for name in sorted({x['mdi'] for x in refs}-{'ON_MEMU_O.MDI'}):
 _,blob=b.iso_read_file(Path('PROJECT_ROOT/BIA_STEP118_FONT_GUTTER_TEST.iso'),['PSP_GAME','USRDIR','SYSTEM',name]);st={x['index']:bytes(x['decoded']) for x in b.parse_mdi(blob)}
 def text(i,o):
  if o+12>len(st[i]):return None
  a,n,c=struct.unpack_from('<III',st[i],o);ii,oo=divmod(a-0x8e03020,0x78000)
  if ii not in st or not 1<=n<=100 or c<n or oo+n>len(st[ii]):return None
  try:return st[ii][oo:oo+n-1].decode('utf-8') if st[ii][oo+n-1]==0 else None
  except UnicodeDecodeError:return None
 for r in refs:
  if r['mdi']!=name or r['english']!='press' or r['key_verified']:continue
  i,o=r['stream'],r['offset'];seq=[text(i,o+12*k) for k in range(6)]
  if seq!=['press','tap','release','hold','hold','move']:continue
  for k in range(6):
   rr=next(x for x in refs if x['mdi']==name and x['stream']==i and x['offset']==o+12*k);rr['key_verified']=True;rr['native_action_property_sequence_verified']=True
   if k==4:rr['korean']='길게 누르기'
   native+=1
print('native_action_fields',native);print('unverified HUD',[(r['mdi'],r['stream'],r['offset'],r['english']) for r in refs if not r['key_verified'] and r['english'] in ['Free Look','Checkpoint']][:14]);p.write_text(json.dumps(j,ensure_ascii=False,indent=2),encoding='utf-8')
