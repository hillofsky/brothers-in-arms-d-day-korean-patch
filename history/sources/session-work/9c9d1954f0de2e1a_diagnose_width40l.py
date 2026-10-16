import struct,re,collections,json
from pathlib import Path
h=Path('outputs/stage40l/utf8_width_helper.bin').read_bytes();r=Path('outputs/stage40l_validation/controls_ram.bin').read_bytes();actual=r[0x08cc4480-0x08000000:0x08cc4480-0x08000000+len(h)]
for off in range(0,len(h),4):
 a=struct.unpack_from('<I',actual,off)[0];e=struct.unpack_from('<I',h,off)[0]
 if a!=e:print(hex(off),hex(e),hex(a))
g=collections.defaultdict(collections.Counter)
for line in Path('outputs/stage40l_validation/ppsspp.log').read_text(encoding='utf-8',errors='replace').splitlines():
 if 'BIA40K' in line:
  d=dict(re.findall('(ra|a1|s[0-7]|sp)=([0-9a-f]+)',line));
  if not all(k in d for k in ['ra','sp','s1','s2','a1']):continue
  g[(d['ra'],d['sp'],d['s1'],d['s2'])][int(d['a1'],16)]+=1
for k,v in g.items():print(k,'count',sum(v.values()),'byte',sum(n for a,n in v.items() if 128<=a<256),'hangul',sum(n for a,n in v.items() if 0xac00<=a<=0xd7a3),'sample',[hex(a) for a in v][:15])

