from pathlib import Path
s=Path('work/audit119.py').read_text(encoding='utf-8-sig').replace("'Hold':'길게 누르기'","'Hold':'길게 누르기','press':'누르기','hold':'누르고 있기','press and hold':'길게 누르기','tap':'짧게 누르기','release':'놓기','move':'이동'");Path('work/audit119.py').write_text(s,encoding='utf-8')
