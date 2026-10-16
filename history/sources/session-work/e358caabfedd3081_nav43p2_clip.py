import time,json
from pathlib import Path
out=Path('outputs/stage43p2_probe');p=Path('work/nav43p2_command.json')
while not(out/'hint_fit_verified_0x4000000.png').exists():time.sleep(.5)
time.sleep(2)
while p.exists():time.sleep(.1)
q=p.with_name('nav43p2_probe_pending.json');q.write_text(json.dumps({'name':'clip_break_added','debug_request':{'event':'cpu.breakpoint.add','address':0x08827ff8,'enabled':True,'log':True,'condition':'s0 == 16 && a0 >= 0 && a0 < 20','logFormat':'HINTCLIP canvas={s4} y={a0} height={s0} sp={sp} ra={ra}'}}));q.replace(p)
while not(out/'clip_break_added_0x4000000.png').exists():time.sleep(.1)
time.sleep(2)
q=p.with_name('nav43p2_probe_pending.json');q.write_text(json.dumps({'name':'hint_clip_hit','scan':True,'regs':True,'debug_request':{'event':'cpu.status'}}));q.replace(p)
while not(out/'hint_clip_hit_ram.bin').exists():time.sleep(.1)
print('CLIP CAPTURED',flush=True)
