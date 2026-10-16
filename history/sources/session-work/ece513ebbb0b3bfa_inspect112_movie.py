exec(open('work/audit112_dialogues.py',encoding='utf-8-sig').read().split('source_pattern=')[0])
for name in ['EM_1230_BOOKENDS2.ST1','SUBTITLEHASHMAP.INI','GBXINVENTORY.INT']:
 _,raw=b.iso_read_file(src,['PSP_GAME','USRDIR','SYSTEM',name]);print(name,len(raw),repr(raw[:280]))
