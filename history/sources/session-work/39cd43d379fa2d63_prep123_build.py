from pathlib import Path
s=Path('work/build120.py').read_text(encoding='utf-8-sig').replace('BIA_STEP119_ACTION_FREELOOK_CHECKPOINT_KO_TEST.iso','BIA_STEP120_MAC_NAME_KO_TEST.iso').replace("dst=Path('PROJECT_ROOT/BIA_STEP120_MAC_NAME_KO_TEST.iso')","dst=Path('PROJECT_ROOT/BIA_STEP123_SKIRMISH_KO_TEST.iso')").replace('outputs/step120','outputs/step123').replace('0x58000','0x5a000').replace("'STEP120'","'STEP123'")
s=s.replace("for name,rr in group.items():","fontmap['ON_MEMU_O.MDI']=[]\nfor name,rr in group.items():").replace('cursor=0x5a000;','cursor=0x6000 if name==\'ON_MEMU_O.MDI\' else 0x5a000;').replace('expected[0x5a000:cursor]=mu[i][0x5a000:cursor]','expected[(0x6000 if name==\'ON_MEMU_O.MDI\' else 0x5a000):cursor]=mu[i][(0x6000 if name==\'ON_MEMU_O.MDI\' else 0x5a000):cursor]').replace("'BIAON.PRX','ON_MEMU_O.MDI','ON_MEMU.DSL'","'BIAON.PRX','ON_MEMU.DSL'")
Path('work/build123.py').write_text(s,encoding='utf-8')
for old,new in [('work/fallback120.py','work/fallback123.py'),('work/verify120.py','work/verify123.py')]:
 s=Path(old).read_text(encoding='utf-8-sig').replace('BIA_STEP120_MAC_NAME_KO_TEST.iso','BIA_STEP123_SKIRMISH_KO_TEST.iso').replace('outputs/step120','outputs/step123')
 if 'verify' in old:s=s.replace('a-0x8e03020','a-(0x8e2d020 if name==\'ON_MEMU_O.MDI\' else 0x8e03020)')
 Path(new).write_text(s,encoding='utf-8')
