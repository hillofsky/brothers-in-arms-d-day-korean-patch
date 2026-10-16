import importlib.util,struct
from pathlib import Path
s=importlib.util.spec_from_file_location('m',r'PROJECT_ROOT\bia_stage40i_tools\bia_stage40i_actual_resource_trace.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);_,b=m.load_helpers()
_,blob=b.iso_read_file(Path(r'PROJECT_ROOT\BIA_STAGE39U_BOOT_RENDER_UTF8_TEST.iso'),'PSP_GAME/USRDIR/SYSTEM/ON_MEMU_O.MDI'.split('/'))
st={x['index']:bytes(x['decoded']) for x in b.parse_mdi(blob)}
def showptr(ptr,num):
 for i,d in st.items():
  off=ptr-(0x08e2d020+i*0x78000)
  if 0<=off<len(d) and 0<num<500:return repr(d[off:off+num])
 return ''
for off in range(0x44a00,0x44cc0,4):
 p,n,c=struct.unpack_from('<III',st[16],off)
 text=showptr(p,n)
 if text:print(hex(off),hex(p),n,c,text)



