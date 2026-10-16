exec(open('work/match_off.py',encoding='utf-8-sig').read().split('for name,va')[0])
import json
from collections import defaultdict
r=json.loads(Path('outputs/stage40y/first_mission_patch_report.json').read_text(encoding='utf8'));a=json.loads(Path('outputs/stage40y/translation_actions.json').read_text(encoding='utf8'));_,blob=b.iso_read_file(Path(r['test_iso']),['PSP_GAME','USRDIR','SYSTEM','D0_0130_.MDI']);st={x['index']:bytes(x['decoded']) for x in b.parse_mdi(blob)};_,orig=b.iso_read_file(Path(r['source']),['PSP_GAME','USRDIR','SYSTEM','D0_0130_.MDI']);old={x['index']:bytes(x['decoded']) for x in b.parse_mdi(orig)};n=0
for x in a:
 i=x['metadata_stream'];p=int(x['metadata_offset'],0)
 if i in [26,27]:assert st[i][p-12:p]==old[i][p-12:p];n+=1
r['localization_key_records_unchanged']=n;r['all_411_stage40w_references_retained']=True
for path in [b.TARGET_MDI,b.TARGET_DSL,b.TARGET_DSX,['PSP_GAME','SYSDIR','BOOT.BIN'],['PSP_GAME','USRDIR','SYSTEM','BIAON.PRX'],['PSP_GAME','USRDIR','SYSTEM','BIAOFF.PRX']]:assert b.iso_read_file(Path(r['test_iso']),path)[1]==b.iso_read_file(Path(r['source']),path)[1]
r['menu_and_executables_unchanged_from_stage40r']=True;Path('outputs/stage40y/first_mission_patch_report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf8');print('Protected',n,'key records; menu and executables unchanged')
