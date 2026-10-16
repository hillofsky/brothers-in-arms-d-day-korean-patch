exec(open('work/disasm124.py',encoding='utf-8-sig').read().split('for a,z,label')[0]);md.skipdata=True
a=0x08c5c000;off=a-0x8804000+0x80
Path('outputs/step124/rfont_render.txt').write_text('\n'.join(f'{i.address:08x} {i.mnemonic} {i.op_str}' for i in md.disasm(d[off:off+0x1100],a)))
