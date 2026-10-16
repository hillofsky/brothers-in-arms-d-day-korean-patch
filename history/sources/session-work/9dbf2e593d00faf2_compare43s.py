from pathlib import Path
import hashlib,struct
for tag,p in [('q','stage43r_title_probe/title_post_hit_ram.bin'),('s','stage43s_validation/title_prompt_verified_ram.bin')]:
 r=(Path('outputs')/p).read_bytes();print(tag,hashlib.sha1(r[0x0987d020-0x8000000:0x0987d020-0x8000000+0x20000]).hexdigest());print(r[0x973bc1c-0x8000000:0x973bc1c-0x8000000+100].hex());print('tex',r[0x95e21c0-0x8000000+0x44:0x95e21c0-0x8000000+0x58].hex())
