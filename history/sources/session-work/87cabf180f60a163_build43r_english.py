exec(open('work/audit43r_title.py',encoding='utf-8-sig').read().split('for name,iso')[0])
import shutil
src=Path('PROJECT_ROOT/BIA_STAGE43Q_HINT_HEIGHT_TEST.iso');dst=Path('PROJECT_ROOT/BIA_STAGE43R_TITLE_ENGLISH_PROBE.iso');_,blob=b.iso_read_file(src,b.TARGET_MDI);st={x['index']:bytes(x['decoded']) for x in b.parse_mdi(blob)};d=bytearray(st[23]);o=d.index('START 버튼을 누르십시오'.encode());old='START 버튼을 누르십시오'.encode()+b'\0';d[o:o+len(old)]=(b'Press START button\0').ljust(len(old),b'\0');new=b.rebuild_mdi(blob,{23:bytes(d)});shutil.copy2(src,dst);b.append_iso_file_and_repoint(dst,b.TARGET_MDI,new);print(dst)
p=Path('work/stage43r_live.py').read_text(encoding='utf-8-sig');p=p.replace('stage43r_title_probe','stage43r_english_probe').replace('nav43r_command','nav43re_command').replace('BIA_STAGE43Q_HINT_HEIGHT_TEST.iso','BIA_STAGE43R_TITLE_ENGLISH_PROBE.iso');Path('work/stage43re_live.py').write_text(p,encoding='utf-8')
Path('work/nav43r_command.json').write_text('{"quit":true}')
