import struct
from pathlib import Path
b=Path('work/biaoff43.prx').read_bytes();off=struct.unpack_from('<I',b,32)[0];size,num,idx=struct.unpack_from('<HHH',b,46);s=[struct.unpack_from('<10I',b,off+i*size) for i in range(num)];a=s[idx];strings=b[a[4]:a[4]+a[5]]
for a in s:
 name=strings[a[0]:].split(b'\0')[0].decode();print(name,'VA',hex(a[3]),'file',hex(a[4]),'size',hex(a[5]),'flags',hex(a[2]))
