from pathlib import Path
import collections
r=Path('outputs/stage40r_validation/controls_ram.bin').read_bytes();seq=0x8e03020
for i in range(29,36):
 a=seq+i*0x78000;d=r[a-0x8000000:a-0x8000000+0x78000];print(i,hex(a),'nonzero',sum(bool(v) for v in d),'end',hex(len(d.rstrip(b'\0'))),'top bytes',collections.Counter(d).most_common(3))
