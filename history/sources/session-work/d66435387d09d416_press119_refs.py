exec(open('work/press119.py',encoding='utf-8-sig').read().split('for en in')[0])
en=b'press\0';base=0x8e03020;stride=0x78000
for si,d in st.items():
 p=0
 while True:
  p=d.find(en,p)
  if p<0:break
  sig=struct.pack('<II',base+si*stride+p,len(en));p+=1
  for i,v in st.items():
   for h in __import__('re').finditer(__import__('re').escape(sig),v):
    o=h.start()
    if o%4 or o<12:continue
    a,n,c=struct.unpack_from('<III',v,o-12);ii,oo=divmod(a-base,stride);key=st[ii][oo:oo+n] if ii in st and n<200 else b'';print(i,hex(o),repr(key))
