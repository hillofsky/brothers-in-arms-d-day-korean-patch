import struct,json
from pathlib import Path
r=Path('outputs/stage40q_campaign/controls_ram.bin').read_bytes();base=0x08000000;target=0x09c8be40;hits=[]
def u(p):return struct.unpack_from('<I',r,p-base)[0]
for off in range(0,len(r)-0x80,4):
 table=struct.unpack_from('<I',r,off+0x6c)[0];count=struct.unpack_from('<I',r,off+0x70)[0]
 if not(0x08800000<=table<=0x0a000000-12*max(1,count) and 1<=count<=3000):continue
 db=struct.unpack_from('<I',r,off+4)[0]
 if not(0x08000000<=db<0x0a000000):continue
 delta=(target-db)&0xffffffff
 if not(delta<0x1000000):continue
 for j in range(count):
  ptr=table+j*12;e0,e1,e2=struct.unpack_from('<III',r,ptr-base)
  if (db+e0)&0x1fffffff==target:
   hits.append({'object':hex(base+off),'data_base':hex(db),'base2':hex(u(base+off+0x34)),'entry':hex(ptr),'words':[hex(e0),hex(e1),hex(e2)]})
print(json.dumps(hits));Path('outputs/stage40q_campaign/mission_relocation_found.json').write_text(json.dumps(hits,indent=2))
