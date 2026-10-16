from pathlib import Path
s=Path('work/audit110_pause.py').read_text(encoding='utf-8-sig').replace("SESSION_SESSION_OUTPUTS/step109/BIA_STEP109_ALL_MISSION_NAMES_KO_TEST.iso","PROJECT_ROOT/BIA_STEP112_DIALOGUE_AND_INTERACTION_KO_TEST.iso").replace("outputs/step110","outputs/step114_menu").replace("    if h.start() and d[h.start()-1] not in (0,255):continue\n",'').replace("'Resume Game': '게임 계속하기'","'Resume Game': '게임 계속하기', 'Restart Chapter':'챕터 재시작','Quit Chapter':'챕터 종료','Completed!':'완료!' ")
Path('work/audit114_menu.py').write_text(s,encoding='utf-8')
