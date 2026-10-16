from pathlib import Path
import importlib.util,re
s=importlib.util.spec_from_file_location('m','PROJECT_ROOT/bia_stage40i_tools/bia_stage40i_actual_resource_trace.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);_,b=m.load_helpers();_,blob=b.iso_read_file(Path('PROJECT_ROOT/BIA_STAGE43O_RESTART_LIFETIME_TEST.iso'),['PSP_GAME','USRDIR','SYSTEM','D0_0130_.MDI']);st={x['index']:bytes(x['decoded']) for x in b.parse_mdi(blob)}
for i,d in st.items():
 for mm in re.finditer(rb'[A-Za-z_][A-Za-z0-9_]{3,}',d):
  if b'hint' in mm[0].lower() or b'subtitle' in mm[0].lower():print(i,hex(mm.start()),mm[0].decode())
