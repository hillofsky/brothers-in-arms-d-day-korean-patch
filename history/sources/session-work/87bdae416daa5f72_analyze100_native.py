import re,struct,json
from pathlib import Path
r=Path('outputs/step100_probe/current_ram.bin').read_bytes();found=[]
for h in re.finditer(b'ton\0',r):
 o=h.start()
 if o and 32<=r[o-1]<=126:continue
 a=o+0x8000000;refs=[]
 for x in re.finditer(re.escape(struct.pack('<I',a)),r):
  k=x.start()
  if k%4 or k+12>len(r):continue
  p,n,c=struct.unpack_from('<III',r,k)
  refs.append({'address':hex(k+0x8000000),'n':n,'cap':c,'context':r[max(0,k-20):k+24].hex()})
 found.append({'ton_address':hex(a),'context':r[max(0,o-20):o+12].hex(),'refs':refs})
print(json.dumps(found,indent=2));Path('outputs/step100_probe/ton_references.json').write_text(json.dumps(found,indent=2))
for text in ['Vierville, France','Action at Vierville','비에르빌','리스너:','XYZ']:
 for enc in ['utf-8','utf-16le']:
  n=text.encode(enc);hits=[hex(h.start()+0x8000000) for h in re.finditer(re.escape(n),r)];print(text,enc,hits[:7])
