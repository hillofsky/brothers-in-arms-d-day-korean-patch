from pathlib import Path
s=Path('work/match113_map.py').read_text(encoding='utf-8-sig').replace('rows=[]',"r=Path('outputs/step121_font/current_ram.bin').read_bytes()\nrows=[]").replace("Path('outputs/step113_font/map_match.json')","Path('outputs/step121_font/map_match.json')");Path('work/match121_map.py').write_text(s,encoding='utf-8')
