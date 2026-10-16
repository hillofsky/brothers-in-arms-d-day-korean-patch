import importlib.util,struct,json,shutil,hashlib
from pathlib import Path
s=importlib.util.spec_from_file_location('m','PROJECT_ROOT/bia_stage40i_tools/bia_stage40i_actual_resource_trace.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);_,b=m.load_helpers()
src=Path('PROJECT_ROOT/BIA_STAGE43A_FIRST_CAMPAIGN_KO_TEST.iso');dst=Path('PROJECT_ROOT/BIA_STAGE43D_CAMPAIGN_UFONT_EXPANSION_TEST.iso');parts=['PSP_GAME','USRDIR','SYSTEM','D0_0130_.MDI'];_,blob=b.iso_read_file(src,parts);st={x['index']:bytes(x['decoded']) for x in b.parse_mdi(blob)};mu={26:bytearray(st[26]),35:bytearray(st[35])};base=0x08e03020;stride=0x78000;meta=base+35*stride;uf=0x59aa0
oldglyphs=st[29][0x6cd60:0x6cd60+150*20];oldmap=st[30][0x3350:0x3350+150*8]
plan=json.loads(Path('PROJECT_ROOT/bia_stage39a_tools/stage39a_font_plan.json').read_text(encoding='utf-8'))['layout'];added=json.loads(Path('outputs/stage43a/new_font_glyphs.json').read_text(encoding='utf-8'));layout=plan+added;assert len(layout)==729
# UFont FFontCharacter ends with one-byte TextureIndex and three padding bytes.
records=bytearray(oldglyphs);pairs=[]
for i in range(150):
 _,cp,gi=struct.unpack_from('<IHH',oldmap,i*8);assert gi<150;pairs.append((cp,gi))
for item in layout:
 index=len(records)//20;records.extend(struct.pack('<4IB3x',item['atlas_x'],item['atlas_y'],17,16,1));pairs.append((item['codepoint'],index))
assert len(records)//20==len(pairs)==879;assert len({cp for cp,gi in pairs})==879
bucket_count=1024;heads=[-1]*bucket_count;maps=bytearray()
for i,(cp,gi) in enumerate(pairs):
 h=cp&(bucket_count-1);maps.extend(struct.pack('<iHH',heads[h],cp,gi));heads[h]=i
locations={'textures':0x17000,'buckets':0x18000,'remap':0x19000,'glyphs':0x20000};payloads={'textures':struct.pack('<II',0x09a8cb30,0x09a8d6d0),'buckets':struct.pack('<1024i',*heads),'remap':maps,'glyphs':records}
for name,data in payloads.items():
 o=locations[name];assert not any(st[35][o:o+len(data)]);mu[35][o:o+len(data)]=data
for off,val in [(0x28,meta+locations['glyphs']),(0x2c,879),(0x30,879),(0x34,meta+locations['textures']),(0x38,2),(0x3c,2),(0x40,meta+locations['remap']),(0x44,879),(0x48,879),(0x4c,meta+locations['buckets']),(0x50,1024)]:struct.pack_into('<I',mu[26],uf+off,val)
# Exercise the same chained hash lookup used by the game's font remap.
for cp,expected in pairs:
 i=heads[cp&1023];seen=set()
 while i>=0:
  assert i not in seen;seen.add(i);next,key,gi=struct.unpack_from('<iHH',maps,i*8)
  if key==cp:assert gi==expected;break
  i=next
 else:raise AssertionError(cp)
assert bytes(records[:3000])==oldglyphs
patched=b.rebuild_mdi(blob,{i:bytes(d) for i,d in mu.items()});decoded={x['index']:bytes(x['decoded']) for x in b.parse_mdi(patched)};assert all(decoded[i]==bytes(d) for i,d in mu.items())
assert not dst.exists();shutil.copy2(src,dst);b.append_iso_file_and_repoint(dst,parts,patched);assert b.iso_read_file(dst,parts)[1]==patched
out=Path('outputs/stage43d');out.mkdir(exist_ok=True)
r={'source':str(src),'test_iso':str(dst),'original_hud_glyphs_preserved':150,'added_hangul_glyphs':729,'total_hud_glyphs':879,'texture_count':2,'textures':['0x09a8cb30','0x09a8d6d0'],'hash_lookup_verified':879,'mdi_readback_verified':True,'iso_readback_verified':True,'utf8_hud_decoder_fixed':False,'runtime_verified':False,'full_campaign_complete':False,'record_layout':'4 signed 32-bit metrics, 1-byte TextureIndex, 3 padding bytes','locations':{k:hex(meta+v) for k,v in locations.items()}}
(out/'ufont_expansion_report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(r))
