from pathlib import Path
import struct
ns={};exec(Path('work/build43l_popup.py').read_text(encoding='utf-8-sig').split('# Add relocation')[0],ns);d=ns['old'];p=struct.unpack_from('<I',d,32)[0];z,n=struct.unpack_from('<HH',d,46)
for i in range(n):
 sh=struct.unpack_from('<10I',d,p+i*z);print(i,hex(sh[1]),hex(sh[4]),hex(sh[5]))
