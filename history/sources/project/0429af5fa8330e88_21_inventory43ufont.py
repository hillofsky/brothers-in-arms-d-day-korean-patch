import importlib.util,struct,json
from pathlib import Path
s=importlib.util.spec_from_file_location('m','PROJECT_ROOT/bia_stage40i_tools/bia_stage40i_actual_resource_trace.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);_,b=m.load_helpers();_,blob=b.iso_read_file(Path('PROJECT_ROOT/BIA_STAGE43A_FIRST_CAMPAIGN_KO_TEST.iso'),['PSP_GAME','USRDIR','SYSTEM','D0_0130_.MDI']);st={x['index']:bytes(x['decoded']) for x in b.parse_mdi(blob)}
base=0x8e03020;stride=0x78000
for addr,size,name in [(0x09a8cac0,112,'ufont'),(0x09c07d80,3000,'glyphs20'),(0x09c16370,1200,'remap8')]:
 i,o=divmod(addr-base,stride);d=st[i][o:o+size];Path('outputs/stage43b/'+name+'.bin').write_bytes(d);print(name,'stream',i,'offset',hex(o),d[:60].hex())
