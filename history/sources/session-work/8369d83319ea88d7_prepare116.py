import csv,re,json
from pathlib import Path
out=Path('outputs/step116');out.mkdir(exist_ok=True);lookup={r['source_text']:(r['ko_review'] or r['ko_current']) for r in csv.DictReader(Path('PROJECT_ROOT/translation/text_master.tsv').open(encoding='utf-8-sig'),delimiter='\t')};t={};missing=[]
for p in Path('PROJECT_ROOT/extracted/PSP_GAME/USRDIR/SYSTEM').glob('D*.INT'):
 for line in p.read_bytes().decode('utf-8-sig',errors='replace').splitlines():
  if '=' not in line:continue
  k,v=line.split('=',1);v=v.strip().strip('"')
  if k.startswith('TRAIN_'):
   ko=lookup.get(v)
   if ko:t[v]=ko
   else:missing.append([p.name,k,v])
(out/'tutorial_targets.json').write_text(json.dumps(t,ensure_ascii=False,indent=2),encoding='utf-8');(out/'missing_tutorials.json').write_text(json.dumps(missing,ensure_ascii=False,indent=2),encoding='utf-8');print('matched',len(t),'missing',len(missing));print(json.dumps(missing,ensure_ascii=False))
