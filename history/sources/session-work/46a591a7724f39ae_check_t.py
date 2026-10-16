import json,struct,hashlib
from pathlib import Path
r=Path('outputs/stage40t_validation/controls_ram.bin').read_bytes()
for a in [0x9c1af84,0x9c1d11c]:print(hex(a),struct.unpack_from('<H',r,a+0x50-0x8000000)[0],hex(struct.unpack_from('<I',r,a+0x54-0x8000000)[0]))
print('atlas?',hashlib.sha1(r[0x9d7b020-0x8000000:0x9d7b020-0x8000000+0x20000]).hexdigest())
