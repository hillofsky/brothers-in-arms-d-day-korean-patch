import json
from pathlib import Path
p=Path('work/nav43r_tmp.json');p.write_text(json.dumps({'debug_request':{'event':'cpu.breakpoint.add','address':0x08972368,'enabled':True,'log':True,'condition':'s0 == 0x08e5a150','logFormat':'TITLEPOST v0={v0} a0={a0} s0={s0} s1={s1} s2={s2} s3={s3} s4={s4} s5={s5} s6={s6} s7={s7}'},'name':'title_post_guard'}));p.replace('work/nav43r_command.json')
