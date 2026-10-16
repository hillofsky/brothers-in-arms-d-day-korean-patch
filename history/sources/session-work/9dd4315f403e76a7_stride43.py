import sys,struct
sys.path.insert(0,'work/python_deps')
from capstone import *
from pathlib import Path
d=Path('work/biaoff43.prx').read_bytes();md=Cs(CS_ARCH_MIPS,CS_MODE_MIPS32+CS_MODE_LITTLE_ENDIAN);md.skipdata=True
for p in range(0x80,0x490080,4):
 w=struct.unpack_from('<I',d,p)[0]
 if w>>26!=0 or w&63!=0 or (w>>6)&31!=4:continue
 src=(w>>16)&31
 nxt=[struct.unpack_from('<I',d,z)[0] for z in range(p+4,min(p+20,len(d)-4),4)]
 if any(x>>26==0 and x&63==0 and (x>>6)&31==2 and (x>>16)&31==src for x in nxt):
  a=p-0x80+0x08804000;print('STRIDE20',hex(a))
  for i in md.disasm(d[p-24:p+56],a-24):print(hex(i.address),i.mnemonic,i.op_str)
