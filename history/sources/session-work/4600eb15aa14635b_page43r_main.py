import struct,json
from pathlib import Path
r=Path('outputs/stage43r_original_probe/original_title_later_ram.bin').read_bytes();rd=lambda a,n:r[a-0x8000000:a-0x8000000+n]
for f in [0x972385c,0x972524c]:
 page=struct.unpack('<I',rd(f+0x58,4))[0];print(hex(f),hex(page),rd(0x09724e10+0x50*2,2).hex())
p=Path('work/nav43ro_tmp.json');p.write_text(json.dumps({'debug_request':{'event':'memory.breakpoint.add','address':0x09724e10+0x50*2,'size':2,'enabled':False,'log':True,'read':True,'write':False,'logFormat':'PLOOKUP pc={pc} ra={ra} a0={a0} a1={a1} s0={s0} s1={s1} s2={s2}'},'debug_send':{'event':'cpu.resume'},'name':'glyph_page_watch'}));p.replace('work/nav43ro_command.json')

