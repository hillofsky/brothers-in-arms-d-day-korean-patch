import json
from pathlib import Path
r=Path('outputs/stage43c_hint_trace/controls_ram.bin').read_bytes();a=json.loads(Path('outputs/stage43a/campaign_actions.json').read_text(encoding='utf-8'));watch=[]
for v in a:
 if not (v['key'].startswith('HINT') or v['key'].startswith('TUT')):continue
 p=(v['korean']+'\0').encode();o=0;hits=[]
 while (o:=r.find(p,o))>=0:
  if o+0x8000000<0x09e6b020: hits.append(hex(o+0x8000000));watch.append(hex(o+0x8000000))
  o+=len(p)
 if hits:print(v['id'],v['key'],hits)
Path('work/watch43c.json').write_text(json.dumps({'watch':list(dict.fromkeys(watch)),'name':'watch_hints'}))

