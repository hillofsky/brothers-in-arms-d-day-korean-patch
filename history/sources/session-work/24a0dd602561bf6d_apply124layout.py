exec(open('work/disasm124.py',encoding='utf-8-sig').read().split("_,d=b.iso_read_file")[0])
import json,hashlib,re
iso=Path('PROJECT_ROOT/BIA_STEP124_TEXT_REVIEW_KO_TEST.iso');out=Path('outputs/step124');layout=json.loads((out/'movie/layout.json').read_text(encoding='utf-8'));reports=[]
for name in sorted({f['file'] for f in layout['fields']}):
 parts=['PSP_GAME','USRDIR','SYSTEM',name];_,old=b.iso_read_file(iso,parts);new=bytearray(old);allowed=set()
 for f in layout['fields']:
  if f['file']!=name:continue
  off=int(f['offset_hex'],16);size=f['field_bytes'];enc=bytes.fromhex(f['encoded_hex']);assert old[off:off+size]==enc.ljust(size-1,b' ')+b'^',(name,f['field_index'])
  repl=bytes.fromhex(f['encoded_new']);new[off:off+size]=repl.ljust(size-1,b' ')+b'^';allowed.update(range(off,off+size-1))
 assert len(new)==len(old) and all(i in allowed for i,(a,z) in enumerate(zip(old,new)) if a!=z)
 b.overwrite_iso_same_size(iso,parts,bytes(new));assert b.iso_read_file(iso,parts)[1]==new;reports.append({'file':name,'timings_control_bytes_preserved':True})
for name in ['SUBTITLEHASHMAP.INI','SUBTITLETEXTURE.RAW']:
 parts=['PSP_GAME','USRDIR','SYSTEM',name];_,old=b.iso_read_file(iso,parts);new=(out/'movie'/name).read_bytes()
 if len(old)==len(new):b.overwrite_iso_same_size(iso,parts,new)
 else:b.append_iso_file_and_repoint(iso,parts,new)
 assert b.iso_read_file(iso,parts)[1]==new;reports.append({'file':name,'size_before':len(old),'size_after':len(new)})
(out/'movie/applied.json').write_text(json.dumps(reports,indent=2))
# Add two source pixels of advance to Hangul only, without changing glyph ink, sprite width or icons.
names=[x['mdi'] for x in json.loads(Path('outputs/step098/maps_report.json').read_text())]+['ON_MEMU_O.MDI'];reports=[]
for name in names:
 base=0x8e2d020 if name=='ON_MEMU_O.MDI' else 0x8e03020;mi=23 if name=='ON_MEMU_O.MDI' else 35;_,blob=b.iso_read_file(iso,['PSP_GAME','USRDIR','SYSTEM',name]);st={x['index']:bytes(x['decoded']) for x in b.parse_mdi(blob)};meta=base+mi*0x78000;counts=[]
 for d in st.values():
  for h in re.finditer(re.escape(struct.pack('<I',meta)),d):
   o=h.start()
   if o>=4 and o%4==0:
    n=struct.unpack_from('<H',d,o-4)[0]
    if 847<=n<=920:counts.append(n)
 assert len(counts)==2 and counts[0]==counts[1],(name,counts);new=bytearray(st[mi]);changed=[]
 for k in range(counts[0]):
  cp=struct.unpack_from('<H',new,k*24)[0]
  if not 0xac00<=cp<=0xd7a3:continue
  assert new[k*24+6]==16,(name,cp,new[k*24+6]);new[k*24+6]=18;changed.append(k*24+6)
 assert all(i in changed for i,(a,z) in enumerate(zip(st[mi],new)) if a!=z)
 rebuilt=b.rebuild_mdi(blob,{mi:bytes(new)});b.append_iso_file_and_repoint(iso,['PSP_GAME','USRDIR','SYSTEM',name],rebuilt);ck={x['index']:bytes(x['decoded']) for x in b.parse_mdi(b.iso_read_file(iso,['PSP_GAME','USRDIR','SYSTEM',name])[1])};assert ck[mi]==new and all(ck[i]==d for i,d in st.items() if i!=mi)
 reports.append({'mdi':name,'hangul_advance_before':16,'hangul_advance_after':18,'glyphs':len(changed),'atlas_and_sprite_bounds_preserved':True});print('SPACING',name,len(changed),flush=True)
(out/'spacing.json').write_text(json.dumps(reports,indent=2));print('FINAL',hashlib.file_digest(iso.open('rb'),'sha256').hexdigest())
