exec(open('work/static104.py',encoding='utf-8-sig').read().split('for a,z')[0])
for a,z in [(0x088b966c,0x088b9930),(0x088b91b4,0x088b9330)]:
 print('CODE',hex(a));off=a-0x8804000+0x80
 for i in md.disasm(prx[off:off+z-a],a):print(hex(i.address),i.mnemonic,i.op_str)
