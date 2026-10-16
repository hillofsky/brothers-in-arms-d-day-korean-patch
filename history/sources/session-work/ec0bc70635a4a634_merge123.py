import json
from pathlib import Path
o=Path('outputs/step123');a=json.loads((o/'reference_audit.json').read_text(encoding='utf-8'));b=json.loads(Path('outputs/step123_ui/reference_audit.json').read_text(encoding='utf-8'));a['targets'].update(b['targets']);d={(r['mdi'],r['stream'],r['offset']):r for r in a['refs']}
for r in b['refs']:
 key=(r['mdi'],r['stream'],r['offset'])
 if r['key_verified'] or key not in d:d[key]=r
a['refs']=list(d.values());(o/'reference_audit.json').write_text(json.dumps(a,ensure_ascii=False,indent=2),encoding='utf-8');(o/'targets.json').write_text(json.dumps(a['targets'],ensure_ascii=False,indent=2),encoding='utf-8');print('verified refs',sum(r['key_verified'] for r in a['refs']))
