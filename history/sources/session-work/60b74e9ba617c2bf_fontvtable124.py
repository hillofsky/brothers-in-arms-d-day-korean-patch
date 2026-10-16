exec(open('work/disasm124.py',encoding='utf-8-sig').read().split('for a,z,label')[0]);a=0x08d643a8;off=a-0x8804000+0x80
for z in range(0,0xb0,8):print(hex(z),[hex(x) for x in struct.unpack_from('<II',d,off+z)])
