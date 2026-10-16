from pathlib import Path
import json
r=json.loads(Path('outputs/stage40s/translation_actions.json').read_text(encoding='utf8'));p={x['english']:x['korean'] for x in r};print({k:p.get(k) for k in ['Rendezvous with Destiny','Over Ste. Mere Eglise, France','Pause','PAUSE','Resume Chapter','Reload Checkpoint','Restart Chapter','Quit Chapter','Continue','Options']});print('excluded uppercase keys',sum(x['english']==x['english'].upper() for x in r))
