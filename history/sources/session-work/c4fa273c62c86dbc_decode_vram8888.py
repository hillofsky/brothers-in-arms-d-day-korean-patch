from pathlib import Path
from PIL import Image
p=Path('outputs/stage40q_campaign/campaign_load_vram.bin')
if p.exists():
 data=p.read_bytes()
 for a in [0,0x44000,0x88000]:
  raw=data[a:a+512*272*4];im=Image.frombytes('RGBA',(512,272),raw).convert('RGB').crop((0,0,480,272));im.save(p.parent/('campaign8888_'+hex(a)+'.png'))
