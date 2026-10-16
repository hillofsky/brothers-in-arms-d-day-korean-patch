import time,json,struct,base64
from pathlib import Path
p=Path('work/nav43p2_command.json');out=Path('outputs/stage43p2_probe');qprx=Path('outputs/stage43q/patched.prx').read_bytes();report=json.loads(Path('outputs/stage43q/patch_report.json').read_text())
def send(c):
 while p.exists():time.sleep(.1)
 q=p.with_name('nav43p2_patch_pending.json');q.write_text(json.dumps(c));q.replace(p)
 while not(out/(c['name']+'_0x4000000.png')).exists():time.sleep(.1)
helper=bytearray(Path('outputs/stage43q/size_adapter.bin').read_bytes());struct.pack_into('<I',helper,20,0x0c000000|(0x08e02d00>>2))
send({'name':'height_helper_live','debug_request':{'event':'memory.write','address':0x08e02f70,'base64':base64.b64encode(helper).decode()}})
for i,(a,v) in enumerate(report['hooks'].items()):
 a=int(a,16);v=int(v,16)
 if v>>26==3:v=0x0c000000|(0x08e02f70>>2)
 send({'name':'height_hook_live'+str(i),'debug_request':{'event':'memory.write','address':0x08804000+a,'base64':base64.b64encode(struct.pack('<I',v)).decode()}})
for i,a in enumerate([0x08827e8c,0x08827ff8]):send({'name':'height_remove_geometry'+str(i),'debug_request':{'event':'cpu.breakpoint.remove','address':a}})
send({'name':'height_live_resume','debug_send':{'event':'cpu.resume'}});time.sleep(1)
send({'name':'height_live_screen','regs':True,'scan':True,'debug_request':{'event':'cpu.status'}});print('HEIGHT LIVE PATCH COMPLETE',flush=True)
