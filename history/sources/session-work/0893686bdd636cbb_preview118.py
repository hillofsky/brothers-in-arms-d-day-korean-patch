from PIL import Image,ImageDraw,ImageFont
im=Image.new('RGB',(380,120),'#222222');d=ImageDraw.Draw(im)
for row,size in enumerate([16,14]):
 font=ImageFont.truetype('LOCAL_PATH',size)
 for j,c in enumerate('쉬움 보통 어려움'):
  if c==' ':continue
  box=font.getbbox(c);w,h=box[2]-box[0],box[3]-box[1];d.text((12+j*18+(17-w)//2-box[0],10+row*55+(16-h)//2-box[1]),c,font=font,fill='white')
im.resize((1140,360)).save('outputs/step118_font/glyph_size_comparison.png')
