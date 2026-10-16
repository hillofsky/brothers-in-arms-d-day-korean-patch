import importlib.util,struct,json,hashlib
from pathlib import Path
s=importlib.util.spec_from_file_location('m','PROJECT_ROOT/bia_stage40i_tools/bia_stage40i_actual_resource_trace.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);_,b=m.load_helpers()
r=Path('outputs/step113_font/current_ram.bin').read_bytes();base=0x8e03020;stride=0x78000
_,d=b.iso_read_file(Path('PROJECT_ROOT/BIA_STEP112_DIALOGUE_AND_INTERACTION_KO_TEST.iso'),['PSP_GAME','USRDIR','SYSTEM','D10_0801.MDI']);st={x['index']:bytes(x['decoded']) for x in b.parse_mdi(d)}
rd=lambda a,n:r[a-0x8000000:a-0x8000000+n]
report={'map':'D10_0801.MDI','streams':[],'glyphs':[]}
for i,o,n in [(34,0,0x40000),(35,0,0x17000),(35,0x17400,24)]:
 a=base+i*stride+o;v=rd(a,n);expected=st[i][o:o+n];report['streams'].append({'stream':i,'offset':hex(o),'equal':v==expected,'different_bytes':sum(x!=y for x,y in zip(v,expected))})
for f in json.loads(Path('outputs/step113_font/live_fonts.json').read_text()):
 if f['n']==11:continue
 a=int(f['font'],16);h=rd(a,100);gp,n=struct.unpack_from('<II',h,0x28);rp,rn=struct.unpack_from('<II',h,0x40);pairs={cp:gi for j in range(rn) for _,cp,gi in [struct.unpack_from('<iHH',rd(rp+j*8,8))]}
 for c in '88mm 포와 제분소를 점령하라.':
  if ord(c) not in pairs:continue
  gi=pairs[ord(c)];x,y,w,hh,ti=struct.unpack('<4IB3x',rd(gp+gi*20,20));report['glyphs'].append({'font':hex(a),'char':c,'index':gi,'box':[x,y,w,hh],'texture':ti})
Path('outputs/step113_font/static_live_comparison.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(report,ensure_ascii=False)[:5000])


