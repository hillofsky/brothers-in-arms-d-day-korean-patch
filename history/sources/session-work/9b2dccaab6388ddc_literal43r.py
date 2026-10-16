exec(open('work/audit43r_title.py',encoding='utf-8-sig').read().split('for name,iso')[0])
for f in [['PSP_GAME','SYSDIR','BOOT.BIN'],['PSP_GAME','USRDIR','SYSTEM','BIAON.PRX']]:
 for tag,iso in [('original','Brothers in Arms - D-Day (USA) (v1.01).iso'),('patched','BIA_STAGE43Q_HINT_HEIGHT_TEST.iso')]:
  _,d=b.iso_read_file(Path('PROJECT_ROOT')/iso,f)
  for n in [b'Press START button','Press START button'.encode('utf-16le'),'START 버튼을 누르십시오'.encode()]:
   for h in re.finditer(re.escape(n),d):print(f[-1],tag,hex(h.start()),repr(d[h.start()-20:h.start()+80]))
