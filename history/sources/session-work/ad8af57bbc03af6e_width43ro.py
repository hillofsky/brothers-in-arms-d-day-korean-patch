import json
from pathlib import Path
p=Path('work/nav43ro_tmp.json');p.write_text(json.dumps({'debug_request':{'event':'memory.breakpoint.add','address':0x0973bc78,'size':4,'enabled':True,'log':True,'read':False,'write':True,'logFormat':'TITLEWIDTH pc={pc} ra={ra} a0={a0} a1={a1} s0={s0} s1={s1} s2={s2}'},'name':'width_guard'}));p.replace('work/nav43ro_command.json')
