import importlib.util,struct,sys,json
from pathlib import Path
sys.path.insert(0,'work/python_deps');from capstone import *
s=importlib.util.spec_from_file_location('m','PROJECT_ROOT/bia_stage40i_tools/bia_stage40i_actual_resource_trace.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);_,b=m.load_helpers();_,prx=b.iso_read_file(Path('PROJECT_ROOT/BIA_STEP111_RADIO_SUBTITLE_KO_TEST.iso'),['PSP_GAME','USRDIR','SYSTEM','BIAOFF.PRX']);md=Cs(CS_ARCH_MIPS,CS_MODE_MIPS32+CS_MODE_LITTLE_ENDIAN);a=0x0891b660;off=a-0x08804000+0x80
for i in md.disasm(prx[off:off+180],a):print(hex(i.address),i.mnemonic,i.op_str)
j=json.load(open('outputs/step112_hang/regs.json'));c=j['categories'][0];g=dict(zip(c['registerNames'],c['uintValues']));print({k:hex(v) for k,v in g.items() if k in ['pc','ra','s0','s1','s2','s3','s4','s5','a0','a1','a2','a3','t0','sp']});r=Path('outputs/step112_hang/current_ram.bin').read_bytes()
for key in ['a0','a1','a2','s0','s1']:
 addr=g[key]
 if 0x8000000<=addr<0xa000000:print(key,repr(r[addr-0x8000000:addr-0x8000000+120]))
