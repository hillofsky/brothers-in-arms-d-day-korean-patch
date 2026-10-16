import json,sys
from pathlib import Path
j=json.loads(Path('PROJECT_ROOT/stage42g/stage42g_token_dictionary.json').read_text(encoding='utf-8'))
print(j.keys());print('tokens',len(j['tokens']),'area',sum(t['rect']['w']*t['rect']['h'] for t in j['tokens']));print('fields',j['all_fields'][:2])
sys.path.insert(0,'work/python_deps');import psutil
for p in psutil.process_iter(['name']):
 if p.info['name']=='PPSSPPWindows64.exe':print('USER',p.pid,[x.path for x in p.open_files() if x.path.lower().endswith('.iso')])
