import importlib.util,struct,json,shutil
from pathlib import Path
s=importlib.util.spec_from_file_location('m','PROJECT_ROOT/bia_stage40i_tools/bia_stage40i_actual_resource_trace.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);_,b=m.load_helpers()
src=Path('PROJECT_ROOT/BIA_STAGE43G_CAMPAIGN_TEXTURE_SIZE_TEST.iso');dst=Path('PROJECT_ROOT/BIA_STAGE43H_CAMPAIGN_ALL_TEXT_FONTS_TEST.iso');p=['PSP_GAME','USRDIR','SYSTEM','D0_0130_.MDI'];_,blob=b.iso_read_file(src,p);st={x['index']:bytes(x['decoded']) for x in b.parse_mdi(blob)};base=0x08e03020;stride=0x78000;meta=base+35*stride;off=0x58c80
header=st[3][off:off+0x58]
def read(a,n):
 i,o=divmod(a-base,stride);return st[i][o:o+n]
gp,count,cap,tp,tc,tcap,rp,rc,rcap,bp,bc=struct.unpack_from('<11I',header,0x28);assert count==rc==150 and tc==1
records=bytearray(read(gp,count*20));pairs=[struct.unpack_from('<iHH',read(rp,rc*8),i*8)[1:] for i in range(rc)]
layout=json.loads(Path('PROJECT_ROOT/bia_stage39a_tools/stage39a_font_plan.json').read_text(encoding='utf-8'))['layout']+json.loads(Path('outputs/stage43a/new_font_glyphs.json').read_text(encoding='utf-8'))
for it in layout:
 pairs.append((it['codepoint'],len(records)//20));records.extend(struct.pack('<4IB3x',it['atlas_x'],it['atlas_y'],17,16,1))
heads=[-1]*1024;maps=bytearray()
for i,(cp,gi) in enumerate(pairs):
 h=cp&1023;maps.extend(struct.pack('<iHH',heads[h],cp,gi));heads[h]=i
loc={'textures':0x25000,'buckets':0x26000,'remap':0x27000,'glyphs':0x29000};payload={'textures':read(tp,4)+struct.pack('<I',meta+0x17200),'buckets':struct.pack('<1024i',*heads),'remap':maps,'glyphs':records};mu={3:bytearray(st[3]),35:bytearray(st[35])}
for k,data in payload.items():
 o=loc[k];assert not any(mu[35][o:o+len(data)]);mu[35][o:o+len(data)]=data
vals=[meta+loc['glyphs'],879,879,meta+loc['textures'],2,2,meta+loc['remap'],879,879,meta+loc['buckets'],1024];struct.pack_into('<11I',mu[3],off+0x28,*vals)
for cp,expected in pairs:
 i=heads[cp&1023]
 while i>=0:
  nex,key,gi=struct.unpack_from('<iHH',maps,i*8)
  if key==cp:assert gi==expected;break
  i=nex
 else:raise AssertionError(cp)
new=b.rebuild_mdi(blob,{i:bytes(d) for i,d in mu.items()});assert not dst.exists();shutil.copy2(src,dst);b.append_iso_file_and_repoint(dst,p,new);assert b.iso_read_file(dst,p)[1]==new
out=Path('outputs/stage43h');out.mkdir(exist_ok=True)
for k,data in payload.items():(out/(k+'.bin')).write_bytes(data)
(out/'header.bin').write_bytes(mu[3][off+0x28:off+0x54])
r={'test_iso':str(dst),'font':'0x08fc3ca0','glyph_count':879,'hangul_added':729,'original_latin_preserved':150,'lookup_checks':879,'iso_readback_verified':True,'runtime_verified':False,'addresses':{k:hex(meta+v) for k,v in loc.items()}}
(out/'font_report.json').write_text(json.dumps(r,indent=2));print(json.dumps(r))
