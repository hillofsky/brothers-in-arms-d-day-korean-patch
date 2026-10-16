import importlib.util,struct,sys
from pathlib import Path
sys.path.insert(0,'work/python_deps');from capstone import *
s=importlib.util.spec_from_file_location('m','PROJECT_ROOT/bia_stage40i_tools/bia_stage40i_actual_resource_trace.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);_,b=m.load_helpers();_,on=b.iso_read_file(Path('PROJECT_ROOT/BIA_STAGE43I_CAMPAIGN_HINT_FIT_TEST.iso'),['PSP_GAME','USRDIR','SYSTEM','BIAON.PRX']);off=Path('work/biaoff43.prx').read_bytes();a=0x47b2fc;chunk=on[a+0x80:a+0xc0];md=Cs(CS_ARCH_MIPS,CS_MODE_MIPS32+CS_MODE_LITTLE_ENDIAN)
for ins in md.disasm(chunk,0x08c7f2fc):print(hex(ins.address),ins.mnemonic,ins.op_str)
for start in range(0,len(chunk)-15,4):
 needle=chunk[start:start+16];p=off.find(needle)
 if p>=0:print('MATCH',hex(start),hex(p-0x80+0x8804000))
Path('work/biaon43.prx').write_bytes(on)
