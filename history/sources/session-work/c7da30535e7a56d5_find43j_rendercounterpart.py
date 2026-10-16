from pathlib import Path
import sys
sys.path.insert(0,'work/python_deps');from capstone import *
on=Path('work/biaon43.prx').read_bytes();off=Path('work/biaoff43.prx').read_bytes();md=Cs(CS_ARCH_MIPS,CS_MODE_MIPS32+CS_MODE_LITTLE_ENDIAN)
for a in [0x16e340,0x16e348,0x16e368,0x16e350]:
 chunk=on[a+0x80:a+0x90];p=off.find(chunk);print('MATCH',hex(a),hex(p-0x80+0x8804000) if p>=0 else None)
for ins in md.disasm(on[0x16e330+0x80:0x16e390+0x80],0x08972330):print(hex(ins.address),ins.mnemonic,ins.op_str)
