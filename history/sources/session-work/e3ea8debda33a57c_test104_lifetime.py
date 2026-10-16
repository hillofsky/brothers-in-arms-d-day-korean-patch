import sys,json,struct
from pathlib import Path
sys.path.insert(0,'work/python_deps');from unicorn import *;from unicorn.mips_const import *
o=Path('outputs/step104_fix');j=json.loads((o/'patch_metadata.json').read_text());code=(o/'helper.bin').read_bytes();start=j['helper_runtime'];returnpc=0x08805000;resume=j['hook_runtime']+8;tests=[]
for ptr in [0,0x0990c660,j['protected_start']-1,j['protected_start'],j['protected_start']+0x10044,j['protected_end']-1,j['protected_end'],0x09ff0000]:
 u=Uc(UC_ARCH_MIPS,UC_MODE_MIPS32|UC_MODE_LITTLE_ENDIAN);u.mem_map(0x08000000,0x02000000);u.mem_write(start,code);u.reg_write(UC_MIPS_REG_A1,ptr);u.reg_write(UC_MIPS_REG_A3,0x1234);u.reg_write(UC_MIPS_REG_SP,0x09fff000);u.reg_write(UC_MIPS_REG_RA,returnpc);seen=[]
 def hook(uc,a,size,data):
  if a in [returnpc,resume]:seen.append(a);uc.emu_stop()
 u.hook_add(UC_HOOK_CODE,hook);u.emu_start(start,0,count=40);protected=j['protected_start']<=ptr<j['protected_end'];assert seen==[returnpc if protected else resume];assert u.reg_read(UC_MIPS_REG_SP)==0x09fff000-(0 if protected else 16);assert u.reg_read(UC_MIPS_REG_A3)==(0x1234 if protected else ptr);tests.append({'pointer':hex(ptr),'protected':protected,'passed':True})
(o/'helper_tests.json').write_text(json.dumps(tests,indent=2));print('PASS',len(tests),'boundary and original-path tests')
