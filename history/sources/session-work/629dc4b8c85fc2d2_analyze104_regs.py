import json,struct,sys
from pathlib import Path
sys.path.insert(0,'work/python_deps');from capstone import *
out=Path('outputs/step104_user_repro');j=json.loads((out/'paused_088b9c8c_regs.json').read_text());print(str(j)[:400]);r=(out/'paused_088b9c8c_ram.bin').read_bytes();c=j['categories'][0];print(c.keys());print(c)
