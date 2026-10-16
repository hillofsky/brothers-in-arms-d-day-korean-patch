import struct,re,json
from pathlib import Path
r=Path('outputs/step117_icon/current_ram.bin').read_bytes();rd=lambda a,n:r[a-0x8000000:a-0x8000000+n] if 0x8000000<=a<0xa000000 else b'';rows=[]
for m in re.finditer(re.escape(struct.pack('<I',0x8d70f48)),r):
 a=0x8000000+m.start()
 if a%4 or len(rd(a,240))<240:continue
 h=rd(a,240);w,hh=struct.unpack_from('<II',h,0x48);p=struct.unpack_from('<I',h,0xe0)[0]
 if w not in [16,32,64,128,256,512] or hh not in [16,32,64,128,256,512] or len(rd(p,24))!=24:continue
 desc=rd(p,24);owner=struct.unpack_from('<I',desc,16)[0]
 if owner!=a:rows.append({'texture':hex(a),'size':[w,hh],'render_ptr':hex(p),'owner':hex(owner),'vtable':hex(struct.unpack_from('<I',desc)[0])})
Path('outputs/step117_icon/renderer_owner_audit.json').write_text(json.dumps(rows,indent=2));print('mismatches',len(rows));print(json.dumps(rows[:20]))
