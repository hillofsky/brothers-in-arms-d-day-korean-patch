exec(open('work/audit43r_title.py',encoding='utf-8-sig').read().split('for name,iso')[0])
import sys;sys.path.insert(0,'work/python_deps');from capstone import *
cs=Cs(CS_ARCH_MIPS,CS_MODE_MIPS32|CS_MODE_LITTLE_ENDIAN)
for f in ['BIAOFF.PRX','BIAON.PRX']:
 _,o=b.iso_read_file(Path('PROJECT_ROOT/Brothers in Arms - D-Day (USA) (v1.01).iso'),['PSP_GAME','USRDIR','SYSTEM',f]);_,p=b.iso_read_file(Path('PROJECT_ROOT/BIA_STAGE43Q_HINT_HEIGHT_TEST.iso'),['PSP_GAME','USRDIR','SYSTEM',f]);
 print(f)
 for a in range(0x80,min(len(o),len(p),0x490000),4):
  if o[a:a+4]!=p[a:a+4] and p[a:a+4]==bytes(4):
   ins=list(cs.disasm(o[a:a+4],a-0x80+0x08804000));
   if ins:print(hex(a-0x80),ins[0].mnemonic,ins[0].op_str)
