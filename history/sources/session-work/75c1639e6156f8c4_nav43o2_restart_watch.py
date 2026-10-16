import time,json
from pathlib import Path
out=Path('outputs/stage43o2_validation');log=out/'ppsspp.log';p=Path('work/nav43o2_command.json');end=time.time()+600
while time.time()<end:
 t=log.read_text(errors='ignore');tail=t.split('HEAPROOTCLEAR')[-1]
 if 'RESTARTBAD' in tail or 'Invalid address' in tail or 'Invalid PC' in tail:print('RESTART FAILURE',flush=True);break
 if 'HUDCP' in tail:
  while p.exists():time.sleep(.1)
  q=p.with_name('nav43o2_finish_pending.json');q.write_text(json.dumps({'name':'restart_returned_to_gameplay','scan':True,'regs':True,'debug_request':{'event':'cpu.status'}}));q.replace(p)
  while not(out/'restart_returned_to_gameplay_ram.bin').exists():time.sleep(.2)
  print('RESTART GAMEPLAY CAPTURED',flush=True);break
 time.sleep(2)
else:print('RESTART TIMEOUT',flush=True)
