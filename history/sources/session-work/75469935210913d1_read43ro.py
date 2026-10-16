import json
from pathlib import Path
p=Path('work/nav43ro_tmp.json');p.write_text(json.dumps({'debug_request':{'event':'memory.breakpoint.add','address':0x09747550,'size':36,'enabled':True,'log':True,'read':True,'write':False,'logFormat':'ORIGREAD pc={pc} ra={ra} a0={a0} a1={a1} a2={a2} s0={s0} s1={s1} s2={s2} s3={s3}'},'name':'original_read_guard'}));p.replace('work/nav43ro_command.json')
