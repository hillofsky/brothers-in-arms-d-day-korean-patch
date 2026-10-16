import struct
from pathlib import Path
for tag,p in [('orig','stage43r_original_probe/original_title_later_ram.bin'),('patch','stage43r_title_probe/title_missing_ram.bin')]:
 r=(Path('outputs')/p).read_bytes();rd=lambda a,n:r[a-0x8000000:a-0x8000000+n];f=0x972524c;page=struct.unpack('<I',rd(f+0x58,4))[0];gi=struct.unpack('<H',rd(page+160,2))[0];gp=struct.unpack('<I',rd(f+0x54,4))[0];print(tag,hex(page),gi,rd(gp+gi*24,24).hex());print('texarray',rd(struct.unpack('<I',rd(f+0x488,4))[0],16).hex())
