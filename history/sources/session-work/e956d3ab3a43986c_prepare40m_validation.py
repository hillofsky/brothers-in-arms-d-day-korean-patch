from pathlib import Path
s=Path('work/stage40l_validate.py').read_text(encoding='utf-8').replace('outputs/stage40l_validation','outputs/stage40m_validation').replace('BIA_STAGE40L_CONTROLS_UTF8_WIDTH_TEST.iso','BIA_STAGE40M_CONTROLS_COMPLETE_TEST.iso');Path('work/stage40m_validate.py').write_text(s,encoding='utf-8')
