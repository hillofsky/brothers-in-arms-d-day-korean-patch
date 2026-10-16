exec(open('work/match_off.py',encoding='utf-8-sig').read().split('for name,va')[0])
for name in ['D0_0130_.MDI','ON_MEMU_O.MDI']:
 _,blob=b.iso_read_file(iso,['PSP_GAME','USRDIR','SYSTEM',name]);st=b.parse_mdi(blob);print(name,len(st))
 for x in st:
  dec=bytes(x['decoded']);p=dec.find(b'Rendezvous with Destiny\0')
  if p>=0:print('title',x['index'],hex(p))
  for p in range(0,len(dec)-0x480,4):
   if struct.unpack_from('<H',dec,p+0x50)[0]==151 and sum(bool(v) for v in struct.unpack_from('<256I',dec,p+0x58)) in range(1,15):
    ptr=struct.unpack_from('<I',dec,p+0x54)[0]
    if ptr:print('possiblefont',x['index'],hex(p),hex(ptr))
