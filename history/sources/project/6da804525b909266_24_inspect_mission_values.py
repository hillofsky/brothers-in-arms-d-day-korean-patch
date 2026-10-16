exec(open('work/match_off.py',encoding='utf-8-sig').read().split('for name,va')[0])
_,blob=b.iso_read_file(iso,['PSP_GAME','USRDIR','SYSTEM','D0_0130_.MDI']);sts={x['index']:bytes(x['decoded']) for x in b.parse_mdi(blob)};seq=0x08e03020;stride=0x78000
for font in []:
 si=(font-seq)//stride;po=(font-seq)%stride;dec=sts[si];p=struct.unpack_from('<I',dec,po+0x488)[0];psi=(p-seq)//stride;ppo=(p-seq)%stride;tex=struct.unpack_from('<I',sts[psi],ppo)[0];tsi=(tex-seq)//stride;tpo=(tex-seq)%stride;print('font',hex(font),'texture',hex(tex),'record:',sts[tsi][tpo:tpo+0x130].hex())
for text in ['Pause','Resume Chapter','Rendezvous with Destiny']:
 for si,dec in sts.items():
  pos=dec.find(text.encode()+b'\0')
  if pos<0:continue
  pointer=seq+si*stride+pos;needle=struct.pack('<I',pointer)
  for mi,data in sts.items():
   p=data.find(needle)
   while p>=0:
    if p%4==0 and struct.unpack_from('<I',data,p+4)[0]==len(text)+1:print(text,si,hex(pos),'metadata',mi,hex(p),'context',data[p-24:p+36].hex())
    p=data.find(needle,p+1)


