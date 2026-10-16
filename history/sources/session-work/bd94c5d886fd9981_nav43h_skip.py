import time,json
from pathlib import Path
p=Path('work/nav43h_command.json');out=Path('outputs/stage43h_validation')
for i in range(30):
 while p.exists():time.sleep(.1)
 n='skip'+str(i);q=p.with_name('nav43h_pending.json');q.write_text(json.dumps({'name':n,'hold_button':'start','hold_seconds':.5,'settle':1}),encoding='utf-8');q.replace(p)
 while not (out/(n+'_0x4000000.png')).exists():time.sleep(.1)
 if 'HUDCP' in (out/'ppsspp.log').read_text(errors='ignore'):
  print('HUD READY',flush=True);break
 time.sleep(1)
