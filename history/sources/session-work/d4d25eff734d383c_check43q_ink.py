from PIL import Image
from pathlib import Path
import json
im=Image.open('outputs/stage43p_probe/atlas_alpha.png');items=json.loads(Path('PROJECT_ROOT/bia_stage39a_tools/stage39a_font_plan.json').read_text(encoding='utf-8'))['layout']+json.loads(Path('outputs/stage43a/new_font_glyphs.json').read_text(encoding='utf-8'));counts={};bottom=[]
for a in items:
 b=im.crop((a['atlas_x'],a['atlas_y'],a['atlas_x']+17,a['atlas_y']+16)).getbbox();h=b[3] if b else 0;counts[h]=counts.get(h,0)+1
 if h==16:bottom.append(a['codepoint'])
print('Bottom bound counts',counts,'Row15 glyphs',len(bottom),bottom[:15])
