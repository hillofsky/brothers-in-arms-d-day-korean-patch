import struct
from pathlib import Path
b=Path('work/biaoff43.prx').read_bytes();o=struct.unpack_from('<I',b,28)[0];n=struct.unpack_from('<H',b,44)[0]
for i in range(n):print(i,[hex(x) for x in struct.unpack_from('<8I',b,o+i*32)])
