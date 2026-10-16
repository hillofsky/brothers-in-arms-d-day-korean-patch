import re,struct,json
from pathlib import Path
r=Path('outputs/stage43r_original_probe/original_title_later_ram.bin').read_bytes()
for n in [b'Press START button','Press START button'.encode('utf-16le')]:
 for h in re.finditer(re.escape(n),r):
  a=h.start()+0x8000000;print(hex(a),len(n));
  for x in re.finditer(re.escape(struct.pack('<I',a)),r):print('REF',hex(x.start()+0x8000000))
