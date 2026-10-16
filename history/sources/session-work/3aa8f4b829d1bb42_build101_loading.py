import importlib.util,struct,json,shutil,hashlib,collections
from pathlib import Path
s=importlib.util.spec_from_file_location('m','PROJECT_ROOT/bia_stage40i_tools/bia_stage40i_actual_resource_trace.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);_,b=m.load_helpers();src=Path('PROJECT_ROOT/BIA_STEP099_COMPLETION_SAVE_KO_TEST.iso');dst=Path('PROJECT_ROOT/BIA_STEP101_SAVE_LOADING_KO_TEST.iso');out=Path('outputs/step101');audit=json.loads((out/'reference_audit.json').read_text(encoding='utf-8'));refs=[r for r in audit['refs'] if r['key_verified']];group=collections.defaultdict(list)
for r in refs:group[r['mdi']].append(r)
assert not dst.exists();sourcehash=hashlib.file_digest(src.open('rb'),'sha256').hexdigest();shutil.copy2(src,dst);reports=[];fontinv=json.loads(Path('outputs/step098/inventory.json').read_text());fontmap={r['mdi']:[f for f in r['fonts'] if f['glyph_count']!=11] for r in fontinv}
for name,rr in group.items():
 base=0x08e2d020 if name=='ON_MEMU_O.MDI' else 0x08e03020;stride=0x78000;_,blob=b.iso_read_file(src,['PSP_GAME','USRDIR','SYSTEM',name]);st={x['index']:bytes(x['decoded']) for x in b.parse_mdi(blob)};mu={i:bytearray(d) for i,d in st.items()};cursor=0x32000;cache={}
 def read(a,n):
  i,o=divmod(a-base,stride);assert i in st and o+n<=len(st[i]);return st[i][o:o+n]
 needed={ord(c) for r in rr for c in r['korean']}
 for f in fontmap[name]:
  a=int(f['runtime'],16);rp,rn=struct.unpack_from('<II',read(a,0x64),0x40);cps={struct.unpack_from('<H',read(rp,rn*8),j*8+4)[0] for j in range(rn)};assert needed<=cps,(name,'missing UI glyphs',needed-cps)
 for r in rr:
  en,ko=r['english'],r['korean'];i,o=r['stream'],r['offset'];assert struct.unpack_from('<II',st[i],o)==(r['old_ptr'],r['old_n'])
  assert read(r['old_ptr'],r['old_n'])==en.encode('latin1')+b'\0'
  if ko not in cache:
   payload=ko.encode()+b'\0';assert not any(st[35][cursor:cursor+len(payload)]);mu[35][cursor:cursor+len(payload)]=payload;cache[ko]=(base+35*stride+cursor,len(payload));cursor=(cursor+len(payload)+3)&~3
  ptr,n=cache[ko];struct.pack_into('<III',mu[i],o,ptr,n,n)
 changed={i:bytes(d) for i,d in mu.items() if bytes(d)!=st[i]};new=b.rebuild_mdi(blob,changed);decoded={x['index']:bytes(x['decoded']) for x in b.parse_mdi(new)};assert all(decoded[i]==bytes(mu[i]) for i in st)
 # Apart from selected value FStrings and previously-empty payload space, preserve every byte.
 for i in changed:
  expected=bytearray(st[i])
  if i==35:expected[0x32000:cursor]=mu[i][0x32000:cursor]
  for r in rr:
   if r['stream']==i:expected[r['offset']:r['offset']+12]=mu[i][r['offset']:r['offset']+12]
  assert expected==mu[i]
 b.append_iso_file_and_repoint(dst,['PSP_GAME','USRDIR','SYSTEM',name],new);assert b.iso_read_file(dst,['PSP_GAME','USRDIR','SYSTEM',name])[1]==new
 reports.append({'mdi':name,'value_refs_patched':len(rr),'unique_translations':len(cache),'changed_streams':sorted(changed),'payload_end':hex(cursor),'mdi_sha256':hashlib.sha256(new).hexdigest(),'all_original_keys_font_data_and_atlas_preserved':True});print('APPLIED',name,len(rr),'UI values',flush=True)
# Translate external MemoryStick localization consumed by the boot dialog.
int_updates={
'LOAD_PROFILE':'최근 저장 데이터를 불러오는 중입니다. 메모리 스틱을 제거하지 마십시오.',
'CHECKING_MEMORYSTICK':'메모리 스틱을 확인하는 중입니다. 메모리 스틱을 제거하지 마십시오.',
'SAVE_FAILED':'다시 시도하시겠습니까?',
'CONTINUE_WITHOUT_SAVING':'저장하지 않고 계속하시겠습니까?',
'M_LOADERROR':'불러오기에 실패했습니다. 다시 시도하시겠습니까?',
'M_DATACORRUPTED':'불러오기에 실패했습니다. 저장 데이터가 손상되었을 수 있습니다. 다시 시도하시겠습니까?'}
_,original=b.iso_read_file(src,['PSP_GAME','USRDIR','SYSTEM','MEMORYSTICK.INT'])
lines=original.splitlines(keepends=True); changedkeys=[]
for j,line in enumerate(lines):
 key=line.split(b'=',1)[0].decode('ascii',errors='ignore')
 if key in int_updates:
  lines[j]=key.encode()+b'='+int_updates[key].encode('utf-8')+b'\r\n';changedkeys.append(key)
newint=b''.join(lines);b.append_iso_file_and_repoint(dst,['PSP_GAME','USRDIR','SYSTEM','MEMORYSTICK.INT'],newint)
assert b.iso_read_file(dst,['PSP_GAME','USRDIR','SYSTEM','MEMORYSTICK.INT'])[1]==newint
# Preserve all earlier font/PRX/DSL fixes; original key and source English bytes stay in place.
for f in ['BIAOFF.PRX','BIAON.PRX','ON_MEMU_O.MDI','ON_MEMU.DSL','ON_MEMU.DSX']:
 a=b.iso_read_file(src,['PSP_GAME','USRDIR','SYSTEM',f])[1];z=b.iso_read_file(dst,['PSP_GAME','USRDIR','SYSTEM',f])[1];assert a==z
assert hashlib.file_digest(src.open('rb'),'sha256').hexdigest()==sourcehash
report={'step':'STEP101','source':str(src),'output':str(dst),'source_sha256':sourcehash,'source_preserved':True,'output_sha256':hashlib.file_digest(dst.open('rb'),'sha256').hexdigest(),'external_int_translations':int_updates,'external_int_keys_updated':changedkeys,'translations':audit['targets'],'maps_patched':len(reports),'value_refs_patched':len(refs),'key_metadata_preserved':True,'font_and_atlas_and_prx_preserved':True,'all_new_ui_glyphs_available':True,'mdi_and_iso_readback_verified':True,'runtime_visually_verified':False,'maps':reports};(out/'build_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print('DONE',dst,flush=True)
