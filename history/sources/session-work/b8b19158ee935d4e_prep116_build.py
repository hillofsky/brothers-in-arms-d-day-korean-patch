import json
from pathlib import Path
o=Path('outputs/step116');a=json.loads((o/'reference_audit.json').read_text(encoding='utf-8'));d=json.loads(Path('outputs/step112/available_translations.json').read_text(encoding='utf-8'));actors={en.split(':')[0]:ko.split(':')[0] for en,ko in d.items() if ':' in en and ':' in ko};nm=json.loads((o/'name_translations.json').read_text(encoding='utf-8'))
for en in nm:
 surname=en.rsplit(' ',1)[-1]
 if surname in actors:nm[en]=actors[surname]+' '+nm[en].rsplit(' ',1)[-1]
for en,ko in nm.items():a['targets'][en]=ko
for r in a['refs']:
 if r['english'] in nm:r['korean']=nm[r['english']]
(o/'reference_audit.json').write_text(json.dumps(a,ensure_ascii=False,indent=2),encoding='utf-8');(o/'translations.json').write_text(json.dumps(a['targets'],ensure_ascii=False,indent=2),encoding='utf-8');(o/'name_translations.json').write_text(json.dumps(nm,ensure_ascii=False,indent=2),encoding='utf-8')
s=Path('work/build114_menu.py').read_text(encoding='utf-8-sig').replace('BIA_STEP112_DIALOGUE_AND_INTERACTION_KO_TEST.iso','BIA_STEP115_FONT_UV_INSET_TEST.iso').replace('BIA_STEP114_MENU_COMPLETION_KO_TEST.iso','BIA_STEP116_TUTORIAL_CHARACTER_NAMES_KO_TEST.iso').replace('outputs/step114_menu','outputs/step116').replace('0x50000','0x52000').replace("'STEP114'","'STEP116'");Path('work/build116.py').write_text(s,encoding='utf-8')
