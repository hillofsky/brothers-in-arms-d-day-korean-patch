exec(open('work/weapon124inspect.py',encoding='utf-8-sig').read().split('for i,d')[0])
for j in range(1,60):
 r=st[35][j*24:j*24+24]
 print(j,repr(chr(struct.unpack_from('<H',r)[0])),list(r[2:8]))
# RFont methods around lookup/draw, offsets relative module base.
md=Cs(CS_ARCH_MIPS,CS_MODE_MIPS32+CS_MODE_LITTLE_ENDIAN)
d=Path('outputs/step124/biaoff.prx').read_bytes()
a=0x08c5ee00;off=a-0x8804000+0x80
Path('outputs/step124/rfont_methods.txt').write_text('\n'.join(f'{i.address:08x} {i.mnemonic} {i.op_str}' for i in md.disasm(d[off:off+0x1000],a)))
