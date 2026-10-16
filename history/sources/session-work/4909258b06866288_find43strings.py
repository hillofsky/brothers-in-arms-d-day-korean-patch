import json
from pathlib import Path
r=Path('outputs/stage43a_validation/controls_ram.bin').read_bytes();t=json.loads(Path('work/campaign_first_ko.json').read_text(encoding='utf-8'))
for id in ['BIA-01372','BIA-01291']:
 s=t[id];u=s.encode('utf-8'); w=b''.join(bytes([x,0]) for x in u)
 for name,p in [('utf8',u),('utf16',s.encode('utf-16le')),('wideutf8',w)]:
  a=[];o=0
  while (o:=r.find(p,o))>=0:a.append(hex(o+0x8000000));o+=len(p)
  print(id,name,a[:15])
