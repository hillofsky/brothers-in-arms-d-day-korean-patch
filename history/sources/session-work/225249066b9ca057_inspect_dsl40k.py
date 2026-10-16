import importlib.util,struct
from pathlib import Path
s=importlib.util.spec_from_file_location('m','PROJECT_ROOT/bia_stage40i_tools/bia_stage40i_actual_resource_trace.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);_,b=m.load_helpers()
iso=Path('PROJECT_ROOT/BIA_STAGE40J_LOCALIZATION_KEYS_RESTORED_TEST.iso');_,dsl=b.iso_read_file(iso,b.TARGET_DSL);_,mdi=b.iso_read_file(iso,b.TARGET_MDI);st={x['index']:bytes(x['decoded']) for x in b.parse_mdi(mdi)}
for word in [0x40127f80,0xb8000907]:
 p=0
 while 1:
  p=dsl.find(struct.pack('<I',word),p)
  if p<0:break
  print(hex(word),hex(p),dsl[max(0,p-16):p+20].hex());p+=4
for i,d in st.items():
 p=d.find(struct.pack('<III',0x40006580,0x200,0x41419020))
 if p>=0:print('mainrec stream',i,hex(p))
bodyoff=0x0972524c-b.STREAM19_RAM_BASE;print('bodyobjoffset',hex(bodyoff));print('stream sizes',[(i,len(d)) for i,d in st.items() if i>=19]);Path('work/source40j_dsl.bin').write_bytes(dsl)
