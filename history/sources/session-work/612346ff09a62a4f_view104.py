from pathlib import Path
from PIL import Image
r=Path('outputs/step104_runtime/current_vram.bin').read_bytes()
for o in [0,0x88000,0x44000]:
 img=Image.frombytes('RGBA',(512,272),r[o:o+512*272*4]);img.crop((0,0,480,272)).save('outputs/step104_runtime/view_'+hex(o)+'.png')
