from pathlib import Path
import struct
ram=Path('outputs/stage40q_campaign/controls_ram.bin').read_bytes()
for text in ['Rendezvous','Eagles','EAGLES','Over Ste','destiny']:
 for enc in ['ascii','utf-16le']:
  p=ram.find(text.encode(enc));print(text,enc,hex(0x8000000+p) if p>=0 else None)
fonts=[]
for p in range(0,len(ram)-0x500,4):
 n=struct.unpack_from('<H',ram,p+0x50)[0]
 if n not in [151,847]:continue
 ptr=struct.unpack_from('<I',ram,p+0x54)[0]
 if not (0x08800000<=ptr<0xa000000):continue
 glyph=ram[ptr-0x8000000:ptr-0x8000000+24]
 if glyph[:2]==b'\0\0' and glyph[8:24]!=b'\0'*16:fonts.append((hex(0x8000000+p),n,hex(ptr),glyph.hex()))
print('fonts',fonts[:30])
