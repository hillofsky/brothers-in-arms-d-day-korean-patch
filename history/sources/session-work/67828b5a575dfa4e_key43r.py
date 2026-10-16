exec(open('work/audit43r_title.py',encoding='utf-8-sig').read().split('for name,iso')[0])
for tag,iso in [('original','Brothers in Arms - D-Day (USA) (v1.01).iso'),('patched','BIA_STAGE43Q_HINT_HEIGHT_TEST.iso')]:
 _,blob=b.iso_read_file(Path('PROJECT_ROOT')/iso,b.TARGET_MDI);st={x['index']:bytes(x['decoded']) for x in b.parse_mdi(blob)}
 for i,d in st.items():
  for mm in re.finditer(rb'START_PAGE',d):print(tag,i,hex(mm.start()),repr(d[mm.start()-40:mm.start()+80]))
