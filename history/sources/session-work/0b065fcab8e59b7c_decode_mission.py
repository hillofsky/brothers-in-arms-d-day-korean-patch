from pathlib import Path
from PIL import Image
out=Path('outputs/stage40q_campaign');data=(out/'first_mission_vram.bin').read_bytes()
for a in [0,0x44000,0x88000]:Image.frombytes('RGBA',(512,272),data[a:a+512*272*4]).convert('RGB').crop((0,0,480,272)).save(out/('first_mission8888_'+hex(a)+'.png'))
