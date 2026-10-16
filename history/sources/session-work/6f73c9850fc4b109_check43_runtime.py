import json,struct
from pathlib import Path
p=Path('outputs/stage43a_validation/controls_ram.bin');r=p.read_bytes();a=json.loads(Path('outputs/stage43a/campaign_actions.json').read_text(encoding='utf-8'));good=[];bad=[]
for v in a:
 o=0x08E03020+v['stream']*0x78000+int(v['offset'],0)-0x08000000
 ptr,n,cap=struct.unpack_from('<III',r,o)
 s=(v['korean']+'\0').encode()
 ok=ptr==int(v['pointer'],0) and r[ptr-0x08000000:ptr-0x08000000+len(s)]==s
 (good if ok else bad).append(v['id'])
print(json.dumps({'verified':len(good),'failed':len(bad),'sample':bad[:5]}))
