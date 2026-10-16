from pathlib import Path
p=Path('work/build_firstmission40v.py').read_text(encoding='utf-8-sig').replace('outputs/stage40v','outputs/stage40w').replace('BIA_STAGE40V_FIRST_MISSION_UI_TEST','BIA_STAGE40W_FIRST_MISSION_UI_TEST')
p=p.replace('  for ri,ro in refLOCAL_PATH   if ro >= 12:', '  for ri,ro in refLOCAL_PATH   if ri not in [26,27,13]:continue\n   if ro >= 12:')
Path('work/build_firstmission40w.py').write_text(p,encoding='utf8')
