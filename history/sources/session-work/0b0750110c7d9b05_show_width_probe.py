import json,struct
from pathlib import Path
p=Path('outputs/stage40l/width_probe_regs.json')
if p.exists():
 r=json.loads(p.read_text());g={n.lower():v for c in r['categories'] for n,v in zip(c.get('registerNames',[]),c.get('uintValues',[]))};print({k:hex(v) for k,v in g.items() if k not in ['hi','lo'] and not k.startswith('f')});d=Path('outputs/stage40l/width_sp.bin').read_bytes();print('stackwords',[hex(x) for x in struct.unpack('<'+'I'*(len(d)//4),d)][:30]);
 for f in ['s1','s2','s3','s6','s7']:
  p=Path('outputs/stage40l/width_'+f+'.bin')
  if p.exists():print(f,p.read_bytes()[:96].hex())
