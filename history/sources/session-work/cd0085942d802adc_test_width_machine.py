import struct
from pathlib import Path
code=Path('outputs/stage40l/utf8_width_helper.bin').read_bytes()
def run(chars,end_units=None):
 mem={};rs=[0]*32;beg=0x1000;vec=0x2000;state=0x3000
 def put(p,v,n):
  for j in range(n):mem[p+j]=(v>>(8*j))&255
 def get(p,n):return sum(mem[p+j]<<(8*j) for j in range(n))
 for j,v in enumerate(chars):put(beg+2*j,v,2)
 put(vec,beg,4);put(vec+4,beg+2*(len(chars) if end_units is None else end_units),4);put(state+0x38,0,4)
 rs[4]=0x4000;rs[5]=chars[0];rs[6]=0x9000;rs[17]=vec;rs[18]=state;rs[31]=0x12345678;pc=0
 for _ in range(200):
  w=struct.unpack_from('<I',code,pc)[0];op=w>>26;s=(w>>21)&31;t=(w>>16)&31;d=(w>>11)&31;sh=(w>>6)&31;f=w&63;im=w&65535;sg=im if im<32768 else im-65536;nxt=pc+4
  if op==0:
   if f==8: assert rs[s]==0x9000;break
   if f==0:rs[d]=rs[t]<<sh
   elif f==33:rs[d]=rs[s]+rs[t]
   elif f==37:rs[d]=rs[s]|rs[t]
   elif f==43:rs[d]=int(rs[s]<rs[t])
   else:raise ValueError(hex(w))
  elif op in (4,5):
   yes=(rs[s]==rs[t]) if op==4 else (rs[s]!=rs[t]);assert struct.unpack_from('<I',code,pc+4)[0]==0
   nxt=pc+4+sg*4 if yes else pc+8
  elif op==9:rs[t]=rs[s]+sg
  elif op==11:rs[t]=int(rs[s]<(sg&0xffffffff))
  elif op==12:rs[t]=rs[s]&im
  elif op==14:rs[t]=rs[s]^im
  elif op==35:rs[t]=get((rs[s]+sg)&0xffffffff,4)
  elif op==37:rs[t]=get((rs[s]+sg)&0xffffffff,2)
  elif op==43:put((rs[s]+sg)&0xffffffff,rs[t],4)
  else:raise ValueError(hex(w))
  rs=[v&0xffffffff for v in rs];rs[0]=0;pc=nxt
 else:raise RuntimeError('No tail call')
 assert rs[4]==0x4000 and rs[6]==0x9000 and rs[17]==vec and rs[18]==state and rs[31]==0x12345678
 return rs[5],get(state+0x38,4)
cases=[([65],None,65,0),([0xc720],None,0xc720,0),([0xe9,65],None,0xe9,0),([0xc2,0xa2],None,0xa2,1),([0xc3,0xa9],None,0xe9,1),([0xc0,0x80],None,0xc0,0),([0xec,0x84,0xa0],None,ord('선'),2),([0xed,0x83,0x9d],None,ord('택'),2),([0xe0,0xa0,0x80],None,0x800,2),([0xed,0xa0,0x80],None,0xed,0),([0xe0,0x80,0x80],None,0xe0,0),([0xec,0x41,0xa0],None,0xec,0),([0xec,0x84,0x41],None,0xec,0),([0xec,0x84,0xa0],2,0xec,0),([0xc3,0xa9],1,0xc3,0),([0xf0,0x90,0x80,0x80],None,0xf0,0)]
for text,end,cp,advance in cases:assert run(text,end)==(cp,advance),(text,run(text,end))
for ch in '유형조준반전보조표준고급취소선택':
 units=list(ch.encode());assert run(units)==(ord(ch),len(units)-1)
print('PASS: 16 boundary/format/ABI cases and 18 Korean glyph cases executed from helper machine code')
