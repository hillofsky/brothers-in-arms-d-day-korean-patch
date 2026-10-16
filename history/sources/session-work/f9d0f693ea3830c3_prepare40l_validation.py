from pathlib import Path
s=Path('work/stage40l_live.py').read_text(encoding='utf-8').replace('outputs/stage40l','outputs/stage40l_validation').replace('BIA_STAGE40K_CONTROLS_FONT_TEST.iso','BIA_STAGE40L_CONTROLS_UTF8_WIDTH_TEST.iso');s=s.replace("condition='a1 >= 0x80'", "condition=c.get('trace_condition','a1 >= 0x80')");Path('work/stage40l_validate.py').write_text(s,encoding='utf-8')
