from pathlib import Path
import struct
r=Path('outputs/stage40q_campaign/controls_ram.bin').read_bytes()
for a in [0x09a8d5e0,0x09a8d6d0]:
 print(hex(a))
 for o in range(0,0x130,16):print(hex(o),' '.join(hex(x) for x in struct.unpack_from('<4I',r,a+o-0x8000000)))
