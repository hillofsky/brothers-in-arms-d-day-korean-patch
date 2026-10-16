from pathlib import Path
s=Path('work/build110_pause.py').read_text(encoding='utf-8-sig').replace('SESSION_SESSION_OUTPUTS/step109/BIA_STEP109_ALL_MISSION_NAMES_KO_TEST.iso','PROJECT_ROOT/BIA_STEP112_DIALOGUE_AND_INTERACTION_KO_TEST.iso').replace('outputs/step110/BIA_STEP110_PAUSE_MENU_KO_TEST.iso','PROJECT_ROOT/BIA_STEP114_MENU_COMPLETION_KO_TEST.iso').replace('outputs/step110','outputs/step114_menu').replace('0x44000','0x50000').replace("'STEP110'","'STEP114'")
Path('work/build114_menu.py').write_text(s,encoding='utf-8')
