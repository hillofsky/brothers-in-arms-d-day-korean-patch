import importlib.util,struct,json,re,collections
from pathlib import Path
s=importlib.util.spec_from_file_location('m','PROJECT_ROOT/bia_stage40i_tools/bia_stage40i_actual_resource_trace.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);_,b=m.load_helpers();src=Path('PROJECT_ROOT/BIA_STEP123_SKIRMISH_KO_TEST.iso');names=[x['mdi'] for x in json.loads(Path('outputs/step098/maps_report.json').read_text())]+['ON_MEMU_O.MDI'];targets=json.loads(Path('outputs/step124/translations.json').read_text(encoding='utf-8'));keys=set()
for p in Path('PROJECT_ROOT/extracted/PSP_GAME/USRDIR/SYSTEM').glob('*.INT'):
 for line in p.read_bytes().decode('utf-8-sig',errors='replace').splitlines():
  if '=' in line:keys.add(line.split('=',1)[0].strip())
source_pattern=re.compile(b'(?:'+b'|'.join(re.escape(en.encode()) for en in sorted(targets,key=len,reverse=True))+b')\x00')
allrefs=[]
for name in names:
 base=0x08e2d020 if name=='ON_MEMU_O.MDI' else 0x08e03020;stride=0x78000;_,blob=b.iso_read_file(src,['PSP_GAME','USRDIR','SYSTEM',name]);st={x['index']:bytes(x['decoded']) for x in b.parse_mdi(blob)}
 def text(a,n,cap):
  i,o=divmod(a-base,stride)
  if i not in st or not(1<=n<=4096 and n<=cap<=0x100000) or o+n>len(st[i]):return None
  raw=st[i][o:o+n]
  if raw[-1:]!=b'\0':return None
  try:return raw[:-1].decode('utf-8')
  except UnicodeDecodeError:return None
 sources={}
 for i,d in st.items():
  for h in re.finditer(source_pattern,d):
    en=h.group(0)[:-1].decode('utf-8')
    sources[base+i*stride+h.start()]=en
 refs=[]
 for ptr,en in sources.items():
  sig=struct.pack('<II',ptr,len(en.encode())+1)
  for i,d in st.items():
   for h in re.finditer(re.escape(sig),d):
    o=h.start()
    if i==2 or o%4 or o<12 or o+12>len(d):continue
    a,n,cap=struct.unpack_from('<III',d,o)
    if cap<n:continue
    key=text(*struct.unpack_from('<III',d,o-12));following=text(*struct.unpack_from('<III',d,o+12)) if o+24<=len(d) else None
    valid=key in keys or (' ' in en and '%s' not in en) # Display phrase or verified localized key
    if en in keys and following is not None:valid=False
    refs.append({'mdi':name,'stream':i,'offset':o,'english':en,'korean':targets[en],'key':key,'next_fstring':following,'key_verified':valid,'old_ptr':ptr,'old_n':n})
 allrefs.extend(refs);print(name,len([x for x in refs if x['key_verified']]),'English dialogue references',flush=True)
out=Path('outputs/step124');out.mkdir(exist_ok=True);(out/'reference_audit.json').write_text(json.dumps({'targets':targets,'refs':allrefs},ensure_ascii=False,indent=2),encoding='utf-8');print('VALID',sum(x['key_verified'] for x in allrefs))

