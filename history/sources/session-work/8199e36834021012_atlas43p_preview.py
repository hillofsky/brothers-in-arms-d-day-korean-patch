from pathlib import Path
import json
from PIL import Image
raw=Path('outputs/stage43p_probe/atlas_swizzled.bin').read_bytes();im=Image.new('L',(512,512));px=im.load()
for y in range(512):
 for x in range(512):
  bx=x//2;o=(y//8)*16*128+(bx//16)*128+(y%8)*16+bx%16;v=(raw[o]>>(4*(x%2)))&15;px[x,y]=v*17
im.save('outputs/stage43p_probe/atlas_alpha.png');plan=json.loads(Path('PROJECT_ROOT/bia_stage39a_tools/stage39a_font_plan.json').read_text(encoding='utf-8'))['layout'];items=[a for cp in map(ord,'자유시점모드') for a in plan if a['codepoint']==cp];strip=Image.new('L',(17*len(items),16))
for i,a in enumerate(items):
 crop=im.crop((a['atlas_x'],a['atlas_y'],a['atlas_x']+17,a['atlas_y']+16));strip.paste(crop,(i*17,0));print(hex(a['codepoint']),crop.getbbox())
strip.resize((strip.width*6,96),Image.Resampling.NEAREST).save('outputs/stage43p_probe/reference_glyphs.png')
