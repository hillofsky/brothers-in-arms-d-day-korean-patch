import json,time
from pathlib import Path
out=Path('outputs/stage43p2_probe');p=Path('work/nav43p2_command.json');end=time.time()+500
while time.time()<end:
 t=(out/'ppsspp.log').read_text(errors='ignore')
 if 'TOPMAIN' in t or 'TOPTEXT' in t:
  while p.exists():time.sleep(.1)
  q=p.with_name('nav43p2_hit_pending.json');q.write_text(json.dumps({'name':'toptext_native_hit','regs':True,'scan':True,'debug_request':{'event':'cpu.status'}}));q.replace(p)
  while not(out/'toptext_native_hit_ram.bin').exists():time.sleep(.1)
  print('NATIVE TEXT HIT CAPTURED',flush=True);break
 time.sleep(2)
else:print('TIMEOUT',flush=True)
