import struct
from pathlib import Path
for tag,p in [('orig','stage43r_original_probe/original_title_later_ram.bin'),('patch','stage43r_title_probe/title_missing_ram.bin')]:
 r=Path('outputs')/p;r=r.read_bytes();print(tag)
 for a in range(0x973bbb0,0x973bd00,4):
  v=struct.unpack_from('<I',r,a-0x8000000)[0]
  print(hex(a),hex(v),struct.unpack('<f',struct.pack('<I',v))[0])
