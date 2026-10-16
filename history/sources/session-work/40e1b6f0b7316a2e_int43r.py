exec(open('work/audit43r_title.py',encoding='utf-8-sig').read().split('for name,iso')[0])
for f in ['LOCALIZE.INT','NEWLOCALIZE.INT']:
 _,d=b.iso_read_file(Path('PROJECT_ROOT/BIA_STAGE43Q_HINT_HEIGHT_TEST.iso'),['PSP_GAME','USRDIR','SYSTEM',f]);print(f,d[:220])
