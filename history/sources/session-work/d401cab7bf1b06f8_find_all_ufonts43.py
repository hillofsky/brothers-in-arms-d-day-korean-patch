exec(open('work/inventory43ufont.py',encoding='utf-8').read().split('for addr,size,name')[0])
found=[]
for i,d in st.items():
 for o in range(0,len(d)-0x70,4):
  if struct.unpack_from('<I',d,o)[0]!=0x08d68be8:continue
  ptr,num,cap,texptr,tn,tc=struct.unpack_from('<6I',d,o+0x28)
  if 10<=num<=300 and num==cap and 1<=tn<=4 and tn==tc:
   a=base+i*stride+o;found.append({'stream':i,'offset':hex(o),'runtime':hex(a),'glyphs':hex(ptr),'glyph_count':num,'textures':hex(texptr),'texture_count':tn,'remap_count':struct.unpack_from('<I',d,o+0x44)[0]})
Path('outputs/stage43g/all_ufont_objects.json').write_text(json.dumps(found,indent=2));print(json.dumps(found))
