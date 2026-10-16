import csv,json
from pathlib import Path
rows=list(csv.DictReader(Path('PROJECT_ROOT/analysis/stage38_translation_worklist/stage38_translation_units.tsv').open(encoding='utf-8-sig'),delimiter='\t'));old=json.loads(Path('work/campaign_first_ko.json').read_text(encoding='utf-8'));new=[r for r in rows if r['priority']=='B' and r['id'] not in old and 'D0_0700_EXIT4:' in r['references']];Path('work/campaign_second_units.json').write_text(json.dumps(new,ensure_ascii=False,indent=2),encoding='utf-8');print(len(new));print('\n'.join(r['id']+' '+r['English'] for r in new[:45]))
