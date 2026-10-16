import json
from pathlib import Path
p=Path('outputs/step119/reference_audit.json');j=json.loads(p.read_text(encoding='utf-8'));j['targets']['release']='누름 해제'
for r in j['refs']:
 if r['english']=='release':r['korean']='누름 해제'
p.write_text(json.dumps(j,ensure_ascii=False,indent=2),encoding='utf-8');Path('outputs/step119/targets.json').write_text(json.dumps(j['targets'],ensure_ascii=False),encoding='utf-8')
s=Path('work/build119.py').read_text(encoding='utf-8-sig').replace('assert not dst.exists();','assert dst.exists();').replace('shutil.copy2(src,dst);','');Path('work/build119.py').write_text(s,encoding='utf-8')
