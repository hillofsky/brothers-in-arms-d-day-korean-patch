import json,time,struct
from pathlib import Path
p=Path('work/nav43h_command.json');out=Path('outputs/stage43h_validation')
def send(c):
 while p.exists():time.sleep(.1)
 q=p.with_name('nav43h_pending.json');q.write_text(json.dumps(c),encoding='utf-8');q.replace(p)
 while not (out/(c['name']+'_0x4000000.png')).exists():time.sleep(.1)
for i in range(2):send({'hold_button':'start','hold_seconds':.4,'settle':2,'name':'start'+str(i)})
send({'buttons':['cross','cross','cross','cross'],'wait':2,'name':'story'})
for i in range(60):
 n='load'+str(i);send({'hold_button':'start','hold_seconds':.3,'settle':1,'name':n,'memoryAddress':'0x08fc3ccc','memorySize':8})
 f=out/(n+'_memory.bin')
 until=time.time()+5
 while not f.exists() and time.time()<until:time.sleep(.1)
 if f.exists() and struct.unpack_from('<H',f.read_bytes())[0]==879:
  print('MISSION FONT READY',flush=True);time.sleep(2);send({'analog':[0,1],'hold_seconds':4,'name':'hint_test','scan':True});break
 time.sleep(1)
else:print('MISSION WAIT TIMEOUT',flush=True)
