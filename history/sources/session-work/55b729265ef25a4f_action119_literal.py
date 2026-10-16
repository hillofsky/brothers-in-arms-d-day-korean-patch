exec(open('work/press119.py',encoding='utf-8-sig').read().split('for en in')[0])
import re
for i,d in list(st.items())+[('PRX',prx)]:
 for m in re.finditer(rb'(?<![A-Za-z])(Press|Hold|Tap|Release|Move)[ \t]*\x00',d):print(i,hex(m.start()),repr(d[m.start():m.end()]))
