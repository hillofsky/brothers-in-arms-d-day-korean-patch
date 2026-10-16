import json,math,re
from pathlib import Path
from PIL import Image,ImageFont,ImageDraw
out=Path('outputs/step124/movie');out.mkdir(exist_ok=True)
j=json.loads(Path('PROJECT_ROOT/stage42g/stage42g_token_dictionary.json').read_text(encoding='utf-8'));lookup={t['key']:t['text'] for t in j['tokens']};lookup[92]='\\'
# Stable byte dictionary, 512x512 RGBA texture and original text budgets.
font=ImageFont.truetype('LOCAL_PATH',11)
rects={k:(math.ceil(font.getlength(t))+1,14) for k,t in lookup.items() if k!=92};free=[(0,0,512,512)];placed={}
for k,(w,h) in sorted(rects.items(),key=lambda kv:(-kv[1][1],-kv[1][0])):
 options=[(min(rw-w,rh-h),max(rw-w,rh-h),y,x) for x,y,rw,rh in free if w<=rw and h<=rh]
 assert options,('atlas full',k)
 _,_,y,x=min(options);placed[k]=(x,y,w,h);nf=[]
 for fx,fy,fw,fh in free:
  if x>=fx+fw or x+w<=fx or y>=fy+fh or y+h<=fy:nf.append((fx,fy,fw,fh));continue
  if x>fx:nf.append((fx,fy,x-fx,fh))
  if x+w<fx+fw:nf.append((x+w,fy,fx+fw-x-w,fh))
  if y>fy:nf.append((fx,fy,fw,y-fy))
  if y+h<fy+fh:nf.append((fx,y+h,fw,fy+fh-y-h))
 free=[r for n,r in enumerate(nf) if not any(n!=i and r[0]>=s[0] and r[1]>=s[1] and r[0]+r[2]<=s[0]+s[2] and r[1]+r[3]<=s[1]+s[3] and (r!=s or n<i) for i,s in enumerate(nf))]
atlas=Image.new('RGBA',(512,512));lines=[]
for k,(x,y,w,h) in placed.items():
 mask=Image.new('L',(w,h));ImageDraw.Draw(mask).text((0,-1),lookup[k],font=font,fill=255)
 # Existing movie renderer uses RGBA grayscale antialias pixels with binary coverage.
 rgba=Image.merge('RGBA',(mask,mask,mask,mask.point(lambda v:255 if v else 0)));atlas.paste(rgba,(x,y));lines.append(bytes([k])+f'-{x:03d},{y:03d},{w:03d},{h:03d}\r\n'.encode())
(out/'SUBTITLEHASHMAP.INI').write_bytes(b''.join(lines));(out/'SUBTITLETEXTURE.RAW').write_bytes(atlas.tobytes());atlas.save(out/'atlas.png')
fields=[]
for f in j['all_fields']:
 enc=bytes.fromhex(f['encoded_hex']);title=f['field_index']==1
 if title:new=enc
 else:
  joined=enc.replace(b'\\',b' ');tokens=list(joined);result=[];width=0;lastbreak=None
  # Prefer spaces that are standalone dictionary tokens. Avoid splitting encoded phrase/syllable fragments.
  for k in tokens:
   width+=placed[k][2]
   result.append(k)
   if k==32:lastbreak=len(result)-1
   if width>370:
    assert lastbreak is not None,(f['file'],f['field_index'],'no word boundary')
    result[lastbreak]=92;width=sum(placed[v][2] for v in result[lastbreak+1:]);lastbreak=None
  new=bytes(result)
 assert len(new)<=f['field_bytes']-1
 # All original spoken text preserved; only whitespace and wrap positions may change.
 assert re.sub(r'\s+','',''.join(lookup[k] for k in new).replace('\\',' '))==re.sub(r'\s+','',f['korean'].replace('\\',' '))
 rows=new.split(b'\\');widths=[sum(placed[k][2] for k in row) for row in rows];assert max(widths)<=390,(f['file'],f['field_index'],widths)
 fields.append({**f,'encoded_new':new.hex(),'new_text':''.join(lookup[k] for k in new),'line_widths':widths,'lines':len(rows)})
(out/'layout.json').write_text(json.dumps({'font_before':9,'font_after':11,'texture_size':[512,512],'fields':fields},ensure_ascii=False,indent=2),encoding='utf-8')
print('packed',len(placed),'fields',len(fields),'maxlines',max(f['lines'] for f in fields),'reflow',sum(f['encoded_new']!=f['encoded_hex'].replace(' ','').lower() for f in fields))
# 4x offline preview of reported short sentence; no gameplay or movie playback.
f=next(f for f in fields if '원한 건 아니지만' in f['korean']);im=Image.new('RGB',(480,272),(50,50,50));dr=ImageDraw.Draw(im);dr.rectangle((47,206,433,267),fill=(12,12,12));x,y=57,211
for k in bytes.fromhex(f['encoded_new']):
 if k==92:x,y=57,y+17;continue
 a,b,w,h=placed[k];im.paste(atlas.crop((a,b,a+w,b+h)),(x,y),atlas.crop((a,b,a+w,b+h)));x+=w
im.resize((1920,1088)).save(out/'subtitle_preview.png')
