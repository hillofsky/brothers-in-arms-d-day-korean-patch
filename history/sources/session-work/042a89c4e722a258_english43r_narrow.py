import json,base64
from pathlib import Path
payload='Press START button'.encode('ascii')+b'\0\0'
p=Path('work/nav43r_tmp.json');p.write_text(json.dumps({'debug_request':{'event':'memory.write','address':0x099026a0,'base64':base64.b64encode(payload.ljust(32,b'\0')).decode()},'name':'english_live_probe'}));p.replace('work/nav43r_command.json')


