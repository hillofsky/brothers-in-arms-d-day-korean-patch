exec(open('work/audit101_loading.py',encoding='utf-8').read().split('allrefs=[]')[0])
for name in ['ON_MEMU_O.MDI','D1_0900_.MDI']:
 _,blob=b.iso_read_file(src,['PSP_GAME','USRDIR','SYSTEM',name])
 for e in b.parse_mdi(blob):
  d=bytes(e['decoded'])
  for term in [b'Loading your',b'Checking Memory']:
   pos=d.find(term)
   if pos>=0:print(name,e['index'],hex(pos),repr(d[pos:pos+150]))
