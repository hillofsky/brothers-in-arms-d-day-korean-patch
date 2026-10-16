import json,struct,importlib.util
from pathlib import Path
s=importlib.util.spec_from_file_location('m','PROJECT_ROOT/bia_stage40i_tools/bia_stage40i_actual_resource_trace.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);_,b=m.load_helpers();_,blob=b.iso_read_file(Path('PROJECT_ROOT/BIA_STAGE40L_CONTROLS_UTF8_WIDTH_TEST.iso'),b.TARGET_MDI);st={x['index']:bytes(x['decoded']) for x in b.parse_mdi(blob)}
for needle in [b'StanceAction\0',b'Stance/Action\0',b'ReloadAction\0',b'Reload/Action\0',b'STANCE_OR_ACTION\0',b'RELOAD_OR_ACTION\0']:
 for si,data in st.items():
  pos=0
  while 1:
   pos=data.find(needle,pos)
   if pos<0:break
   print(needle.decode(errors='replace'),si,hex(pos),hex(b.MDI_SEQ_BASE+si*b.MDI_STREAM_SIZE+pos));pos+=len(needle)
   if pos>len(data):break
for off in range(0x44d90,0x44f40,4):
 p,n,c=struct.unpack_from('<III',st[16],off);si=(p-b.MDI_SEQ_BASE)//b.MDI_STREAM_SIZE;so=(p-b.MDI_SEQ_BASE)%b.MDI_STREAM_SIZE
 if si in st and 1<n<80 and n==c:
  val=st[si][so:so+n]
  if val.endswith(b'\0') and all(32<=v<127 for v in val[:-1]):print('metadata',hex(off),val,hex(p),n)
