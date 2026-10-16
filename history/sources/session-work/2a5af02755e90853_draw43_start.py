import sys
sys.path.insert(0,'work/python_deps')
from capstone import *
from pathlib import Path
d=Path('work/biaoff43.prx').read_bytes();md=Cs(CS_ARCH_MIPS,CS_MODE_MIPS32+CS_MODE_LITTLE_ENDIAN)
for i in md.disasm(d[0x20f38+0x80:0x21570+0x80],0x08824f38):print(hex(i.address),i.mnemonic,i.op_str)

