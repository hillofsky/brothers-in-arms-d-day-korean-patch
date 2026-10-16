import struct
from pathlib import Path
for tag,p in [('orig','stage43r_original_probe/original_title_later_ram.bin'),('patch','stage43r_title_probe/title_missing_ram.bin')]:
 r=(Path('outputs')/p).read_bytes();print(tag)
 for o in range(0,len(r)-0x500,4):
  n=struct.unpack_from('<H',r,o+0x50)[0]
  if not 60<=n<=1000:continue
  ptr=struct.unpack_from('<I',r,o+0x54)[0];off=ptr-0x8000000
  if not 0<=off<len(r)-24*n:continue
  cps=[struct.unpack_from('<H',r,off+i*24)[0] for i in range(45)]
  if sum(32<=v<127 for v in cps)>30:print(hex(o+0x8000000),n,hex(ptr), 'tex',hex(struct.unpack_from('<I',r,o+0x488)[0]))
