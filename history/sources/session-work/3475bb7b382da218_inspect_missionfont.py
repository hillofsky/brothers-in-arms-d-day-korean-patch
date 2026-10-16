from pathlib import Path
import struct
r=Path('outputs/stage40q_campaign/controls_ram.bin').read_bytes()
for a in [0x9c1af84,0x9c1d11c]:
 print(hex(a))
 for off in [0x50,0x54,0x474,0x478,0x488]:
  p=struct.unpack_from('<I',r,a+off-0x8000000)[0];print(hex(off),hex(p),r[p-0x8000000:p-0x8000000+16].hex() if 0x8000000<p<0xa000000 else '')
