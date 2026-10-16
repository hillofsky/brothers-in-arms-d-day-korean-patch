import sys,importlib.util,struct
from pathlib import Path
sys.path.insert(0,'work/python_deps');from capstone import *
s=importlib.util.spec_from_file_location('m','PROJECT_ROOT/bia_stage40i_tools/bia_stage40i_actual_resource_trace.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);_,b=m.load_helpers();iso=Path('PROJECT_ROOT/BIA_STEP123_SKIRMISH_KO_TEST.iso')
_,d=b.iso_read_file(iso,['PSP_GAME','USRDIR','SYSTEM','BIAOFF.PRX']);Path('outputs/step124/biaoff.prx').write_bytes(d);md=Cs(CS_ARCH_MIPS,CS_MODE_MIPS32+CS_MODE_LITTLE_ENDIAN)
for a,z,label in [(0x0893d800,0x0893dd20,'movie'),(0x08c7f100,0x08c7fa00,'rfont')]:
 off=a-0x08804000+0x80
 Path('outputs/step124/'+label+'_disasm.txt').write_text('\n'.join(f'{i.address:08x} {i.mnemonic} {i.op_str}' for i in md.disasm(d[off:off+z-a],a)))
print('extracted')
