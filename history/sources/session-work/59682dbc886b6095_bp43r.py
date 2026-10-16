import json
from pathlib import Path
p=Path('work/nav43r_tmp.json');p.write_text(json.dumps({'debug_request':{'event':'cpu.breakpoint.add','address':0x08972360,'enabled':True,'log':True,'logFormat':'TITLEDRAW a0={a0} a1={a1} a2={a2} a3={a3} s0={s0} s1={s1} s2={s2} s3={s3} ra={ra}'},'name':'title_draw_hit','regs':True,'scan':True}));p.replace('work/nav43r_command.json')
