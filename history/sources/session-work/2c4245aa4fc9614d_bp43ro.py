import json
from pathlib import Path
p=Path('work/nav43ro_tmp.json');p.write_text(json.dumps({'debug_request':{'event':'cpu.breakpoint.add','address':0x08972360,'enabled':True,'log':True,'condition':'a1 == 0x50','logFormat':'ORIGTITLE a0={a0} a1={a1} s0={s0} s1={s1} s2={s2} ra={ra}'},'name':'original_title','scan':True,'regs':True}));p.replace('work/nav43ro_command.json')
