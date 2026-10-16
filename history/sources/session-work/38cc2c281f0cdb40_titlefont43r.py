import struct
from pathlib import Path
for tag,p in [('orig','stage43r_original_probe/original_title_later_ram.bin'),('patch','stage43r_title_probe/title_missing_ram.bin')]:
 r=(Path('outputs')/p).read_bytes();print(tag)
 for a in [0x9723d0c,0x9723d0c+0x28,0x9723d0c+0x50]:print(hex(a),r[a-0x8000000:a-0x8000000+100].hex())
