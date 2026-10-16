import importlib.util,struct,json,shutil,hashlib
from pathlib import Path
ROOT=Path.cwd();out=ROOT/'outputs/step097';out.mkdir(exist_ok=True)
s=importlib.util.spec_from_file_location('m','PROJECT_ROOT/bia_stage40i_tools/bia_stage40i_actual_resource_trace.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);_,b=m.load_helpers()
src=Path('PROJECT_ROOT/BIA_STAGE79_COMPILED967_STRUCTURAL_TEST.iso');dst=Path('PROJECT_ROOT/BIA_STEP097_MISSION2_UFONT_TEST.iso');p=['PSP_GAME','USRDIR','SYSTEM','D0_0700_.MDI'];_,blob=b.iso_read_file(src,p);st={x['index']:bytes(x['decoded']) for x in b.parse_mdi(blob)};mu={i:bytearray(d) for i,d in st.items()};base=0x08e03020;stride=0x78000;meta=base+35*stride

def read(a,n):
 i,o=divmod(a-base,stride);assert i in st and o+n<=len(st[i]);return st[i][o:o+n]
def put(o,data):
 assert not any(st[35][o:o+len(data)]),hex(o);mu[35][o:o+len(data)]=data
# Derive coordinates from the actual per-mission RFont records, including its extra characters.
layout=[]
for j in range(878):
 d=st[35][j*24:j*24+24];cp=struct.unpack_from('<H',d)[0]
 if not 0xac00<=cp<=0xd7a3:continue
 u,v,u1,v1=struct.unpack_from('<4f',d,8);x=round(u*128-.5);y=round(v*256-.5)
 assert abs(u*128-(x+.5))<.001 and abs(v*256-(y+.5))<.001
 assert abs((u1-u)*128-17)<.001 and abs((v1-v)*256-16)<.001
 assert 0<=x<=495 and 0<=y<=496;layout.append((cp,x,y))
assert len(layout)==len({cp for cp,x,y in layout})==727
tex=struct.unpack_from('<I',st[35],0xab20)[0];assert tex==0x09a77fb0
clone=bytearray(read(tex,0xf0));w=struct.unpack_from('<I',clone,0x44)[0];struct.pack_into('<5I',clone,0x44,(w&65535)|0x09090000,512,512,512,512);struct.pack_into('<I',clone,0x18,0x09a74150);put(0x17200,clone)
reports=[]
for a,loc in [(0x09a74150,{'textures':0x17000,'buckets':0x18000,'remap':0x19000,'glyphs':0x20000}),(0x08fc3ca0,{'textures':0x25000,'buckets':0x26000,'remap':0x27000,'glyphs':0x29000})]:
 i,o=divmod(a-base,stride);h=read(a,0x64);assert struct.unpack_from('<I',h)[0]==0x08d68be8
 gp,n,cap,tp,tn,tc,rp,rn,rc,bp,bn=struct.unpack_from('<11I',h,0x28);assert n==rn==150 and tn==1 and bn==8
 orig=read(gp,n*20);records=bytearray(orig);pairs=[struct.unpack_from('<iHH',read(rp,rn*8),j*8)[1:] for j in range(rn)];assert len({cp for cp,gi in pairs})==n
 for cp,x,y in layout:
  assert cp not in {c for c,g in pairs};pairs.append((cp,len(records)//20));records.extend(struct.pack('<4IB3x',x,y,17,16,1))
 heads=[-1]*1024;maps=bytearray()
 for j,(cp,gi) in enumerate(pairs):
  buck=cp&1023;maps.extend(struct.pack('<iHH',heads[buck],cp,gi));heads[buck]=j
 for cp,gi in pairs:
  j=heads[cp&1023];seen=set()
  while j>=0:
   assert j not in seen;seen.add(j);nex,key,actual=struct.unpack_from('<iHH',maps,j*8)
   if key==cp:assert actual==gi;break
   j=nex
  else:raise AssertionError(hex(cp))
 for k,data in {'textures':read(tp,4)+struct.pack('<I',meta+0x17200),'buckets':struct.pack('<1024i',*heads),'remap':maps,'glyphs':records}.items():put(loc[k],data)
 total=len(pairs);assert total==877 and bytes(records[:3000])==orig
 vals=[meta+loc['glyphs'],total,total,meta+loc['textures'],2,2,meta+loc['remap'],total,total,meta+loc['buckets'],1024];struct.pack_into('<11I',mu[i],o+0x28,*vals)
 reports.append({'font':hex(a),'stream':i,'offset':hex(o),'old_glyph_count':n,'new_glyph_count':total,'latin_glyphs_preserved':n,'hash_lookup_cases':len(pairs),'metadata':loc})
changed={i:bytes(d) for i,d in mu.items() if bytes(d)!=st[i]};assert set(changed)=={3,26,35};new=b.rebuild_mdi(blob,changed);verify={x['index']:bytes(x['decoded']) for x in b.parse_mdi(new)};assert all(verify[i]==bytes(d) for i,d in mu.items());assert not dst.exists();shutil.copy2(src,dst);b.append_iso_file_and_repoint(dst,p,new);assert b.iso_read_file(dst,p)[1]==new
(out/'patched.mdi').write_bytes(new);(out/'hangul_layout.json').write_text(json.dumps(layout,indent=2))
report={'step':'STEP097','source':str(src),'output':str(dst),'strategy':'Expand actual native UFonts; preserve font selection and original Latin records','fonts':reports,'added_hangul_per_font':727,'shared_atlas':'0x09DF3020','dedicated_texture':hex(meta+0x17200),'texture_dimensions':[512,512],'changed_streams':list(changed),'mdi_roundtrip_verified':True,'iso_readback_verified':True,'prx_changed':False,'runtime_verified':False,'deferred_videos_resumed':False};(out/'build_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(report,ensure_ascii=False))
