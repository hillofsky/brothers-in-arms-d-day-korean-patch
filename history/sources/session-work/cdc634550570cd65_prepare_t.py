from pathlib import Path
p=Path('work/build_firstmission40s.py').read_text(encoding='utf-8-sig').replace('outputs/stage40s','outputs/stage40t').replace('BIA_STAGE40S_FIRST_MISSION_KOREAN_TEST','BIA_STAGE40T_CAMPAIGN_FONT_ISOLATION_TEST')
p=p.replace("for i,dec in st.items():\n for match in re.finditer", "for i,dec in []:\n for match in re.finditer")
Path('work/build_firstmission40t.py').write_text(p,encoding='utf8')
