import struct,json
from pathlib import Path
r=Path('outputs/step097_validation/chapter2_first_screen_ram.bin').read_bytes();rd=lambda a,n:r[a-0x8000000:a-0x8000000+n];report=[]
for a in [0x09a74150,0x08fc3ca0]:
 h=rd(a,0x64);gp,n,cap,tp,tn,tc,rp,rn,rc,bp,bn=struct.unpack_from('<11I',h,0x28);assert n==rn==877 and tn==2 and bn==1024
 pairs=[struct.unpack_from('<iHH',rd(rp,rn*8),i*8) for i in range(rn)]
 results={}
 for cp in map(ord,'프랑스유타해변인근베이커결국두려움을'):
  j=struct.unpack_from('<i',rd(bp+(cp&1023)*4,4))[0]
  while j>=0:
   nex,key,gi=pairs[j]
   if key==cp:results[chr(cp)]={'index':gi,'metrics':list(struct.unpack('<4IB3x',rd(gp+gi*20,20)))};break
   j=nex
  else:raise AssertionError(hex(cp))
 report.append({'font':hex(a),'glyph_count':n,'texture_count':tn,'hangul_samples':results})
Path('outputs/step097_validation/live_font_verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print('LIVE FONTS',[(x['font'],x['glyph_count']) for x in report])
