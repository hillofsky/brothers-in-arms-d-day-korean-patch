exec(open('work/disasm124.py',encoding='utf-8-sig').read().split("_,d=b.iso_read_file")[0])
_,blob=b.iso_read_file(iso,['PSP_GAME','USRDIR','SYSTEM','D0_0130_.MDI']);st={x['index']:bytes(x['decoded']) for x in b.parse_mdi(blob)};base=0x8e03020
for i,d in st.items():
 start=0
 while True:
  p=d.find(b'German P38',start)
  if p<0:break
  start=p+1;ptr=base+i*0x78000+p;print('TEXT',i,hex(p),repr(d[p-10:p+65]),hex(ptr))
  for j,s in st.items():
   q=0
   while True:
    q=s.find(struct.pack('<I',ptr),q)
    if q<0:break
    print('REF',j,hex(q),s[q-12:q+24].hex());q+=4
