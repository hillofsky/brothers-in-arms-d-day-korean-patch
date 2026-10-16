import struct,json,re
from pathlib import Path
out=Path('outputs/step106_font');r=(out/'current_ram.bin').read_bytes();rd=lambda a,n:r[a-0x8000000:a-0x8000000+n];reports=[]
for m in re.finditer(re.escape(struct.pack('<I',0x08d68be8)),r):
 a=0x8000000+m.start()
 if a%4:continue
 try:
  h=rd(a,0x64);gp,n,cap,tp,tn,tc,rp,rn,rc,bp,bn=struct.unpack_from('<11I',h,0x28)
  if not(11<=n<=1500 and n==rn and 1<=tn<=3):continue
  textures=struct.unpack('<'+'I'*tn,rd(tp,tn*4));detail=[]
  for t in textures:
   raw=rd(t,0xf0);detail.append({'pointer':hex(t),'header_hex':raw.hex(),'dimensions':list(struct.unpack_from('<5I',raw,0x44))})
  reports.append({'font':hex(a),'n':n,'glyphs':hex(gp),'textures':detail,'remap':hex(rp),'buckets':hex(bp)})
 except Exception:pass
(out/'live_fonts.json').write_text(json.dumps(reports,indent=2));print(json.dumps(reports,indent=2)[:6500])
