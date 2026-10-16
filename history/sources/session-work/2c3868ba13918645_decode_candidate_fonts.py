from pathlib import Path
from PIL import Image
r=Path('outputs/stage40q_campaign/controls_ram.bin').read_bytes();out=Path('outputs/stage40q_campaign')
for a in [0x086c6ec0,0x0877ba40]:
 raw=r[a-0x8000000:a-0x8000000+16384];pixels=[]
 for y in range(256):
  for x in range(128):
   xb=x//2;i=((y//8)*4+xb//16)*128+(y%8)*16+xb%16;v=(raw[i]>>(4*(x%2)))&15;pixels.append(v*17)
 im=Image.new('L',(128,256));im.putdata(pixels);im.save(out/(hex(a)+'_texture.png'))
