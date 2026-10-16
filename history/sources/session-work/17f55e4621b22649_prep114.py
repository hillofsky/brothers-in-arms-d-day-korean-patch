from pathlib import Path
s=Path('work/match113_map.py').read_text(encoding='utf-8-sig');s=s.replace('rows=[]',"r=Path('outputs/step114_menu/current_ram.bin').read_bytes()\nrows=[]").replace("Path('outputs/step113_font/map_match.json')","Path('outputs/step114_menu/map_match.json')");Path('work/match114_map.py').write_text(s,encoding='utf-8')
