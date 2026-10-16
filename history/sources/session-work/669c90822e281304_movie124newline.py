exec(open('work/disasm124.py',encoding='utf-8-sig').read().split('for a,z,label')[0])
a=0x0893e908;off=a-0x8804000+0x80
print('\n'.join(f'{i.address:08x} {i.mnemonic} {i.op_str}' for i in md.disasm(d[off:off+0x170],a)))
