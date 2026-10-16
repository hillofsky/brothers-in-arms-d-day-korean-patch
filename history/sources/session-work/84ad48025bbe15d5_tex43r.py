import struct
from pathlib import Path
for tag,p in [('orig','stage43r_original_probe/original_title_later_ram.bin'),('patch','stage43r_title_probe/title_post_hit_ram.bin')]:
 r=(Path('outputs')/p).read_bytes();rd=lambda a,n:r[a-0x8000000:a-0x8000000+n];f=0x972524c;ta=struct.unpack('<I',rd(f+0x488,4))[0];tex=struct.unpack('<I',rd(ta,4))[0];desc=struct.unpack('<I',rd(tex+0xc,4))[0];print(tag,hex(tex),hex(desc),rd(desc,128).hex())
