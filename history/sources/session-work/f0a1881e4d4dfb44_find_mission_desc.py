exec(open('work/match_off.py',encoding='utf-8-sig').read().split('for name,va')[0])
from pathlib import Path
r=Path('outputs/stage40q_campaign/controls_ram.bin').read_bytes();a=0x09bf66d8;words=struct.unpack_from('<12I',r,a-0x8000000);print('descriptor',[(i,hex(v)) for i,v in enumerate(words)])
_,dsl=b.iso_read_file(iso,['PSP_GAME','USRDIR','SYSTEM','D0_0130_.DSL']);Path('work/mission.DSL').write_bytes(dsl)
needle=struct.pack('<I',0xb8000807);positions=[];p=dsl.find(needle)
while p>=0:
 positions.append((hex(p),dsl[p-8:p+40].hex()));p=dsl.find(needle,p+1)
print('matchingGE',positions[:20])
