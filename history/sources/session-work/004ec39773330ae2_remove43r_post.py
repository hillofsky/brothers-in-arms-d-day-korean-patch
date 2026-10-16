import json
from pathlib import Path
p=Path('work/nav43r_tmp.json');p.write_text(json.dumps({'debug_request':{'event':'cpu.breakpoint.remove','address':0x08972368},'debug_send':{'event':'cpu.resume'},'name':'title_texture_unpaused'}));p.replace('work/nav43r_command.json')
