exec(open('work/analyze112_hang.py',encoding='utf-8-sig').read().split('md=Cs')[0])
_,blob=b.iso_read_file(Path('PROJECT_ROOT/BIA_STEP118_FONT_GUTTER_TEST.iso'),['PSP_GAME','USRDIR','SYSTEM','D0_0130_.MDI']);st={x['index']:bytes(x['decoded']) for x in b.parse_mdi(blob)}
for en in [b'Press',b'Hold']:
 for i,d in st.items():
  pos=0
  while True:
   p=d.find(en+b'\0',pos)
   if p<0:break
   pos=p+1;print(en,i,hex(p),repr(d[max(0,p-35):p+70]))
