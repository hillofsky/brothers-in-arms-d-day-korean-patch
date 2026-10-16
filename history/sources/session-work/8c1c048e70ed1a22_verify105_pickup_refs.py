import json,importlib.util,struct
from pathlib import Path
p=Path('outputs/step105/reference_audit.json');j=json.loads(p.read_text(encoding='utf-8'));s=importlib.util.spec_from_file_location('m','PROJECT_ROOT/bia_stage40i_tools/bia_stage40i_actual_resource_trace.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);_,b=m.load_helpers();count=0
for name in {r['mdi'] for r in j['refs'] if 'HandGrenade' in r['english']}:
 _,blob=b.iso_read_file(Path('PROJECT_ROOT/BIA_STEP104_CHECKPOINT_STRING_LIFETIME_TEST.iso'),['PSP_GAME','USRDIR','SYSTEM',name]);st={e['index']:bytes(e['decoded']) for e in b.parse_mdi(blob)}
 for r in j['refs']:
  if r['mdi']!=name or r['english']!='You picked up a HandGrenade.':continue
  ptr,n,cap=struct.unpack_from('<III',st[r['stream']],r['offset']);assert r['stream']!=2 and n==cap==29;i,o=divmod(ptr-0x08e03020,0x78000);assert st[i][o:o+n]==r['english'].encode()+b'\0';r['key_verified']=True;r['verification']='Exact GBXINVENTORY PickupUsableUSHandGrenade.PickupMessage value in aligned FString; sentence is not an identifier';count+=1
p.write_text(json.dumps(j,ensure_ascii=False,indent=2),encoding='utf-8');print('Verified pickup property FStrings',count)
