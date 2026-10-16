import json,time
from pathlib import Path
p=Path('work/nav43o_command.json');out=Path('outputs/stage43o_validation')
def send(c):
 while p.exists():time.sleep(.1)
 q=p.with_name('nav43o_follow_pending.json');q.write_text(json.dumps(c));q.replace(p)
 while not(out/(c['name']+'_0x4000000.png')).exists():time.sleep(.1)
while not(out/'hint_fit_verified_0x4000000.png').exists():time.sleep(.5)
time.sleep(2)
send({'debug_request':{'event':'cpu.breakpoint.add','address':0x088160a8,'enabled':True,'log':True,'condition':'a1 < 0x08800000 || a1 >= 0x0A000000','logFormat':'RESTARTBAD a0={a0} a1={a1} a2={a2} s0={s0} s1={s1} ra={ra}'},'name':'guard_ready'})
send({'hold_button':'start','hold_seconds':.15,'settle':.5,'name':'pause_for_restart'})
print('PAUSED',flush=True)
