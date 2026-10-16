import struct
from pathlib import Path
r=Path('outputs/stage43a_validation/controls_ram.bin').read_bytes()
for p in range(0,len(r)-0x500,4):
 n=struct.unpack_from('<H',r,p+0x50)[0]
 if not 60<=n<=1000:continue
 ptr=struct.unpack_from('<I',r,p+0x54)[0];off=ptr-0x8000000
 if not 0<=off<len(r)-24*n:continue
 cps=[struct.unpack_from('<H',r,off+i*24)[0] for i in range(45)]
 if sum(32<=v<127 for v in cps)>30:print(hex(p+0x8000000),n,hex(ptr))

