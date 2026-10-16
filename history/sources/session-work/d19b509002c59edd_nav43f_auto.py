import time,json
from pathlib import Path
p=Path('work/nav43f_command.json')
def send(c):
 while p.exists():time.sleep(.2)
 q=p.with_name('nav43f_pending.json');q.write_text(json.dumps(c),encoding='utf-8');q.replace(p);time.sleep(5)
send({'hold_button':'start','hold_seconds':.4,'settle':2,'name':'start1'})
send({'hold_button':'start','hold_seconds':.4,'settle':2,'name':'start2'})
send({'buttons':['cross','cross','cross'],'wait':2,'name':'story'})
for i in range(4):
 send({'hold_button':'start','hold_seconds':.4,'settle':2,'name':'skip'+str(i)});time.sleep(5)
send({'name':'loaded','scan':True})
