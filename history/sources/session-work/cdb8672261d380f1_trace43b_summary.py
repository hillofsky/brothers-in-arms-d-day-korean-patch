import re,collections
from pathlib import Path
s=Path('outputs/stage43b_trace/ppsspp.log').read_text(encoding='utf-8',errors='replace')
c=collections.Counter()
for f,v,ra,s2 in re.findall(r'BIA40Y a0=(\w+) a1=(\w+) ra=(\w+) s0=\w+ s1=\w+ s2=(\w+)',s): c[(f,ra,'byte' if int(v,16)<256 else 'unicode',s2)]+=1
for k,v in c.items():print(k,v)

