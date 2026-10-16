import json
from pathlib import Path
p=Path('work/nav43r_tmp.json');p.write_text(json.dumps({'debug_request':{'event':'cpu.breakpoint.add','address':0x08972360,'enabled':False,'log':True,'logFormat':'TITLEDRAW a0={a0} a1={a1} s0={s0} s1={s1} s2={s2} ra={ra}'},'debug_send':{'event':'cpu.resume'},'name':'draw_resume'}));p.replace('work/nav43r_command.json')
