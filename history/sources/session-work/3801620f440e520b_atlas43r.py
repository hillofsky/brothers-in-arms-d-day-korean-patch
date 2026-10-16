from pathlib import Path
from PIL import Image
r=Path('outputs/stage43r_title_probe/title_post_hit_ram.bin').read_bytes();raw=r[0x0987d020-0x8000000:0x0987d020-0x8000000+0x20000];im=Image.new('L',(512,512));p=im.load()
for y in range(512):
 for x in range(512):
  bx=x//2;o=(y//8)*16*128+(bx//16)*128+(y%8)*16+bx%16;p[x,y]=((raw[o]>>(4*(x%2)))&15)*17
im.save('outputs/stage43r_title_probe/menu_atlas.png');print(r[0x08e693c0-0x8000000:0x08e693c0-0x8000000+32].hex())
