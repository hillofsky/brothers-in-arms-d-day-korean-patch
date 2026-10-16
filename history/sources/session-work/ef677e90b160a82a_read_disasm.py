import json,re,collections
from pathlib import Path
r=json.loads(Path('outputs/stage40k/lookup_disasm.json').read_text())
print('\n'.join(hex(x['address'])+' '+x.get('name','')+' '+x.get('params','') for x in r['lines'][:35]))
