import sys,json
from pathlib import Path
sys.path.insert(0,'work/python_deps')
from unicorn import Uc,UC_ARCH_MIPS,UC_MODE_MIPS32,UC_MODE_LITTLE_ENDIAN
from unicorn.mips_const import *
layout=json.loads(Path('PROJECT_ROOT/bia_stage39a_tools/stage39a_font_plan.json').read_text(encoding='utf-8'))['layout']+json.loads(Path('outputs/stage43a/new_font_glyphs.json').read_text(encoding='utf-8'))
cases=[(c.encode('utf-8')+b'\0',ord(c),len(c.encode('utf-8'))-1) for c in ''.join(x['char'] for x in layout)+'ASCII 0123éß']+[(b'\xe1\0',0xe1,0),(b'\xe1\x80\0',0xe1,0),(b'\xc2\0',0xc2,0)]
verified=0
for name,out,advance in [('size',UC_MIPS_REG_A1,UC_MIPS_REG_T9),('wrap',UC_MIPS_REG_A1,UC_MIPS_REG_V1)]:
 code=Path('outputs/stage43l/'+name+'_decoder.bin').read_bytes();u=Uc(UC_ARCH_MIPS,UC_MODE_MIPS32|UC_MODE_LITTLE_ENDIAN);u.mem_map(0x1000000,0x2000);u.mem_map(0x2000000,0x2000);u.mem_map(0x3000000,0x1000);u.mem_write(0x1000000,code)
 for data,expected,consumed in cases:
  for i,reg in enumerate([UC_MIPS_REG_T0,UC_MIPS_REG_T1,UC_MIPS_REG_T2,UC_MIPS_REG_T3]):u.reg_write(reg,0x12340000+i)
  u.mem_write(0x3000000,data);u.reg_write(UC_MIPS_REG_SP,0x2001000);u.reg_write(UC_MIPS_REG_A0,0x3000000);u.reg_write(advance,3);u.reg_write(UC_MIPS_REG_RA,0x1001000);u.emu_start(0x1000000,0x1001000,count=200)
  assert u.reg_read(out)==expected,(name,data,u.reg_read(out),expected)
  assert u.reg_read(advance)==3+consumed
  assert u.reg_read(UC_MIPS_REG_SP)==0x2001000
  for i,reg in enumerate([UC_MIPS_REG_T0,UC_MIPS_REG_T1,UC_MIPS_REG_T2,UC_MIPS_REG_T3]):assert u.reg_read(reg)==0x12340000+i
  verified+=1
p=Path('outputs/stage43l/decoder_execution_test.json');p.write_text(json.dumps({'native_mips_execution_cases':verified,'hangul_per_decoder':729,'register_and_stack_preservation':True,'byte_advance_verified':True,'truncated_input_verified':True},indent=2));print('MIPS machine code cases passed:',verified)
