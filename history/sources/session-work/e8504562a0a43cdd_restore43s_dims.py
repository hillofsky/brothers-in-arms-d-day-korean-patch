import json,base64
from pathlib import Path
r=Path('outputs/stage43s_validation/title_prompt_verified_ram.bin').read_bytes();a=0x095e21c0+0x44;v=r[a-0x8000000:a-0x8000000+20];p=Path('work/nav43s_tmp.json');p.write_text(json.dumps({'debug_request':{'event':'memory.write','address':a,'base64':base64.b64encode(v).decode()},'name':'size_original_restored'}));p.replace('work/nav43s_command.json')
