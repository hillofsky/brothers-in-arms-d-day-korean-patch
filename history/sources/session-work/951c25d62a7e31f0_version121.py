exec(open('work/analyze112_hang.py',encoding='utf-8-sig').read().split('md=Cs')[0])
import json,hashlib,struct
r=Path('outputs/step121_font/current_ram.bin').read_bytes();base=0x8e03020;stride=0x78000;rows=[]
paths=['PROJECT_ROOT/BIA_STEP120_MAC_NAME_KO_TEST.iso','PROJECT_ROOT/BIA_STEP118_FONT_GUTTER_TEST.iso','PROJECT_ROOT/BIA_STEP117_NEW_OBJECTIVE_KO_TEST.iso','PROJECT_ROOT/BIA_STEP116_TUTORIAL_CHARACTER_NAMES_KO_TEST.iso','PROJECT_ROOT/BIA_STEP112_DIALOGUE_AND_INTERACTION_KO_TEST.iso']
for path in paths:
 _,blob=b.iso_read_file(Path(path),['PSP_GAME','USRDIR','SYSTEM','D0_0130_.MDI']);st={x['index']:bytes(x['decoded']) for x in b.parse_mdi(blob)};vals=[]
 for i,o,n in [(34,0,0x20000),(35,0,0x17000),(35,0x56000,64),(35,0x58000,32)]:
  a=base+i*stride+o;raw=r[a-0x8000000:a-0x8000000+n];expected=st[i][o:o+n];vals.append({'stream':i,'offset':hex(o),'diff':sum(a!=z for a,z in zip(raw,expected))})
 rows.append({'iso':Path(path).name,'comparison':vals})
Path('outputs/step121_font/version_comparison.json').write_text(json.dumps(rows,indent=2));print(json.dumps(rows,indent=2))
