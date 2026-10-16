import sys,struct,json
from pathlib import Path
sys.path.insert(0,'work/python_deps');from unicorn import *;from unicorn.mips_const import *
ram=Path('outputs/stage43p2_probe/main_hint_hit_ram.bin').read_bytes();old=Path('outputs/stage43o/patched.prx').read_bytes();new=Path('outputs/stage43q/patched.prx').read_bytes()
def load(u,p,lo,hi):
 d=bytearray(p[lo+0x80:hi+0x80])
 for o in range(0,len(d)-3,4):
  w=struct.unpack_from('<I',d,o)[0]
  if w>>26==3:struct.pack_into('<I',d,o,0x0c000000|(((w&0x3ffffff)*4+0x08804000)>>2))
 u.mem_write(0x08804000+lo,bytes(d))
report=[]
for text in ['나','자유 시점 모드를 켤 수 있다.','Hold 로 자유 시점 모드를 켤 수 있다.','ASCII 0123','나침반 는 다음 목표 방향을 가리킨다.']:
 results={}
 for label,p in [('before',old),('after',new)]:
  u=Uc(UC_ARCH_MIPS,UC_MODE_MIPS32|UC_MODE_LITTLE_ENDIAN);u.mem_map(0x08000000,0x02000000);u.mem_write(0x08000000,ram);load(u,p,0x20f38,0x21204);load(u,p,0x1b2b4,0x1b3b4);load(u,p,0x5fed00,0x5fedbc)
  if label=='after':load(u,p,0x5fef70,0x5fefa4)
  u.mem_write(0x08003000,text.encode('utf-8')+b'\0')
  for reg,val in [(UC_MIPS_REG_A0,0x09a8bb10),(UC_MIPS_REG_A1,0x09a85860),(UC_MIPS_REG_A2,0x08fc3ca0),(UC_MIPS_REG_A3,0x08001000),(UC_MIPS_REG_T0,0x08001004),(UC_MIPS_REG_T1,0x08003000),(UC_MIPS_REG_RA,0x08002000),(UC_MIPS_REG_SP,0x09ffe000),(UC_MIPS_REG_F12,0x3f800000),(UC_MIPS_REG_F13,0x3f800000)]:u.reg_write(reg,val)
  u.emu_start(0x08824f38,0x08002000,count=100000);results[label]=struct.unpack('<II',u.mem_read(0x08001000,8));assert u.reg_read(UC_MIPS_REG_SP)==0x09ffe000
 if any(ord(c)>127 for c in text):assert results['after'][1]==16,(text,results)
 else:assert results['before']==results['after']
 report.append({'text':text,'before':results['before'],'after':results['after']});print(text,results)
Path('outputs/stage43q/text_size_execution_test.json').write_text(json.dumps({'cases':report,'passed':len(report)},ensure_ascii=False,indent=2),encoding='utf-8')

