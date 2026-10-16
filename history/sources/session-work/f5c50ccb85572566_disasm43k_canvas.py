import sys
sys.path.insert(0,'work/python_deps')
from capstone import *
from pathlib import Path
d=Path('work/biaoff43.prx').read_bytes();md=Cs(CS_ARCH_MIPS,CS_MODE_MIPS32+CS_MODE_LITTLE_ENDIAN);md.skipdata=True
for a,z in [(0x20f38,0x2121c)]:
 for i in md.disasm(d[a+0x80:z+0x80],0x08804000+a):print(hex(i.address),i.mnemonic,i.op_str)

