import importlib.util,struct,json,shutil,hashlib,csv,re,time
from pathlib import Path
OUT=Path('outputs/step098');OUT.mkdir(exist_ok=True);src=Path('PROJECT_ROOT/BIA_STEP097_MISSION2_UFONT_TEST.iso');dst=Path('PROJECT_ROOT/BIA_STEP098_ALL_CHAPTER_UFONT_TEST.iso');BASE=0x08e03020;STRIDE=0x78000;META=BASE+35*STRIDE;PARTS=['PSP_GAME','USRDIR','SYSTEM']
s=importlib.util.spec_from_file_location('m','PROJECT_ROOT/bia_stage40i_tools/bia_stage40i_actual_resource_trace.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);_,b=m.load_helpers()
inv=json.loads((OUT/'inventory.json').read_text());rows=list(csv.DictReader(Path('PROJECT_ROOT/log/STEP_079/outputs/compiled967_patch_refs.tsv').open(encoding='utf-8-sig'),delimiter='\t'));demand={x['mdi']:{ord(c) for r in rows if r['mdi']==x['mdi'] for c in r['korean']} for x in inv}
assert not dst.exists();source_hash=hashlib.file_digest(src.open('rb'),'sha256').hexdigest();shutil.copy2(src,dst);reports=[]
for item in inv:
 name=item['mdi'];p=PARTS+[name];_,blob=b.iso_read_file(src,p);st={x['index']:bytes(x['decoded']) for x in b.parse_mdi(blob)};mu={i:bytearray(d) for i,d in st.items()};native=[f for f in item['fonts'] if f['glyph_count']!=11];assert len(native)==2
 def read(a,n,streams=st):
  i,o=divmod(a-BASE,STRIDE);assert i in streams and 0<=o and o+n<=len(streams[i]),(name,hex(a),n);return streams[i][o:o+n]
 def put(o,data):
  assert not any(st[35][o:o+len(data)]),(name,hex(o));mu[35][o:o+len(data)]=data
 def verify_font(a,streams):
  h=read(a,0x64,streams);gp,n,cap,tp,tn,tc,rp,rn,rc,bp,bn=struct.unpack_from('<11I',h,0x28);assert n==cap==rn==rc;assert bn==1024 and tn==tc==2
  records=read(gp,n*20,streams);maps=read(rp,n*8,streams);heads=struct.unpack('<1024i',read(bp,4096,streams));pairs=[struct.unpack_from('<iHH',maps,j*8)[1:] for j in range(n)];assert len({cp for cp,gi in pairs})==n
  for cp,expected in pairs:
   j=heads[cp&1023];seen=set()
   while j>=0:
    assert j<n and j not in seen;seen.add(j);nex,key,gi=struct.unpack_from('<iHH',maps,j*8)
    if key==cp:assert gi==expected and gi<n;break
    j=nex
   else:raise AssertionError((name,hex(a),hex(cp)))
  missing=demand[name]-{cp for cp,gi in pairs};assert not missing,(name,'missing required text',missing)
  for j in range(150,n):
   x,y,w,h,ti=struct.unpack_from('<4IB3x',records,j*20);assert ti==1 and w==17 and h==16 and x+w<=512 and y+h<=512
  return {'font':hex(a),'glyph_count':n,'hash_lookup_cases':n,'translated_codepoints_checked':len(demand[name]),'missing_translated_codepoints':0}
 if all(f['glyph_count']>150 for f in native):
  verified=[verify_font(int(f['runtime'],16),st) for f in native];assert b.iso_read_file(dst,p)[1]==blob;reports.append({'mdi':name,'action':'PRESERVED_ALREADY_FIXED','fonts':verified,'mdi_sha256':hashlib.sha256(blob).hexdigest()});print('PRESERVED',name,flush=True);continue
 assert all(f['glyph_count']==150 for f in native)
 # Existing per-mission production RFont uses stream35 glyph array and embeds all new Korean cells.
 candidates=[]
 for i,d in st.items():
  for hit in re.finditer(re.escape(struct.pack('<I',META)),d):
   o=hit.start()
   if o%4 or o<4:continue
   count=struct.unpack_from('<H',d,o-4)[0]
   if 847<=count<=907:candidates.append(count)
 assert len(candidates)==2 and len(set(candidates))==1,(name,candidates);rcount=candidates[0];layout=[]
 for j in range(rcount):
  d=st[35][j*24:j*24+24];cp=struct.unpack_from('<H',d)[0]
  if j<151:continue
  assert 0xac00<=cp<=0xd7a3 or cp in (0x2018,0x2019),(name,hex(cp))
  u,v,u1,v1=struct.unpack_from('<4f',d,8);x=round(u*128-.5);y=round(v*256-.5);assert abs(u*128-(x+.5))<.001 and abs(v*256-(y+.5))<.001;assert abs((u1-u)*128-17)<.001 and abs((v1-v)*256-16)<.001;assert 0<=x<=495 and 0<=y<=496;layout.append((cp,x,y))
 # Include per-mission curly quote cells as well as Hangul. Their absence in the
 # native map would otherwise leave a fallback glyph in translated quotations.
 assert 696<=len(layout)<=756 and len({cp for cp,x,y in layout})==len(layout)
 tex=struct.unpack_from('<I',st[35],0xab20)[0];clone=bytearray(read(tex,0xf0));assert struct.unpack_from('<4I',clone,0x48)==(128,256,128,256),(name,'texture shape',hex(tex));w=struct.unpack_from('<I',clone,0x44)[0];struct.pack_into('<5I',clone,0x44,(w&65535)|0x09090000,512,512,512,512);struct.pack_into('<I',clone,0x18,int(native[1]['runtime'],16));put(0x17200,clone)
 bounds=[]
 for f,loc in zip(native,[{'textures':0x17000,'buckets':0x18000,'remap':0x19000,'glyphs':0x20000},{'textures':0x25000,'buckets':0x26000,'remap':0x27000,'glyphs':0x29000}]):
  a=int(f['runtime'],16);i,o=divmod(a-BASE,STRIDE);h=read(a,0x64);gp,n,cap,tp,tn,tc,rp,rn,rc,bp,bn=struct.unpack_from('<11I',h,0x28);assert n==rn==150 and bn==8 and tn==1;orig=read(gp,n*20);records=bytearray(orig);pairs=[struct.unpack_from('<iHH',read(rp,rn*8),j*8)[1:] for j in range(rn)];oldcps={cp for cp,gi in pairs};assert len(oldcps)==150
  for cp,x,y in layout:
   assert cp not in oldcps;pairs.append((cp,len(records)//20));records.extend(struct.pack('<4IB3x',x,y,17,16,1))
  heads=[-1]*1024;maps=bytearray()
  for j,(cp,gi) in enumerate(pairs):
   buck=cp&1023;maps.extend(struct.pack('<iHH',heads[buck],cp,gi));heads[buck]=j
  for k,data in {'textures':read(tp,4)+struct.pack('<I',META+0x17200),'buckets':struct.pack('<1024i',*heads),'remap':maps,'glyphs':records}.items():put(loc[k],data)
  total=len(pairs);assert total==150+len(layout) and records[:3000]==orig;vals=[META+loc['glyphs'],total,total,META+loc['textures'],2,2,META+loc['remap'],total,total,META+loc['buckets'],1024];struct.pack_into('<11I',mu[i],o+0x28,*vals);bounds.append((i,o))
 temp={i:bytes(d) for i,d in mu.items()};vf=[verify_font(int(f['runtime'],16),temp) for f in native];changed={i:temp[i] for i in st if temp[i]!=st[i]};assert set(changed)=={35}|{i for i,o in bounds};assert temp[34]==st[34] and temp[35][:0x17000]==st[35][:0x17000]
 for i in set(changed)-{35}:
  expected=bytearray(st[i])
  for si,o in bounds:
   if si==i:expected[o+0x28:o+0x54]=temp[i][o+0x28:o+0x54]
  assert bytes(expected)==temp[i]
 new=b.rebuild_mdi(blob,changed);decoded={x['index']:bytes(x['decoded']) for x in b.parse_mdi(new)};assert all(decoded[i]==temp[i] for i in st);b.append_iso_file_and_repoint(dst,p,new);assert b.iso_read_file(dst,p)[1]==new
 reports.append({'mdi':name,'action':'NATIVE_UFONT_EXPANDED','rfont_count':rcount,'unicode_glyphs_added_per_font':len(layout),'hangul_added_per_font':sum(0xac00<=cp<=0xd7a3 for cp,x,y in layout),'curly_quotes_added_per_font':sum(cp in (0x2018,0x2019) for cp,x,y in layout),'fonts':vf,'changed_streams':sorted(changed),'texture_clone':hex(META+0x17200),'mdi_sha256':hashlib.sha256(new).hexdigest(),'original_strings_and_atlas_and_latin_and_icons_preserved':True});print('APPLIED',name,len(layout),'Unicode glyphs/font',flush=True)
(OUT/'maps_report.json').write_text(json.dumps(reports,ensure_ascii=False,indent=2),encoding='utf-8');assert len(reports)==32;assert sum(x['action']=='NATIVE_UFONT_EXPANDED' for x in reports)==30
unchanged=[]
for f in ['BIAOFF.PRX','BIAON.PRX','ON_MEMU_O.MDI','ON_MEMU.DSL','ON_MEMU.DSX']:
 a=b.iso_read_file(src,PARTS+[f])[1];z=b.iso_read_file(dst,PARTS+[f])[1];assert a==z;unchanged.append(f)
for x in inv:
 for ext in ['DSL','DSX']:
  f=x['mdi'][:-4]+'.'+ext;a=b.iso_read_file(src,PARTS+[f])[1];z=b.iso_read_file(dst,PARTS+[f])[1];assert a==z;unchanged.append(f)
assert hashlib.file_digest(src.open('rb'),'sha256').hexdigest()==source_hash
summary={'step':'STEP098','output_iso':str(dst),'source_iso':str(src),'source_sha256':source_hash,'source_preserved':True,'output_sha256':hashlib.file_digest(dst.open('rb'),'sha256').hexdigest(),'map_resources':32,'campaign_map_resources':20,'skirmish_map_resources':12,'newly_expanded_resources':30,'already_fixed_resources_preserved':['D0_0130_.MDI','D0_0700_.MDI'],'native_fonts_total':64,'newly_expanded_native_fonts':60,'all_native_unicode_lookup_checks':sum(f['hash_lookup_cases'] for r in reports for f in r['fonts']),'per_map_translated_codepoint_coverage_complete':True,'original_atlas_pixels_and_latin_and_icons_preserved':True,'unchanged_files':unchanged,'prx_unchanged':True,'runtime_scope':'Chapter2 was visually verified in STEP097; all32 map resources statically verified, not all chapters played','all_chapters_runtime_verified':False,'deferred_videos_resumed':False};(OUT/'build_report.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8');print('BUILD COMPLETE',dst,flush=True)
