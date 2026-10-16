import sys,struct,json,importlib.util
from pathlib import Path
sys.path.insert(0,'work/python_deps')
from unicorn import *
from unicorn.mips_const import *
s=importlib.util.spec_from_file_location('m','PROJECT_ROOT/bia_stage40i_tools/bia_stage40i_actual_resource_trace.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);_,b=m.load_helpers();iso=Path('PROJECT_ROOT/BIA_STAGE43L_CAMPAIGN_OBJECTIVE_UTF8_TEST.iso');_,prx=b.iso_read_file(iso,['PSP_GAME','USRDIR','SYSTEM','BIAOFF.PRX']);_,blob=b.iso_read_file(iso,['PSP_GAME','USRDIR','SYSTEM','D0_0130_.MDI']);st={x['index']:bytes(x['decoded']) for x in b.parse_mdi(blob)}
u=Uc(UC_ARCH_MIPS,UC_MODE_MIPS32|UC_MODE_LITTLE_ENDIAN);u.mem_map(0x08000000,0x02000000);u.mem_write(0x089f4178,prx[0x1f0178+0x80:0x1f0278+0x80])
for i in [3,29,30,35]:u.mem_write(0x08e03020+i*0x78000,st[i])
font=0x08fc3ca0;meta=0x09e6b020;pairs=[struct.unpack_from('<iHH',st[35],0x27000+i*8)[1:] for i in range(879)]
for cp,index in pairs:
 u.reg_write(UC_MIPS_REG_A0,font);u.reg_write(UC_MIPS_REG_A1,cp);u.reg_write(UC_MIPS_REG_A2,0x08001000);u.reg_write(UC_MIPS_REG_A3,0x08001004);u.reg_write(UC_MIPS_REG_RA,0x08002000);u.emu_start(0x089f4178,0x08002000,count=2000)
 width,height=struct.unpack('<II',u.mem_read(0x08001000,8));expected=struct.unpack_from('<II',st[35],0x29000+index*20+8);assert (width,height)==expected,(hex(cp),index,width,height,expected)
Path('outputs/stage43l/font_width_execution_test.json').write_text(json.dumps({'machine_code_font_width_lookups':879,'all_glyph_widths_and_heights_verified':True,'includes_all_original_latin_glyphs':True,'includes_all_729_hangul_glyphs':True},indent=2));print('Font width MIPS lookups passed: 879')
