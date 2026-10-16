exec(open('work/audit43r_title.py',encoding='utf-8-sig').read().split('for name,iso')[0])
base=0x08e03020;stride=0x78000
for name,iso in [('orig','Brothers in Arms - D-Day (USA) (v1.01).iso'),('patch','BIA_STAGE43Q_HINT_HEIGHT_TEST.iso')]:
 _,blob=b.iso_read_file(Path('PROJECT_ROOT')/iso,b.TARGET_MDI);st={x['index']:bytes(x['decoded']) for x in b.parse_mdi(blob)}
 needle=b'Press START button' if name=='orig' else 'START 버튼을 누르십시오'.encode();loc=[(i,d.find(needle)) for i,d in st.items() if needle in d]
 for i,o in loc:
  ptr=base+i*stride+o;print(name,'text',hex(ptr))
  for j,d in st.items():
   for hit in re.finditer(re.escape(struct.pack('<I',ptr)),d):print('REF',j,hex(hit.start()),d[max(0,hit.start()-24):hit.start()+32].hex())
ram=Path('outputs/stage43r_title_probe/title_missing_ram.bin').read_bytes()
for needle in ['START 버튼을 누르십시오'.encode(),b'Press START button']:
 for hit in re.finditer(re.escape(needle),ram):
  ptr=0x08000000+hit.start();print('RAMTEXT',hex(ptr));
  for ref in re.finditer(re.escape(struct.pack('<I',ptr)),ram):print('RAMREF',hex(0x08000000+ref.start()),ram[max(0,ref.start()-16):ref.start()+24].hex())
