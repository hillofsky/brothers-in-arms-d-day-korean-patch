import re,collections
from pathlib import Path
s=Path('outputs/stage43k_trace/ppsspp.log').read_text(errors='ignore');rows=re.findall(r'HUDREAD pc=([^ ]+) ra=([^ ]+) a0=([^ ]+) a1=([^ ]+) s0=([^ ]+) s1=([^ ]+) s2=([^ ]+)',s);print(collections.Counter(x[0] for x in rows));print(rows[:8]);
