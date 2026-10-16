from pathlib import Path
p=Path('work/stage40j_live.py');s=p.read_text(encoding='utf-8');s=s.replace("out=root/'outputs/stage40j'","out=root/'outputs/stage40j_validation'");s=s.replace("_,b=m.load_helpers();", "m.SOURCE_ISO=Path(r'PROJECT_ROOT\BIA_STAGE40J_LOCALIZATION_KEYS_RESTORED_TEST.iso'); _,b=m.load_helpers();")
Path('work/stage40j_validate.py').write_text(s,encoding='utf-8')
s=Path('work/read_anchors.py').read_text(encoding='utf-8-sig').replace('outputs/stage40j/','outputs/stage40j_validation/')
Path('work/read_validation.py').write_text(s,encoding='utf-8')
