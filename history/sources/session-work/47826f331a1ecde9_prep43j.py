from pathlib import Path
s=Path('work/stage43i_live.py').read_text(encoding='utf-8').replace('stage43i_validation','stage43j_trace').replace('nav43i_command','nav43j_command').replace("condition='a0 >= 0xAC00 && a0 <= 0xD7A3'","condition='a0 >= 0x80'");Path('work/stage43j_live.py').write_text(s,encoding='utf-8')
s=Path('work/nav43i_auto.py').read_text(encoding='utf-8').replace('nav43i','nav43j').replace('stage43i_validation','stage43j_trace');Path('work/nav43j_auto.py').write_text(s,encoding='utf-8')
