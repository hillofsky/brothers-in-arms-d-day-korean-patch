exec(open('work/inspect112_movie.py',encoding='utf-8-sig').read().split('for name')[0]);_,raw=b.iso_read_file(src,['PSP_GAME','USRDIR','SYSTEM','EM_1230_BOOKENDS2.TI1']);print('TI1 bytes',len(raw));Path('outputs/step112/bookends_ti1.bin').write_bytes(raw)
from PIL import Image
assert len(raw)%2048==0;Image.frombytes('RGBA',(512,len(raw)//2048),raw).save('outputs/step112/bookends_title_original.png')
