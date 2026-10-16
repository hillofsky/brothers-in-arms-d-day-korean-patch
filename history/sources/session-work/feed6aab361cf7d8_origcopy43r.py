import json
from pathlib import Path
p=Path('work/nav43ro_tmp.json');p.write_text(json.dumps({'debug_request':{'event':'memory.breakpoint.add','address':0x08e4cae4,'size':36,'enabled':False,'log':True,'read':True,'write':False,'logFormat':'ORIGCOPY pc={pc} ra={ra} a0={a0} a1={a1} s0={s0} s1={s1}'},'debug_send':{'event':'cpu.resume'},'name':'orig_resume'}));p.replace('work/nav43ro_command.json')

