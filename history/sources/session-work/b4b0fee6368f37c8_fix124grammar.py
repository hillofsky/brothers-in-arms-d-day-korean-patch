exec(open('work/disasm124.py',encoding='utf-8-sig').read().split("_,d=b.iso_read_file")[0]);import json
iso=Path('PROJECT_ROOT/BIA_STEP124_TEXT_REVIEW_KO_TEST.iso');o=Path('outputs/step124');audit=json.loads((o/'reference_audit.json').read_text(encoding='utf-8'));fix={}
for r in audit['refs']:
 if not r['key_verified']:continue
 old=r['korean'];new=old.replace('맥 중사이','맥 중사가').replace('맥 중사은','맥 중사는')
 if new!=old:fix[old]=new;r['korean']=new
for name in {r['mdi'] for r in audit['refs'] if r['key_verified'] and any(v==r['korean'] for v in fix.values())}:
 _,blob=b.iso_read_file(iso,['PSP_GAME','USRDIR','SYSTEM',name]);st={x['index']:bytearray(x['decoded']) for x in b.parse_mdi(blob)};changed=set()
 for r in audit['refs']:
  if r['mdi']!=name or not r['key_verified'] or r['korean'] not in fix.values():continue
  ptr,n,_=struct.unpack_from('<III',st[r['stream']],r['offset']);i,p=divmod(ptr-(0x8e2d020 if name=='ON_MEMU_O.MDI' else 0x8e03020),0x78000);old=next(k for k,v in fix.items() if v==r['korean']);assert st[i][p:p+n]==old.encode()+b'\0';new=r['korean'].encode()+b'\0';assert len(new)==n;st[i][p:p+n]=new;changed.add(i)
 b.append_iso_file_and_repoint(iso,['PSP_GAME','USRDIR','SYSTEM',name],b.rebuild_mdi(blob,{i:bytes(st[i]) for i in changed}))
for k,v in list(audit['targets'].items()):audit['targets'][k]=v.replace('맥 중사이','맥 중사가').replace('맥 중사은','맥 중사는')
(o/'reference_audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8');(o/'translations.json').write_text(json.dumps(audit['targets'],ensure_ascii=False,indent=2),encoding='utf-8')
rec=b.iso_find_record(iso,['PSP_GAME','USRDIR','SYSTEM'])
with iso.open('rb') as f:names=[r['name'] for r in b.iso_list_dir(f,rec['extent'],rec['size']) if r['name'].endswith('.INT')]
for name in names:
 _,old=b.iso_read_file(iso,['PSP_GAME','USRDIR','SYSTEM',name]);new=old
 for a,z in fix.items():new=new.replace(a.encode(),z.encode())
 if new!=old:b.overwrite_iso_same_size(iso,['PSP_GAME','USRDIR','SYSTEM',name],new)
# Movie line gap 3 -> 1 keeps three enlarged lines within original 49px subtitle band.
sig=bytes.fromhex('0000488c0000a48f4000a58c0000850040000000') if False else None
for parts,at in [(['PSP_GAME','USRDIR','SYSTEM','BIAOFF.PRX'],0x13a950+0x80),(['PSP_GAME','USRDIR','SYSTEM','BIAON.PRX'],None),(['PSP_GAME','SYSDIR','BOOT.BIN'],None)]:
 _,old=b.iso_read_file(iso,parts)
 if at is not None:signature=old[at-12:at+12];assert struct.unpack_from('<I',old,at)[0]==0x24840003
 else:
  matches=[h.start()+12 for h in __import__('re').finditer(__import__('re').escape(signature),old)];assert len(matches)==1,(parts,matches);at=matches[0]
 new=bytearray(old);struct.pack_into('<I',new,at,0x24840001);b.overwrite_iso_same_size(iso,parts,bytes(new));assert b.iso_read_file(iso,parts)[1]==new;print('MOVIE LINE GAP',parts[-1],hex(at))
print('grammar corrections',len(fix))
