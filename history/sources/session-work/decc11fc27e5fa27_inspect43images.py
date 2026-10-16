exec(open('work/inventory43ufont.py',encoding='utf-8').read().split('for addr,size,name')[0])
for addr,size,name in [(0x095b6d00,256,'glyph_image0'),(0x095bb600,256,'glyph_image_space'),(0x08e039a0,32,'font_textures')]:
 i,o=divmod(addr-base,stride);d=st[i][o:o+size];Path('outputs/stage43b/'+name+'.bin').write_bytes(d);print(name,[(hex(k),hex(struct.unpack_from('<I',d,k)[0])) for k in range(0,min(128,len(d)),4)])
