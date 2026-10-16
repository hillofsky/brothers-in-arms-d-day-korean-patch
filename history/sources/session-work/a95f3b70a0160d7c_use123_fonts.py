from pathlib import Path
p=Path('work/build123.py');s=p.read_text(encoding='utf-8-sig').replace("src=Path('PROJECT_ROOT/BIA_STEP120_MAC_NAME_KO_TEST.iso')","src=Path('PROJECT_ROOT/working/step123_font_source.iso')").replace('assert not dst.exists();','assert dst.exists();');p.write_text(s,encoding='utf-8')
