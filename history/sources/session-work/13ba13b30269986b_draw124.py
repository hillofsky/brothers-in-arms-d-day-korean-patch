exec(open('work/disasm124.py',encoding='utf-8-sig').read().split('for a,z,label')[0]);md.skipdata=True
a=0x08c5d100;off=a-0x8804000+0x80
Path('outputs/step124/rfont_draw.txt').write_text('\n'.join(f'{i.address:08x} {i.mnemonic} {i.op_str}' for i in md.disasm(d[off:off+0x980],a)))
