from pathlib import Path
import struct
r=Path('work/mission.DSL').read_bytes();p=0;hits=[]
while True:
 p=r.find(struct.pack('<I',128),p)
 if p<0:break
 if p>=4 and p+8<=len(r):
  v=struct.unpack_from('<III',r,p-4)
  if v[0]>>30==1 and v[2]>>30==1:hits.append((hex(p-4),*[hex(x) for x in v]))
 p+=1
print(hits)
