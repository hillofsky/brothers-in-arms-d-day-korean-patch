exec(open('work/weapon124inspect.py',encoding='utf-8-sig').read().split('for i,d')[0]);import re
for i,d in st.items():
 for h in re.finditer(re.escape(struct.pack('<I',base+35*0x78000)),d):
  p=h.start();
  if p%4 or p<0x54:continue
  n=struct.unpack_from('<H',d,p-4)[0]
  if 847<=n<920:print('FONT',i,hex(p-0x54),d[p-0x54:p-0x54+0x58].hex())
