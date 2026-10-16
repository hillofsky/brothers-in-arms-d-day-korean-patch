import struct,json
from pathlib import Path
r=Path('outputs/step114_menu/current_ram.bin').read_bytes();a=0x9e6b020
print('STEP110 pause payload',repr(r[a-0x8000000+0x44000:a-0x8000000+0x44000+160]))
print('STEP112 interaction payload',repr(r[a-0x8000000+0x47000:a-0x8000000+0x47000+80]))
for text in ['Pause','Resume Chapter','Options','Restart Chapter','Quit Chapter','Back']:
 en=text.encode()+b'\0';results=[];pos=0
 while True:
  p=r.find(en,pos)
  if p<0:break
  pos=p+1;sig=struct.pack('<II',p+0x8000000,len(en));q=0
  while True:
   q=r.find(sig,q)
   if q<0:break
   if q%4==0:results.append(hex(q+0x8000000))
   q+=1
 print(text,results[:30])
