import json,time
from pathlib import Path
p=Path('work/nav43p2_command.json');out=Path('outputs/stage43p2_probe')
def send(c):
 while p.exists():time.sleep(.1)
 q=p.with_name('nav43p2_pending.json');q.write_text(json.dumps(c),encoding='utf-8');q.replace(p)
 while not (out/(c['name']+'_0x4000000.png')).exists():time.sleep(.1)
for i in range(2):send({'hold_button':'start','hold_seconds':.5,'settle':2,'name':'start'+str(i)})
for i in range(4):send({'hold_button':'cross','hold_seconds':.5,'settle':2,'name':'cross'+str(i)})
for i in range(100):
 send({'hold_button':'start','hold_seconds':.5,'settle':1,'name':'load'+str(i)})
 if 'HUDCP' in (out/'ppsspp.log').read_text(errors='ignore'):
  send({'name':'hint_fit_verified'});print('HUD READY',flush=True);break
 time.sleep(1)
