import sys,struct
sys.path.insert(0,'work/python_deps');from capstone import *
from pathlib import Path
d=Path('work/biaoff43.prx').read_bytes();md=Cs(CS_ARCH_MIPS,CS_MODE_MIPS32+CS_MODE_LITTLE_ENDIAN);needle=struct.pack('<I',0x0c000000|(0x1f0178>>2));p=d.find(needle)
while p>=0:
 a=p-0x80+0x8804000;print('LOOKUPCALL',hex(a))
 for ins in md.disasm(d[p-16:p+24],a-16):print(hex(ins.address),ins.mnemonic,ins.op_str)
 p=d.find(needle,p+4)

