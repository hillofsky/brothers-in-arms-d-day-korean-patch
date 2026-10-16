exec(open('work/analyze104_regs.py',encoding='utf-8-sig').read().split('print(str(j)')[0])
r=(out/'paused_088b9c8c_ram.bin').read_bytes();g=dict(zip(j['categories'][0]['registerNames'],j['categories'][0]['uintValues']));print({k:hex(v) for k,v in g.items()});md=Cs(CS_ARCH_MIPS,CS_MODE_MIPS32+CS_MODE_LITTLE_ENDIAN)
md.skipdata=True
for key in ['s0','s1','s3','s4','s5','sp']:
 a=g[key];o=a-0x8000000;print(key,hex(a),r[o:o+100].hex(),repr(r[o:o+100]))
for a,z in [(0x088b9ae4,0x088b9c40),(0x088b99f8,0x088b9ae4),(0x088d4690,0x088d4700)]:
 print('CODE',hex(a))
 for i in md.disasm(r[a-0x8000000:z-0x8000000],a):print(hex(i.address),i.mnemonic,i.op_str)


