import json
from pathlib import Path
p=Path('outputs/step119/reference_audit.json');j=json.loads(p.read_text(encoding='utf-8'));count=0
for r in j['refs']:
 if r['mdi']=='ON_MEMU_O.MDI' or r['key_verified']:continue
 valid=(r['english']=='Free Look' and r['key']=='Spectating View' and r['next_fstring']=='New Objective') or (r['english']=='Checkpoint' and ((r['key']=='OracleCamTargetSelf' and r['next_fstring']=='Loading Progress') or (r['key']=='Load Checkpoint' and r['next_fstring']=='CONNECTING')))
 if valid:r['key_verified']=True;r['native_hud_display_context_verified']=True;count+=1
p.write_text(json.dumps(j,ensure_ascii=False,indent=2),encoding='utf-8');Path('outputs/step119/targets.json').write_text(json.dumps(j['targets'],ensure_ascii=False),encoding='utf-8');print('native_hud_contexts',count,'total',sum(x['key_verified'] for x in j['refs']))
s=Path('work/build117.py').read_text(encoding='utf-8-sig').replace('BIA_STEP116_TUTORIAL_CHARACTER_NAMES_KO_TEST.iso','BIA_STEP118_FONT_GUTTER_TEST.iso').replace('BIA_STEP117_NEW_OBJECTIVE_KO_TEST.iso','BIA_STEP119_ACTION_FREELOOK_CHECKPOINT_KO_TEST.iso').replace('outputs/step117_icon','outputs/step119').replace('0x54000','0x56000').replace("'STEP117'","'STEP119'");Path('work/build119.py').write_text(s,encoding='utf-8')
for old,new in [('work/fallback117.py','work/fallback119.py'),('work/verify117.py','work/verify119.py')]:
 s=Path(old).read_text(encoding='utf-8-sig').replace('BIA_STEP117_NEW_OBJECTIVE_KO_TEST.iso','BIA_STEP119_ACTION_FREELOOK_CHECKPOINT_KO_TEST.iso').replace('outputs/step117_icon','outputs/step119');Path(new).write_text(s,encoding='utf-8')
