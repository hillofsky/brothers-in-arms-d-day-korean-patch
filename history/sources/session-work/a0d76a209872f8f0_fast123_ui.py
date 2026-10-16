from pathlib import Path
p=Path('work/audit123_ui.py');s=p.read_text(encoding='utf-8-sig').replace("    en=h.group(0)[:-1].decode('utf-8')","    en=h.group(0)[:-1].decode('utf-8')\n    if h.start() and ((65<=d[h.start()-1]<=90) or (97<=d[h.start()-1]<=122) or d[h.start()-1]==95):continue")
p.write_text(s,encoding='utf-8')
