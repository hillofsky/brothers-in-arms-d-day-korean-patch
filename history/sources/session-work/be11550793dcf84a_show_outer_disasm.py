import json
from pathlib import Path
r=json.loads(Path('outputs/stage40l/disasm_0x8853c10.json').read_text());print('\n'.join(hex(x['address'])+' '+x.get('name','')+' '+x.get('params','') for x in r['lines']))
