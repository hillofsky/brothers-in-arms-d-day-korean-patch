import json,struct,re
from pathlib import Path
r=json.loads(Path('outputs/stage43i/hint_fit_report.json').read_text(encoding='utf-8'));maps=Path('outputs/stage43h/remap.bin').read_bytes();glyphs=Path('outputs/stage43h/glyphs.bin').read_bytes();width={}
for i in range(len(maps)//8):
 _,cp,gi=struct.unpack_from('<iHH',maps,i*8);width[cp]=struct.unpack_from('<I',glyphs,gi*20+8)[0]
for k in ['before','after']:
 t=re.sub(r'%icon_compass_arrow%','',r[k]);r[k+'_glyph_width']=sum(width[ord(c)] for c in t);r[k+'_icon_width_estimate']=17
Path('outputs/stage43i/hint_fit_report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8');print(r['before_glyph_width'],r['after_glyph_width'])
