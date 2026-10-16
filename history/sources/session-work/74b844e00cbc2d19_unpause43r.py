import json
from pathlib import Path
p=Path('work/nav43ro_tmp.json');p.write_text(json.dumps({'debug_request':{'event':'memory.breakpoint.remove','address':0x0973bc78,'size':4},'debug_send':{'event':'cpu.resume'},'name':'unpause_width'}));p.replace('work/nav43ro_command.json')
