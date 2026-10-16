exec(open('work/press119.py',encoding='utf-8-sig').read().split('for en in')[0])
import re
for i,d in list(st.items())+[('PRX',prx)]:
 for m in re.finditer(rb'(?<![A-Za-z])(?:press|hold)[^\x00]{0,15}\x00',d,re.I):
  if len(m.group())<18:print(i,hex(m.start()),repr(m.group()))
