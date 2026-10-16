from pathlib import Path
s=Path('work/catalog112_dialogues.py').read_text(encoding='utf-8-sig').split('entries=[];targets=')[0].replace('outputs/step112','outputs/step123');s+='''
entries=[];targets={};missing={}
for file in Path('PROJECT_ROOT/extracted/PSP_GAME/USRDIR/SYSTEM').glob('*SKR*.INT'):
 for line in file.read_bytes().decode('cp1252',errors='replace').splitlines():
  if '=' not in line or line.lstrip().startswith(';'):continue
  key,val=line.split('=',1);key=key.strip();raw=val.strip();en=raw[1:-1] if raw.startswith('"') and raw.endswith('"') else raw
  if not en or not re.match(r'[A-Za-z]',en):continue
  if not(key in ['Title','Name','NameLong','SKR_Objective','SKR_Time','SKR_Defense','m_szShortDesc','m_szLongDesc','BEACONNAME','TitleString','HintCaption','MP'] or re.fullmatch(r'(?:Hint|ObjectiveHint)[0-9]+',key)):continue
  ko=lookup.get(norm(en));entries.append({'source':file.name,'key':key,'english':en,'korean':ko})
  if ko:
   targets[en]=ko
   if val.strip('"')!=en:targets[val.strip('"')]=ko
  else:missing[en]=None
(out/'source_skirmish.json').write_text(json.dumps(entries,ensure_ascii=False,indent=2),encoding='utf-8');(out/'translations.json').write_text(json.dumps(targets,ensure_ascii=False,indent=2),encoding='utf-8');(out/'missing.json').write_text(json.dumps(missing,ensure_ascii=False,indent=2),encoding='utf-8');print('sourcevalues',len(entries),'known',len(targets),'missing',len(missing));print(json.dumps(list(missing),ensure_ascii=False,indent=2))
''';Path('work/catalog123.py').write_text(s,encoding='utf-8')
