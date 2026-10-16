import importlib.util,re,struct,json
from pathlib import Path
s=importlib.util.spec_from_file_location('m','PROJECT_ROOT/bia_stage40i_tools/bia_stage40i_actual_resource_trace.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);_,b=m.load_helpers();print('MENU',b.TARGET_MDI)
for name,iso in [('orig','Brothers in Arms - D-Day (USA) (v1.01).iso'),('patch','BIA_STAGE43Q_HINT_HEIGHT_TEST.iso')]:
 _,blob=b.iso_read_file(Path('PROJECT_ROOT')/iso,b.TARGET_MDI);st={x['index']:bytes(x['decoded']) for x in b.parse_mdi(blob)}
 for i,d in st.items():
  for mm in re.finditer(rb'Press START button|START|strPress',d):
   print(name,i,hex(mm.start()),repr(d[max(0,mm.start()-40):mm.start()+100]))
