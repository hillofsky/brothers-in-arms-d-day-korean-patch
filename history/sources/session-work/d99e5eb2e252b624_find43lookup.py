import importlib.util,struct
from pathlib import Path
s=importlib.util.spec_from_file_location('m','PROJECT_ROOT/bia_stage40i_tools/bia_stage40i_actual_resource_trace.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);_,b=m.load_helpers();_,d=b.iso_read_file(Path('PROJECT_ROOT/BIA_STAGE43A_FIRST_CAMPAIGN_KO_TEST.iso'),['PSP_GAME','USRDIR','SYSTEM','BIAOFF.PRX']);Path('work/biaoff43.prx').write_bytes(d)
for p in range(0x80,0x490000,4):
 if struct.unpack_from('<I',d,p)[0]==0x0c1163b5:print(hex(p-0x80),hex(p-0x80+0x08804000))
