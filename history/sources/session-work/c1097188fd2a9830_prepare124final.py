from pathlib import Path
s=Path('work/fallback123.py').read_text(encoding='utf-8-sig').replace('BIA_STEP123_SKIRMISH_KO_TEST.iso','BIA_STEP124_TEXT_REVIEW_KO_TEST.iso').replace('outputs/step123','outputs/step124').replace("out/'targets.json'","out/'translations.json'")
Path('work/fallback124.py').write_text(s,encoding='utf-8')
s=Path('work/verify123.py').read_text(encoding='utf-8-sig').replace('BIA_STEP123_SKIRMISH_KO_TEST.iso','BIA_STEP124_TEXT_REVIEW_KO_TEST.iso').replace('outputs/step123','outputs/step124');Path('work/verify124.py').write_text(s,encoding='utf-8')
