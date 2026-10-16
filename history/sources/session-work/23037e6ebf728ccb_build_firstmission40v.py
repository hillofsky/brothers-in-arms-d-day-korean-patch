import importlib.util,struct,json,shutil,csv,re,hashlib
from pathlib import Path
out=Path('outputs/stage40v');out.mkdir(exist_ok=True)
s=importlib.util.spec_from_file_location('m','PROJECT_ROOT/bia_stage40i_tools/bia_stage40i_actual_resource_trace.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);_,b=m.load_helpers();src=Path('PROJECT_ROOT/BIA_STAGE40R_CAMPAIGN_RENDERER_TEST.iso');dst=Path('PROJECT_ROOT/BIA_STAGE40V_FIRST_MISSION_UI_TEST.iso');parts=['PSP_GAME','USRDIR','SYSTEM'];name='D0_0130_';_,blob=b.iso_read_file(src,parts+[name+'.MDI']);st={x['index']:bytes(x['decoded']) for x in b.parse_mdi(blob)};mu={i:bytearray(d) for i,d in st.items()};seq=0x08e03020;stride=0x78000
assert not any(st[33]) and not any(st[34]) and not any(st[35]);atlasbase=seq+34*stride;metabase=seq+35*stride;textbase=metabase+0xb000
_,menublob=b.iso_read_file(src,b.TARGET_MDI);menu={x['index']:bytes(x['decoded']) for x in b.parse_mdi(menublob)};meta=bytearray(menu[23][:0xa860]);oldmetabase=0x098f5020
# Rebase Unicode pages and font auxiliaries; glyph records have no pointers.
tex=0x09a8d6d0
for j in range(4):struct.pack_into('<I',meta,0xa820+j*4,tex)
mu[35][:len(meta)]=meta;atlas=Path('PROJECT_ROOT/bia_stage39a_tools/stage39a_tmr18_512x512_swizzled.bin').read_bytes();assert len(atlas)==0x20000;mu[34][:len(atlas)]=atlas
font=menu[19][0xe83c:0xe83c+0x490];fonts=[]
for off in [0x7f64,0xa0fc]:
 assert struct.unpack_from('<H',mu[30],off+0x50)[0]==151
 struct.pack_into('<H',mu[30],off+0x50,847);struct.pack_into('<I',mu[30],off+0x54,metabase)
 for hb in range(0xac,0xd8):
  ptr=struct.unpack_from('<I',font,0x58+hb*4)[0]
  if oldmetabase<=ptr<oldmetabase+0xa860:struct.pack_into('<I',mu[30],off+0x58+hb*4,metabase+(ptr-oldmetabase))
 for field in [0x474,0x478,0x488]:
  ptr=struct.unpack_from('<I',font,field)[0];assert oldmetabase<=ptr<oldmetabase+0xa860;struct.pack_into('<I',mu[30],off+field,metabase+ptr-oldmetabase)
 fonts.append({'runtime':hex(seq+30*stride+off),'count':847,'glyph_pointer':hex(metabase)})
# The Latin16 font's exact texture was identified from the runtime texture image and relocation record.
_,dsl=b.iso_read_file(src,parts+[name+'.DSL']);_,dsx=b.iso_read_file(src,parts+[name+'.DSX']);assert b.dsx_logical_bytes(dsx)==dsl;d=bytearray(dsl);entry=(0x40055140,0x80,0x4010e9c0);assert struct.unpack_from('<III',d,0x31e2ae)==entry;newentry=(entry[0],512,(-atlasbase)&0xffffffff);struct.pack_into('<III',d,0x31e2ae,*newentry);assert struct.unpack_from('<I',d,0x4acee4)[0]==0xb8000807;struct.pack_into('<I',d,0x4acee4,0xb8000909)
assert st[0][0x3501c:0x35028] == bytes(12) # Runtime relocation table is populated from DSX, not static MDI.
# Exact FString metadata references only; never change key/property/section identifiers.
rows=list(csv.DictReader(Path('PROJECT_ROOT/bia_stage39a_tools/stage39a_A_translations.tsv').open(encoding='utf-8-sig'),delimiter='\t'));mapping={r['English']:r for r in rows if r['한국어']};keys=set()
for p in Path('PROJECT_ROOT/extracted/PSP_GAME/USRDIR/SYSTEM').glob('*.INT'):
 text=p.read_bytes().decode('utf-8-sig',errors='replace')
 for line in text.splitlines():
  if '=' in line:keys.add(line.split('=',1)[0].strip())
  if line.strip().startswith('['):keys.add(line.strip().strip('[]'))
references={}
for i,dec in st.items():
 for off in range(0,len(dec)-11,4):
  ptr,n,cap=struct.unpack_from('<III',dec,off)
  if seq<=ptr<seq+37*stride and 1<=n<=4096 and n<=cap<=0x100000:references.setdefault((ptr,n),[]).append((i,off))
actions=[];cache={};cursor=0
for i,dec in st.items():
 for match in re.finditer(rb'[\x20-\x7e]{1,4096}\x00',dec):
  english=match.group()[:-1].decode('ascii');row=mapping.get(english)
  if row is None or english in keys:continue
  refs=references.get((seq+i*stride+match.start(),len(match.group())),[])
  filtered=[]
  for ri,ro in refs:
   if ro >= 12:
    kp,kn,kc=struct.unpack_from('<III',st[ri],ro-12)
    ki=(kp-seq)//stride;ko=(kp-seq)%stride
    if ki in st and 1<=kn<=512 and kn<=kc<=0x100000:
     key=st[ki][ko:ko+kn]
     if key.endswith(b'\0') and key[:-1].decode('ascii',errors='replace') in keys:filtered.append((ri,ro))
   if ri==13 and ro==0x5444c and english=='Rendezvous with Destiny':filtered.append((ri,ro))
  refs=list(set(filtered))
  if not refs:continue
  korean=row['한국어'];payload=korean.encode()+b'\0'
  if korean not in cache:
   assert cursor+len(payload)<stride;mu[35][0xb000+cursor:0xb000+cursor+len(payload)]=payload;cache[korean]=(textbase+cursor,len(payload));cursor=(cursor+len(payload)+3)&~3
  ptr,n=cache[korean]
  for ri,ro in refs:
   struct.pack_into('<III',mu[ri],ro,ptr,n,n);actions.append({'id':row['id'],'english':english,'korean':korean,'source_stream':i,'source_offset':hex(match.start()),'metadata_stream':ri,'metadata_offset':hex(ro),'runtime':hex(ptr),'bytes':n})
changed={i:bytes(d) for i,d in mu.items() if bytes(d)!=st[i]};patched=b.rebuild_mdi(blob,changed);verified={x['index']:bytes(x['decoded']) for x in b.parse_mdi(patched)};assert all(verified[i]==bytes(d) for i,d in mu.items());newdsx,_=b.rebuild_dsx_from_logical(dsx,bytes(d));assert b.dsx_logical_bytes(newdsx)==bytes(d)
assert not dst.exists();shutil.copy2(src,dst)
for ext,data in [('MDI',patched),('DSL',bytes(d)),('DSX',newdsx)]:
 path=parts+[name+'.'+ext]
 if ext=='DSL':b.overwrite_iso_same_size(dst,path,data)
 else:b.append_iso_file_and_repoint(dst,path,data)
 assert b.iso_read_file(dst,path)[1]==data
payloads=[{'korean':ko,'runtime':hex(p),'bytes':n} for ko,(p,n) in cache.items()];report={'source':str(src),'test_iso':str(dst),'mission_mdi_base':hex(seq),'font_objects':fonts,'atlas_runtime':hex(atlasbase),'atlas_bytes':len(atlas),'atlas_sha1':hashlib.sha1(atlas).hexdigest(),'font_metadata_runtime':hex(metabase),'font_metadata_bytes':len(meta),'payloads':payloads,'metadata_actions':len(actions),'unique_units':len({x['id'] for x in actions}),'unique_payloads':len(payloads),'changed_streams':list(changed),'DSL_relocation':{'offset':'0x31e2ae','old':[hex(x) for x in entry],'new':[hex(x) for x in newentry],'address_mode':'negative_absolute'},'iso_readback_ok':True,'runtime_verified':False};(out/'first_mission_patch_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');(out/'translation_actions.json').write_text(json.dumps(actions,ensure_ascii=False,indent=2),encoding='utf8');print({k:report[k] for k in ['test_iso','metadata_actions','unique_units','unique_payloads','changed_streams']})

