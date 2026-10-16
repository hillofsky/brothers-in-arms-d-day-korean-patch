import time,json
from pathlib import Path
out=Path('outputs/stage43n3_restart');log=out/'ppsspp.log';p=Path('work/nav43n3_command.json');end=time.time()+500
while time.time()<end:
 if 'RESTARTBAD' in log.read_text(errors='ignore'):
  while p.exists():time.sleep(.1)
  q=p.with_name('nav43n3_bad_pending.json');q.write_text(json.dumps({'name':'invalid_callback_hit','scan':True,'regs':True,'disasmAddress':'0x08816080','count':30}));q.replace(p)
  while not(out/'invalid_callback_hit_ram.bin').exists():time.sleep(.2)
  print('INVALID CALLBACK CAPTURED',flush=True);break
 time.sleep(2)
else:print('TIMEOUT',flush=True)
