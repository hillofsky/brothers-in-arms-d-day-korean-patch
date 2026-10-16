from pathlib import Path
import struct,importlib.util
s=importlib.util.spec_from_file_location('m','PROJECT_ROOT/bia_stage40i_tools/bia_stage40i_actual_resource_trace.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);_,b=m.load_helpers();p=['PSP_GAME','USRDIR','SYSTEM','BIAOFF.PRX'];_,old=b.iso_read_file(Path('PROJECT_ROOT/BIA_STAGE43I_CAMPAIGN_HINT_FIT_TEST.iso'),p);new=Path('outputs/stage43l/patched.prx').read_bytes()
for d in [old,new]:
 sho=struct.unpack_from('<I',d,32)[0];print('len',len(d),'shoff',hex(sho),'num',struct.unpack_from('<H',d,48)[0])
 for i in range(3):
  sh=struct.unpack_from('<10I',d,sho+i*40);print(i,[hex(x) for x in sh]);
 print('rel prefix',d[struct.unpack_from('<I',d,sho+2*40+16)[0]:][:32].hex())
