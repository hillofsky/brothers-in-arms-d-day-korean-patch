import struct
from pathlib import Path
for tag,p in [('orig','stage43r_original_probe/original_title_later_ram.bin'),('patch','stage43r_title_probe/title_missing_ram.bin')]:
 r=(Path('outputs')/p).read_bytes();rd=lambda a,n:r[a-0x8000000:a-0x8000000+n];p=struct.unpack('<I',rd(0x973bc80,4))[0];print(tag,hex(p),rd(p,100).hex());q=struct.unpack('<I',rd(p,4))[0];print('q',hex(q),rd(q,100).hex())
