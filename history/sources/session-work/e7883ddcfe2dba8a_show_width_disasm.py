import json
from pathlib import Path
p=Path('outputs/stage40l/disasm_0x8c7f8a0.json')
if p.exists():
 r=json.loads(p.read_text());print('\n'.join(hex(x['address'])+' '+x.get('name','')+' '+x.get('params','') for x in r['lines']))
