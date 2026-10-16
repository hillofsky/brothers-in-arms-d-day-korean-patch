exec(open('work/analyze112_hang.py',encoding='utf-8-sig').read().split('md=Cs')[0])
import re,struct,json
name='D0_0130_.MDI';ss=[]
for path in ['PROJECT_ROOT/Brothers in Arms - D-Day (USA) (v1.01).iso','PROJECT_ROOT/BIA_STEP116_TUTORIAL_CHARACTER_NAMES_KO_TEST.iso']:
 _,d=b.iso_read_file(Path(path),['PSP_GAME','USRDIR','SYSTEM',name]);ss.append({x['index']:bytes(x['decoded']) for x in b.parse_mdi(d)})
rows=[]
for i,d in ss[1].items():
 for h in re.finditer(re.escape(struct.pack('<I',0x8d70f48)),d):
  o=h.start()
  if o%4 or o+240>len(d):continue
  w,hh=struct.unpack_from('<II',d,o+0x48)
  if w not in [16,32,64,128,256,512] or hh not in [16,32,64,128,256,512]:continue
  original=ss[0].get(i,b'')[o:o+240];changed=original!=d[o:o+240]
  rows.append({'stream':i,'offset':hex(o),'dimensions':[w,hh],'original_header_identical':not changed})
Path('outputs/step117_icon/original_texture_headers.json').write_text(json.dumps(rows,indent=2));print('textures',len(rows),'changed',[x for x in rows if not x['original_header_identical']])
