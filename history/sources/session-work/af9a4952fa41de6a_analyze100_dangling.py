import json,struct,re
from pathlib import Path
r=Path('outputs/step100_probe/current_ram.bin').read_bytes();inv=json.loads(Path('outputs/step098/inventory.json').read_text());row=next(x for x in inv if x['mdi']=='D1_0900_.MDI')
for f in row['fonts']:
 a=int(f['runtime'],16);print('FONT',f['runtime'],r[a-0x8000000:a-0x8000000+0x64].hex())
res=[]
for h in re.finditer(b'ton\0',r):
 o=h.start()
 if o%16!=12 or not 0x980000<=o<=0x1c00000:continue
 ptr=o-12+0x8000000;refs=[]
 for m in re.finditer(re.escape(struct.pack('<I',ptr)),r):
  k=m.start()
  if k%4 or k+12>len(r):continue
  p,n,c=struct.unpack_from('<III',r,k)
  if (0<n<=4096 and n<=c<=0x100000) or (ptr<=n<=ptr+4096 and n<=c<=ptr+0x10000):refs.append({'address':hex(k+0x8000000),'values':[hex(p),hex(n),hex(c)],'context':r[max(0,k-24):k+36].hex()})
 if refs:res.append({'data':hex(ptr),'contents':r[o-12:o+4].hex(),'refs':refs})
print(json.dumps(res,indent=2));Path('outputs/step100_probe/suspect_string_refs.json').write_text(json.dumps(res,indent=2))
