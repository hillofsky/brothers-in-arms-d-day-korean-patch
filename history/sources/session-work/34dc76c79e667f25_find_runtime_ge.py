from pathlib import Path
import struct
r=Path('outputs/stage40q_campaign/controls_ram.bin').read_bytes();p=0;needle=bytes.fromhex('070800b8000000cb010000c2')
while True:
 p=r.find(needle,p)
 if p<0:break
 print('runtime',hex(0x8000000+p-8),[hex(x) for x in struct.unpack_from('<12I',r,p-8)]);p+=1
DSL=Path('work/mission.DSL').read_bytes()
for p in [0x45c3a4,0x4acee4]:
 print('srcGE',hex(p-8));print([hex(x) for x in struct.unpack_from('<12I',DSL,p-8)])
 for value in [0x80694dc0,0x40694dc0,0x40000dc0,0x40004dc0,0x405dc240]:
  data=struct.pack('<I',value);at=DSL.find(data);print(hex(value),hex(at))
