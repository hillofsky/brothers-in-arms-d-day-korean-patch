exec(open('work/press119.py',encoding='utf-8-sig').read().split('for en in')[0])
for en in ['Press','Hold','Tap','Release','Move']:
 needle=en.encode('utf-16le')+b'\0\0'
 print(en,[(i,hex(d.find(needle))) for i,d in st.items() if needle in d]);print('PRX',prx.find(needle))
