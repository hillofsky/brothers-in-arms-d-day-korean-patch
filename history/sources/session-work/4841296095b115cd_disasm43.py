import sys
sys.path.insert(0,'work/python_deps')
from capstone import *
from pathlib import Path
d=Path('work/biaoff43.prx').read_bytes();md=Cs(CS_ARCH_MIPS,CS_MODE_MIPS32+CS_MODE_LITTLE_ENDIAN)
for i in md.disasm(d[0x18a000+0x80:0x18a600+0x80],0x0898e000):print(hex(i.address),i.mnemonic,i.op_str)
