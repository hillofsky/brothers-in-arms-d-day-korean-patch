import json,time
from pathlib import Path
p=Path('work/nav43j_command.json');out=Path('outputs/stage43j_trace')
def send(c):
 while p.exists():time.sleep(.1)
 q=p.with_name('nav43j_pending.json');q.write_text(json.dumps(c),encoding='utf-8');q.replace(p)
 while not (out/(c['name']+'_0x4000000.png')).exists():time.sleep(.1)
for i in range(100):
 send({'hold_button':'start','hold_seconds':.5,'settle':1,'name':'reload'+str(i)})
 if 'BIA40Y a0=09c1' in (out/'ppsspp.log').read_text(errors='ignore') and i>70:
  send({'name':'popup_reloaded'});print('HUD READY',flush=True);break
 time.sleep(1)
