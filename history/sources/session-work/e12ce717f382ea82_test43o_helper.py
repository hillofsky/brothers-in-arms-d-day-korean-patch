import sys,struct,json
from pathlib import Path
sys.path.insert(0,'work/python_deps');from unicorn import *;from unicorn.mips_const import *
code=Path('outputs/stage43o/heap_reset_helper.bin').read_bytes();cases=[]
for shift in [0,0x10000,-0x10000]:
 u=Uc(UC_ARCH_MIPS,UC_MODE_MIPS32|UC_MODE_LITTLE_ENDIAN);u.mem_map(0x08000000,0x02000000);start=0x08e02f40+shift;ret=0x0881b488+shift;dest=0x08ca0360+shift;global_=0x08ce5b10+shift;u.mem_write(start,code);u.mem_write(global_,struct.pack('<I',0x08fea540));u.reg_write(UC_MIPS_REG_RA,ret)
 for reg,value in [(UC_MIPS_REG_A0,0x08e03020),(UC_MIPS_REG_A1,0),(UC_MIPS_REG_A2,0x400000),(UC_MIPS_REG_SP,0x09fff000)]:u.reg_write(reg,value)
 u.emu_start(start,dest,count=30)
 assert u.reg_read(UC_MIPS_REG_PC)==dest and u.mem_read(global_,4)==b'\0'*4
 assert u.reg_read(UC_MIPS_REG_RA)==ret and u.reg_read(UC_MIPS_REG_A0)==0x08e03020 and u.reg_read(UC_MIPS_REG_A2)==0x400000
 cases.append({'relocation_shift':shift,'passed':True})
Path('outputs/stage43o/helper_execution_test.json').write_text(json.dumps({'cases':cases,'passed':len(cases)},indent=2));print('HELPER PASS',len(cases))
