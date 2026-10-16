import importlib.util,struct,sys
from pathlib import Path
sys.path.insert(0,'work/python_deps');from capstone import *
s=importlib.util.spec_from_file_location('m','PROJECT_ROOT/bia_stage40i_tools/bia_stage40i_actual_resource_trace.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);_,b=m.load_helpers()
_,orig=b.iso_read_file(Path('PROJECT_ROOT/Brothers in Arms - D-Day (USA) (v1.01).iso'),['PSP_GAME','USRDIR','SYSTEM','BIAOFF.PRX']);Path('work/biaoff_original_restart.prx').write_bytes(orig)
new=Path('outputs/stage43m/patched.prx').read_bytes();print('movie routine original match',orig[0x11fb0+0x80:0x12130+0x80]==new[0x11fb0+0x80:0x12130+0x80])
md=Cs(CS_ARCH_MIPS,CS_MODE_MIPS32+CS_MODE_LITTLE_ENDIAN)
for o in range(0x80,min(len(orig),0x4b0000),4):
 w=struct.unpack_from('<I',orig,o)[0]
 if w>>26 in (35,43) and w&65535==0x1b10:
  a=o-0x80
  print('\nREF',hex(0x08804000+a));print('\n'.join(hex(i.address)+' '+i.mnemonic+' '+i.op_str for i in md.disasm(orig[o-12:o+20],0x08804000+a-12)))
