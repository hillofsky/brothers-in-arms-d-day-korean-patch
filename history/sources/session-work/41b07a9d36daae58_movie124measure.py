import json,collections
from pathlib import Path
from PIL import ImageFont
j=json.loads(Path('PROJECT_ROOT/stage42g/stage42g_token_dictionary.json').read_text(encoding='utf-8'))
for size in [11,12,13]:
 f=ImageFont.truetype('LOCAL_PATH',size);rects=[]
 for t in j['tokens']:
  bb=f.getbbox(t['text']);rects.append((t['key'],int(f.getlength(t['text'])+.99)+2,max(1,bb[3]-bb[1])+2))
 print(size,sum(w*h for k,w,h in rects),max(h for k,w,h in rects))
raw=Path('PROJECT_ROOT/stage42g/SUBTITLETEXTURE_42G_512.RAW').read_bytes();print('colors',collections.Counter(tuple(raw[i:i+4]) for i in range(0,len(raw),4)).most_common(8))
