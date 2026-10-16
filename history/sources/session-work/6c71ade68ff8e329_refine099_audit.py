import json
from pathlib import Path
p=Path('outputs/step099/reference_audit.json');d=json.loads(p.read_text(encoding='utf-8'))
for r in d['refs']:
 if r['stream']==2 and r['key_verified']:
  r['key_verified']=False;r['excluded_reason']='Ambiguous duplicated Yes/No metadata outside verified localization dictionaries; preserve identifiers'
p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8');print('LOCALIZATION VALUE REFERENCES',sum(r['key_verified'] for r in d['refs']))
