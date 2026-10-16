from pathlib import Path
import struct
on=Path('work/BOOT.BIN.40k').read_bytes();off=Path('work/BIAOFF.PRX').read_bytes()
for va in [0x49b468,0x18a354,0x4eb3c,0x4e0c0]:print(hex(va),[hex(x) for x in struct.unpack_from('<8I',off,va+0x80)])
rel=[]
for p in range(0x59a558,0x59a558+0x15cdd8,8):
 a,t=struct.unpack_from('<II',off,p)
 if 0x49b468<=a<0x49b468+0x300 or a in [0x18a354,0x4eb3c,0x4e0c0]:rel.append((hex(p),hex(a),hex(t)))
print(rel)
