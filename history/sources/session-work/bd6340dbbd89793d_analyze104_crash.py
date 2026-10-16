import sys,struct
from pathlib import Path
sys.path.insert(0,'work/python_deps')
from capstone import *
r=Path('outputs/step104_crash/current_ram.bin').read_bytes();md=Cs(CS_ARCH_MIPS,CS_MODE_MIPS32+CS_MODE_LITTLE_ENDIAN)
for a,z in [(0x088b9c40,0x088b9cb0),(0x088d46a0,0x088d4700),(0x08891f40,0x08891f90)]:
 print('CODE',hex(a))
 for i in md.disasm(r[a-0x8000000:z-0x8000000],a):print(hex(i.address),i.mnemonic,i.op_str)
print('STACK')
for a in range(0x09ffe6c0,0x09ffe760,16): print(hex(a),[hex(x) for x in struct.unpack_from('<4I',r,a-0x8000000)])
