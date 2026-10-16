from pathlib import Path
s=Path('work/capture117_icon.py').read_text(encoding='utf-8-sig').replace('outputs/step117_icon','outputs/step118_font');Path('work/capture118_font.py').write_text(s,encoding='utf-8')
