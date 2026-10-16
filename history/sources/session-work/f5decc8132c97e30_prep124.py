import json,re,ast
from pathlib import Path
out=Path('outputs/step124');out.mkdir(exist_ok=True);targets={}
pat=re.compile(r'(?:맥|하세이|해세이|해시|하세이|하세이)\s*(?:상사|중사|병장|하사)|해시|해세이')
def visit(x):
 if isinstance(x,dict):
  for k,v in x.items():visit(k);visit(v)
 elif isinstance(x,list):
  for v in x:visit(v)
 elif isinstance(x,str) and len(x)<4096 and pat.search(x) and not any(c in x for c in ['{','\\\\']):
  ko=pat.sub('맥 중사',x)
  if x!=ko:targets[x]=ko
for p in Path('outputs').glob('step*/*.json'):
 if p.stat().st_size>30_000_000:continue
 try:visit(json.loads(p.read_text(encoding='utf-8-sig')))
 except (ValueError,UnicodeError):pass
old=json.loads(Path('outputs/step112/interaction_translations.json').read_text(encoding='utf-8'))
for en,ko in old.items():
 if en.startswith(('German ','US ')) and len(en)<65:
  ko=ko.replace('판처파우스트','Panzerfaust').replace('바주카','Bazooka').replace('스프링필드','Springfield').replace('45구경','.45')
  targets[en]=ko;targets[en+'.']=ko+'.'
  if old[en]!=ko:targets[old[en]]=ko
# No identifier keys: all candidates still require real FString reference validation.
(out/'translations.json').write_text(json.dumps(targets,ensure_ascii=False,indent=2),encoding='utf-8')
s=Path('work/audit123_ui.py').read_text(encoding='utf-8-sig').replace('BIA_STEP120_MAC_NAME_KO_TEST.iso','BIA_STEP123_SKIRMISH_KO_TEST.iso').replace('outputs/step123_ui','outputs/step124').replace('len(en)+1','len(en.encode())+1')
Path('work/audit124.py').write_text(s,encoding='utf-8')
print('targets',len(targets));print('\n'.join(k for k in targets if k.startswith('해시'))[:1500])
