import json
from pathlib import Path
p=Path('work/nav43r_tmp.json');p.write_text(json.dumps({'debug_request':{'event':'memory.breakpoint.add','address':0x08dc65e9,'size':32,'enabled':False,'log':True,'read':True,'write':False,'logFormat':'TITLEEMBED pc={pc} ra={ra} a0={a0} a1={a1} a2={a2} s0={s0} s1={s1}'},'name':'embed_watch'}));p.replace('work/nav43r_command.json')
