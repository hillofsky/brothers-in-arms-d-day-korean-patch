exec(open('work/press119.py',encoding='utf-8-sig').read().split('for en in')[0])
base=0x8e03020;stride=0x78000
for off in range(0x54e50-24,0x54e50+96,12):
 a,n,c=struct.unpack_from('<III',st[26],off);i,o=divmod(a-base,stride);print(hex(off),n,repr(st[i][o:o+n] if i in st and n<100 else b''))
