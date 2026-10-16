exec(open('work/audit100_vierville.py',encoding='utf-8-sig').read().split('hits=[]')[0]+'hits=[]')
for tag,iso in [('099',src),('079',Path('PROJECT_ROOT/BIA_STAGE79_COMPILED967_STRUCTURAL_TEST.iso')),('original',Path('PROJECT_ROOT/Brothers in Arms - D-Day (USA) (v1.01).iso'))]:
 _,bb=b.iso_read_file(iso,['PSP_GAME','USRDIR','SYSTEM','D1_0900_.MDI']);ss={x['index']:bytes(x['decoded']) for x in b.parse_mdi(bb)}
 for i,o in [(11,0x5b36),(24,0x49aa6),(24,0x49b26),(24,0x4a28a)]:
  d=ss[i];print(tag,i,hex(o),repr(d[o-120:o+32]));print('HEX',d[o-36:o+8].hex())
