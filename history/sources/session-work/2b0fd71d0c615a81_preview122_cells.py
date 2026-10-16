exec(open('work/inspect122_positions.py',encoding='utf-8-sig').read().split("for ch in")[0])
from PIL import Image,ImageDraw
atlas=st[34];im=Image.new('L',(512,512));p=im.load()
for y in range(512):
 for x in range(512):
  bx=x//2;o=(y//8)*2048+(bx//16)*128+(y%8)*16+bx%16;p[x,y]=((atlas[o]>>(4*(x%2)))&15)*17
out=Path('outputs/step122_font');out.mkdir(exist_ok=True);im.crop((128,0,256,64)).resize((1024,512)).save(out/'source_upper_cells.png')
