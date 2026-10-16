import struct,sys
from pathlib import Path
sys.path.insert(0,'work/python_deps');from capstone import *
d=Path('work/biaoff43.prx').read_bytes();md=Cs(CS_ARCH_MIPS,CS_MODE_MIPS32+CS_MODE_LITTLE_ENDIAN)
for p in range(0x80,0x490080,4):
 w=struct.unpack_from('<I',d,p)[0]
 if w>>26 in [0x21,0x25] and w&65535==0x50 and (w>>21)&31 not in [29]:
  a=p-0x80+0x8804000;print('FONTCOUNT',hex(a))
  for ins in md.disasm(d[p-12:p+64],a-12):print(hex(ins.address),ins.mnemonic,ins.op_str)
