exec(open('work/analyze112_hang.py',encoding='utf-8-sig').read().split('md=Cs')[0])
import re
_,d=b.iso_read_file(Path('PROJECT_ROOT/BIA_STEP116_TUTORIAL_CHARACTER_NAMES_KO_TEST.iso'),['PSP_GAME','USRDIR','SYSTEM','D0_0130_.MDI']);st={x['index']:bytes(x['decoded']) for x in b.parse_mdi(d)}
for i,d in st.items():
 for h in re.finditer(rb'[A-Za-z0-9_./]{5,}',d):
  if any(x in h.group().lower() for x in [b'stance',b'compass',b'posture',b'crouch',b'planting']):print(i,hex(h.start()),h.group().decode())
