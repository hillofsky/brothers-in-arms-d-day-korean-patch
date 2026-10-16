import importlib.util,struct,sys,re
from pathlib import Path
sys.path.insert(0,'work/python_deps');from capstone import *
s=importlib.util.spec_from_file_location('m','PROJECT_ROOT/bia_stage40i_tools/bia_stage40i_actual_resource_trace.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);_,b=m.load_helpers();_,prx=b.iso_read_file(Path('PROJECT_ROOT/BIA_STEP103_RELOAD_CONFIRM_KO_TEST.iso'),['PSP_GAME','USRDIR','SYSTEM','BIAOFF.PRX']);md=Cs(CS_ARCH_MIPS,CS_MODE_MIPS32+CS_MODE_LITTLE_ENDIAN);md.skipdata=True
for a,z in [(0x088b9518,0x088b9670),(0x088b9ae4,0x088b9c50),(0x0888b600,0x0888b780)]:
 print('CODE',hex(a));off=a-0x8804000+0x80
 for i in md.disasm(prx[off:off+z-a],a):print(hex(i.address),i.mnemonic,i.op_str)
r=Path('outputs/step104_user_repro/paused_088b9c8c_ram.bin').read_bytes()
for a in [0x9a85780,0x9a857d0,0x8ce5b10,0x8dbc740]:print('MEM',hex(a),r[a-0x8000000:a-0x8000000+160].hex())
for name in ['D1_1830_.MDI','D2_0630_.MDI']:
 _,blob=b.iso_read_file(Path('PROJECT_ROOT/BIA_STEP103_RELOAD_CONFIRM_KO_TEST.iso'),['PSP_GAME','USRDIR','SYSTEM',name]);st={e['index']:bytes(e['decoded']) for e in b.parse_mdi(blob)};i,o=divmod(0x9a857e4-0x8e03020,0x78000);print(name,i,hex(o),repr(st[i][o-20:o+24]))
