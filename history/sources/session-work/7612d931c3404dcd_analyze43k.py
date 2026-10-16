import re,collections
from pathlib import Path
s=Path('outputs/stage43k_trace/ppsspp.log').read_text(errors='ignore')
for label in ['RFONT','UWIDTH','HUDCP']:
 rows=re.findall(label+r' cp=([0-9a-f]+) font=([0-9a-f]+)([^\r\n]*)',s)
 print(label,'count',len(rows),'fonts',collections.Counter(f for cp,f,x in rows),'raw examples',[row for row in rows if int(row[0],16)<0xac00 or int(row[0],16)>0xd7a3][:14])
