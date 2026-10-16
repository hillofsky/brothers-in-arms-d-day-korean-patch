from pathlib import Path
s=Path('work/stage40k_live.py').read_text(encoding='utf-8').replace('outputs/stage40k','outputs/stage40k_validation').replace('BIA_STAGE40J_LOCALIZATION_KEYS_RESTORED_TEST.iso','BIA_STAGE40K_CONTROLS_FONT_TEST.iso');Path('work/stage40k_validate.py').write_text(s,encoding='utf-8')
