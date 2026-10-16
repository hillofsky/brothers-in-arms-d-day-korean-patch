import re,collections,json
from pathlib import Path
lines=Path('outputs/stage40k/ppsspp.log').read_text(encoding='utf-8',errors='replace').splitlines();groups=collections.defaultdict(list)
for line in lines:
 if 'BIA40K' in line:
  d=dict(re.findall(r'(a0|a1|ra|s[0-5]|sp)=([0-9a-f]{8})',line));groups[(d['ra'],d['a0'])].append(d)
for key,rows in groups.items():
 print(key,'count',len(rows),'codes',list(dict.fromkeys(x['a1'] for x in rows))[:35]);print(rows[0])
Path('outputs/stage40k/lookup_groups.json').write_text(json.dumps({str(k):{'count':len(v),'examples':v[:20]} for k,v in groups.items()},indent=2),encoding='utf-8')
