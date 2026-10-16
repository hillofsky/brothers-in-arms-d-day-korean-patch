exec(open('work/audit101_loading.py',encoding='utf-8').read().split('allrefs=[]')[0])
for name in ['MEMORYSTICK.INT','LOCALIZE.INT','NEWLOCALIZE.INT']:
 _,data=b.iso_read_file(src,['PSP_GAME','USRDIR','SYSTEM',name]); print(name,repr(data[:180]));print(repr(data[data.find(b'LOAD_PROFILE='):data.find(b'LOAD_PROFILE=')+180]))
