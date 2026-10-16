import json
from pathlib import Path
p=Path('work/nav43ro_tmp.json');p.write_text(json.dumps({'debug_request':{'event':'memory.breakpoint.add','address':0x08dc65e9,'size':19,'enabled':False,'log':True,'read':True,'write':False,'logFormat':'ORIGNARROW pc={pc} ra={ra} a0={a0} a1={a1} s0={s0} s1={s1}'},'debug_send':{'event':'cpu.resume'},'name':'orig_resume'}));p.replace('work/nav43ro_command.json')

