import csv,json,re,unicodedata
from pathlib import Path
out=Path('outputs/step112');out.mkdir(exist_ok=True)
def norm(s):return re.sub(r'\s+',' ',s.replace('’',"'").replace('‘',"'").replace('“','"').replace('”','"')).strip().strip('"')
lookup={}
for file in [Path('PROJECT_ROOT/translation/text_master.tsv')]+list(Path('PROJECT_ROOT/incoming').glob('**/*KO_reviewed.tsv')):
 for row in csv.DictReader(file.open(encoding='utf-8-sig'),delimiter='\t'):
  en=row.get('source_text','');ko=row.get('ko_review') or row.get('ko_current') or ''
  if en and ko:lookup[norm(en)]=ko
for file in Path('PROJECT_ROOT/incoming').glob('**/translations_STEP*.json'):
 try:rows=json.loads(file.read_text(encoding='utf-8-sig')).get('translations',[])
 except Exception:continue
 for row in rows:
  en=row.get('source_text','');ko=row.get('ko_review') or row.get('ko_current') or ''
  if en and ko:lookup[norm(en)]=ko
entries=[];targets={};missing={}
for file in Path('PROJECT_ROOT/extracted/PSP_GAME/USRDIR/SYSTEM').glob('D*.INT'):
 section=''
 for line in file.read_bytes().decode('cp1252',errors='replace').splitlines():
  if line.startswith('['):section=line.strip('[]');continue
  if '=' not in line or section!='LocalizedStrings':continue
  key,val=line.split('=',1);en=val.strip();en=en[1:-1] if en.startswith('"') and en.endswith('"') else en
  if not re.match(r'[A-Za-z][A-Za-z .\'\-]*:\s',en):continue
  ko=lookup.get(norm(en));entries.append({'source':file.name,'key':key,'english':en,'korean':ko})
  if ko:targets[en]=ko
  else:missing[en]=None
(out/'source_dialogues.json').write_text(json.dumps(entries,ensure_ascii=False,indent=2),encoding='utf-8');(out/'available_translations.json').write_text(json.dumps(targets,ensure_ascii=False,indent=2),encoding='utf-8');(out/'missing_translation.json').write_text(json.dumps(missing,ensure_ascii=False,indent=2),encoding='utf-8');print('dialogue occurrences',len(entries),'unique with translations',len(targets),'missing translations',len(missing));print(json.dumps(list(missing)[:20],indent=2))
