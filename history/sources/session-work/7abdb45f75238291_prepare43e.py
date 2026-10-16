from pathlib import Path
s=Path('work/stage43b_live.py').read_text(encoding='utf-8-sig');s=s.replace('stage43b_trace','stage43e_validation').replace('nav43b_command.json','nav43e_command.json').replace('BIA_STAGE43A_FIRST_CAMPAIGN_KO_TEST.iso','BIA_STAGE43E_CAMPAIGN_UTF8_RENDER_TEST.iso');Path('work/stage43e_live.py').write_text(s,encoding='utf-8')
