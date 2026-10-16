exec(open('work/static104.py',encoding='utf-8-sig').read().split('for a,z')[0])
r=Path('outputs/step104_user_repro/paused_088b9c8c_ram.bin').read_bytes()
for a in [0x8dbc740,0x8dbc740+0x1018,0x8dbc740+0x101c,0x8dbc740+0x1020,0x9a85718,0x9a857e4]:
 print(hex(a),[hex(x) for x in struct.unpack_from('<8I',r,a-0x8000000)])
for a,z in [(0x08891ee0,0x08891f70),(0x088c59c0,0x088c5b00),(0x088e20c8,0x088e2280)]:
 print('CODE',hex(a));off=a-0x8804000+0x80
 for i in md.disasm(prx[off:off+z-a],a):print(hex(i.address),i.mnemonic,i.op_str)
