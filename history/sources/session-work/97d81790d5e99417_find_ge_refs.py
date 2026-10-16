from pathlib import Path
import struct
r=Path('outputs/stage40q_campaign/controls_ram.bin').read_bytes()
for a in [0x09c8be40,0x49c8be40]:
 needle=struct.pack('<I',a);p=r.find(needle);hits=[]
 while p>=0:hits.append(hex(p+0x8000000));p=r.find(needle,p+1)
 print(hex(a),hits[:25])
for a in [0x9bf66d8]:
 for o in range(0,0x140,16):print(hex(a+o),' '.join(hex(v) for v in struct.unpack_from('<4I',r,a+o-0x8000000)))
