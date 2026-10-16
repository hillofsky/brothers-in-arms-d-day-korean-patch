import json
from pathlib import Path
r=json.loads(Path('outputs/stage43n_restart/disasm_0x8816080.json').read_text());print('\n'.join(hex(x['address'])+' '+x.get('name','')+' '+x.get('params','') for x in r['lines']));print(Path('outputs/stage43n_restart/ppsspp.log').read_text(errors='ignore')[-900:])
