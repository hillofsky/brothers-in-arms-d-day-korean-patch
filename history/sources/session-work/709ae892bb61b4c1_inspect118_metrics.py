exec(open('work/analyze112_hang.py',encoding='utf-8-sig').read().split('md=Cs')[0])
_,blob=b.iso_read_file(Path('PROJECT_ROOT/BIA_STEP117_NEW_OBJECTIVE_KO_TEST.iso'),['PSP_GAME','USRDIR','SYSTEM','ON_MEMU_O.MDI']);st={x['index']:bytes(x['decoded']) for x in b.parse_mdi(blob)}
for j in [1,34,35,78,151,152]:
 v=st[23][j*24:j*24+24];print(j,v.hex(),struct.unpack('<4H4f',v))
