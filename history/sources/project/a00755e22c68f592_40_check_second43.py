import json,re,collections,csv
from pathlib import Path
rows=json.loads(Path('work/campaign_second_units.json').read_text(encoding='utf-8'));tr=json.loads(Path('work/campaign_second_ko.json').read_text(encoding='utf-8'));assert len(rows)==len(tr)==90
for r in rows:assert collections.Counter(re.findall(r'%[^%\s]+%',r['English']))==collections.Counter(re.findall(r'%[^%\s]+%',tr[r['id']])),r['id']
p=Path('outputs/stage43b');p.mkdir(exist_ok=True)
with (p/'campaign_second_mission_ko.tsv').open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.DictWriter(f,list(rows[0]),delimiter='\t');w.writeheader();w.writerows({**r,'한국어':tr[r['id']]} for r in rows)
print('90 translations; all control tokens preserved')
