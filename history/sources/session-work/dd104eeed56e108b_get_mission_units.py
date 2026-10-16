import csv,json
from pathlib import Path
rows=list(csv.DictReader(Path('PROJECT_ROOT/analysis/stage38b_translation_worklist/stage38b_translation_units.tsv').open(encoding='utf-8-sig'),delimiter='\t'));sel=[r for r in rows if 'D0_0130_EAGLES:' in r['references']];Path('work/first_mission_units.json').write_text(json.dumps(sel,ensure_ascii=False,indent=2),encoding='utf8');print('rows',len(sel));print('\n'.join(r['id']+' '+r['English'] for r in sel if r['priority']=='B'))
