import importlib.util,struct,json,csv,collections
from pathlib import Path
sp=importlib.util.spec_from_file_location('m',r'PROJECT_ROOT\bia_stage40i_tools\bia_stage40i_actual_resource_trace.py');m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);_,b=m.load_helpers()
source=Path(r'PROJECT_ROOT\BIA_STAGE43M_CAMPAIGN_OBJECTIVE_UTF8_TEST.iso');parts=['PSP_GAME','USRDIR','SYSTEM'];_,blob=b.iso_read_file(source,parts+['D0_0130_.MDI']);st={x['index']:bytes(x['decoded']) for x in b.parse_mdi(blob)};base=0x08E03020;stride=0x78000
rows=[{'id':'GBXHUD-NEW-OBJECTIVE','English':'New Objective'}];mapping={x['English']:x for x in rows};keys=set()
for p in Path(r'PROJECT_ROOT\extracted\PSP_GAME\USRDIR\SYSTEM').glob('*.INT'):
 for line in p.read_bytes().decode('utf-8-sig',errors='replace').splitlines():
  if '=' in line:keys.add(line.split('=',1)[0].strip())
def text(ptr,n,cap):
 if not(base<=ptr<base+len(st)*stride and 1<=n<=4096 and n<=cap<=0x100000):return None
 i=(ptr-base)//stride;o=(ptr-base)%stride
 if i not in st:return None
 raw=st[i][o:o+n]
 if len(raw)!=n or raw[-1:]!=b'\0':return None
 for enc in ['utf-8','cp1252']:
  try:return raw[:-1].decode(enc)
  except UnicodeDecodeError:pass
 return None
refs=[];found=collections.Counter()
for i,d in st.items():
 for off in range(12,len(d)-11,4):
  value=text(*struct.unpack_from('<III',d,off))
  if value not in mapping:continue
  row=mapping[value];key=text(*struct.unpack_from('<III',d,off-12));following=text(*struct.unpack_from('<III',d,off+12)) if off+24<=len(d) else None
  valid=key in keys
  refs.append({'id':row['id'],'english':value,'stream':i,'offset':hex(off),'key':key,'key_verified':valid,'next_fstring':following})
  if valid:found[row['id']]+=1
report={'refs':refs,'covered':len(found),'units':len(rows),'by_stream':dict(collections.Counter(x['stream'] for x in refs if x['key_verified'])),'missing':[{'id':x['id'],'english':x['English']} for x in rows if x['id'] not in found]}
Path('work/popup_title_reference_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in report.items() if k not in ['refs','missing']}));print(json.dumps(report['missing'][:8],ensure_ascii=True))
