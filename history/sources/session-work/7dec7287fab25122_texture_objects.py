import struct,json
from pathlib import Path
ram=Path('outputs/stage40k/controls_ram.bin').read_bytes();base=0x08000000
for p in [0x095e21c0,0x095e22f0]:
 d=ram[p-base:p-base+0x130];print(hex(p))
 for o in range(0,len(d),16):print(hex(o),' '.join('%08x'%x for x in struct.unpack_from('<IIII',d,o)))
