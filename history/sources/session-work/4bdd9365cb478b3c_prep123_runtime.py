from pathlib import Path
s=Path('work/runtime112_smoke.py').read_text(encoding='utf-8-sig').replace('BIA_STEP112_DIALOGUE_AND_INTERACTION_KO_TEST.iso','BIA_STEP123_SKIRMISH_KO_TEST.iso').replace('outputs/step112_runtime','outputs/step123_runtime').replace('nav112_command.json','nav123_command.json');Path('work/runtime123_smoke.py').write_text(s,encoding='utf-8')
