exec(open('work/inventory43ufont.py',encoding='utf-8').read().split('for addr,size,name')[0])
addr=0x09a8cb30;i,o=divmod(addr-base,stride);d=st[i][o:o+1024];Path('outputs/stage43b/hud_texture_object.bin').write_bytes(d);print([(hex(k),hex(struct.unpack_from('<I',d,k)[0])) for k in range(0,400,4)])
