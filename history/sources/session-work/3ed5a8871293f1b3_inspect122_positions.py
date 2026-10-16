exec(open('work/analyze112_hang.py',encoding='utf-8-sig').read().split('md=Cs')[0])
_,blob=b.iso_read_file(Path('PROJECT_ROOT/BIA_STEP116_TUTORIAL_CHARACTER_NAMES_KO_TEST.iso'),['PSP_GAME','USRDIR','SYSTEM','SKR_US_BROK.MDI']);st={x['index']:bytes(x['decoded']) for x in b.parse_mdi(blob)}
for ch in '현재게임을종료하고메인뉴로돌아갑니다계속하시겠습니까아니오':
 for j in range(151,848):
  off=j*24;cp=struct.unpack_from('<H',st[35],off)[0]
  if cp==ord(ch):
   u,v,u1,v1=struct.unpack_from('<4f',st[35],off+8);print(ascii(ch),round(u*128-.5),round(v*256-.5));break
