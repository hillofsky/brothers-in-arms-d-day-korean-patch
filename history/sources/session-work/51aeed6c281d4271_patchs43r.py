import json
from pathlib import Path
p=Path('work/nav43r_tmp.json');p.write_text(json.dumps({'debug_request':{'event':'memory.breakpoint.add','address':0x09724eb6,'size':2,'enabled':False,'log':True,'read':True,'write':False,'logFormat':'PATCHS pc={pc} ra={ra} a0={a0} a1={a1} s0={s0} s1={s1} s2={s2}'},'name':'patch_glyph_watch'}));p.replace('work/nav43r_command.json')

