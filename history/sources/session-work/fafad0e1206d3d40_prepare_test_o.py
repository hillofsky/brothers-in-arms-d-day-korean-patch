from pathlib import Path
p=Path('work/test_width_machine.py').read_text(encoding='utf-8-sig').replace('outputs/stage40l','outputs/stage40o').replace('rs[6]=0x9000;rs[17]=vec;rs[18]=state','rs[6]=chars[0];rs[7]=0x9000;rs[16]=vec;rs[17]=state').replace('rs[6]==0x9000 and rs[17]==vec and rs[18]==state','rs[7]==0x9000 and rs[16]==vec and rs[17]==state').replace('18 Korean','16 Korean')
Path('work/test_width40o_machine.py').write_text(p,encoding='utf8')
