from pathlib import Path
s=Path('work/runtime123_smoke.py').read_text(encoding='utf-8-sig').replace('step123_runtime','step124_runtime').replace('nav123_command','nav124_command').replace('BIA_STEP123_SKIRMISH_KO_TEST.iso','BIA_STEP124_TEXT_REVIEW_KO_TEST.iso').replace('26442','26444')
Path('work/runtime124_smoke.py').write_text(s,encoding='utf-8')
