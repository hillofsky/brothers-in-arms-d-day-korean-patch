import sys,struct
sys.path.insert(0,'work/python_deps')
from capstone import *
from pathlib import Path
d=Path('work/biaoff43.prx').read_bytes();md=Cs(CS_ARCH_MIPS,CS_MODE_MIPS32+CS_MODE_LITTLE_ENDIAN);md.skipdata=True
for p in range(0x80,0x490080,4):
 w=struct.unpack_from('<I',d,p)[0]
 if w>>26==0x23 and w&65535==0x54:
  prev=[struct.unpack_from('<I',d,z)[0] for z in range(max(0x80,p-80),p,4)]
  if any(x>>26 in [0x20,0x24,0x25] for x in prev):
   a=p-0x80+0x8804000;print('CANDIDATE',hex(a))
   for i in md.disasm(d[p-40:p+80],a-40):print(hex(i.address),i.mnemonic,i.op_str)
