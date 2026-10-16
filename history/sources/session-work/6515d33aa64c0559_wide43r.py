import re,struct,json
from pathlib import Path
r=Path('outputs/stage43r_title_probe/title_missing_ram.bin').read_bytes()
for n in ['START 버튼을 누르십시오'.encode('utf-16le'),b''.join(bytes([x,0]) for x in 'START 버튼을 누르십시오'.encode()),'Press START button'.encode('utf-16le')]:
 for h in re.finditer(re.escape(n),r):
  a=h.start()+0x8000000;print(hex(a),len(n));
  for x in re.finditer(re.escape(struct.pack('<I',a)),r):print('REF',hex(x.start()+0x8000000),r[x.start():x.start()+16].hex())
