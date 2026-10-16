exec(open('work/disasm124.py',encoding='utf-8-sig').read().split('for a,z,label')[0]);md.skipdata=True
for a,z,n in [(0x0898e000,0x0898ef00,'rfont_wrapper'),(0x08c5e600,0x08c5e800,'rfont_geometry')]:
 off=a-0x8804000+0x80;Path('outputs/step124/'+n+'.txt').write_text('\n'.join(f'{i.address:08x} {i.mnemonic} {i.op_str}' for i in md.disasm(d[off:off+z-a],a)))
