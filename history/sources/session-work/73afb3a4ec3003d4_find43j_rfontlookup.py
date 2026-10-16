import struct,sys
from pathlib import Path
sys.path.insert(0,'work/python_deps');from capstone import *
d=Path('work/biaoff43.prx').read_bytes();md=Cs(CS_ARCH_MIPS,CS_MODE_MIPS32+CS_MODE_LITTLE_ENDIAN)
for p in range(0x80,0x490080,4):
 w=struct.unpack_from('<I',d,p)[0]
 if w>>26==0 and w&63==2 and (w>>6)&31==8 and (w>>16)&31==5:
  print('SRL8A1',hex(p-0x80+0x8804000))
  for ins in md.disasm(d[p-8:p+40],p-0x88+0x8804000):print(hex(ins.address),ins.mnemonic,ins.op_str)
