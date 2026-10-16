import struct,hashlib,json,importlib.util,shutil
from pathlib import Path
out=Path('outputs/stage40l');out.mkdir(exist_ok=True)
regs={'zero':0,'a0':4,'a1':5,'a2':6,'t0':8,'t1':9,'t2':10,'t3':11,'t4':12,'t5':13,'t6':14,'t7':15,'s1':17,'s2':18}
code=[];labels={};fix=[]
def r(op,rd,rs,rt,sa=0):code.append((regs[rs]<<21)|(regs[rt]<<16)|(regs[rd]<<11)|(sa<<6)|op)
def i(op,rt,rs,n):code.append((op<<26)|(regs[rs]<<21)|(regs[rt]<<16)|(n&65535))
def branch(op,rs,rt,label):fix.append((len(code),label));i(op,rt,rs,0);code.append(0)
def mark(name):labels[name]=len(code)
# Decode only valid 2/3-byte UTF-8 widened into UTF-16 elements.
i(11,'t7','a1',0xc2);branch(5,'t7','zero','tail');i(11,'t7','a1',0xf0);branch(4,'t7','zero','tail')
i(35,'t1','s2',0x38);i(35,'t0','s1',0);r(0,'t7','zero','t1',1);r(33,'t0','t0','t7');i(35,'t2','s1',4);i(11,'t7','a1',0xe0);branch(4,'t7','zero','three')
i(9,'t7','t0',4);r(43,'t7','t2','t7');branch(5,'t7','zero','tail');i(37,'t3','t0',2);i(12,'t7','t3',0xffc0);i(14,'t7','t7',0x80);branch(5,'t7','zero','tail')
i(12,'t5','a1',0x1f);r(0,'t5','zero','t5',6);i(12,'t3','t3',0x3f);r(37,'t5','t5','t3');i(9,'t6','zero',1);branch(4,'zero','zero','commit')
mark('three');i(9,'t7','t0',6);r(43,'t7','t2','t7');branch(5,'t7','zero','tail');i(37,'t3','t0',2);i(37,'t4','t0',4)
for reg in ['t3','t4']:
 i(12,'t7',reg,0xffc0);i(14,'t7','t7',0x80);branch(5,'t7','zero','tail')
i(12,'t5','a1',0xf);r(0,'t5','zero','t5',12);i(12,'t3','t3',0x3f);r(0,'t3','zero','t3',6);r(37,'t5','t5','t3');i(12,'t4','t4',0x3f);r(37,'t5','t5','t4');i(11,'t7','t5',0x800);branch(5,'t7','zero','tail');i(12,'t7','t5',0xf800);i(14,'t7','t7',0xd800);branch(4,'t7','zero','tail');i(9,'t6','zero',2)
mark('commit');r(33,'t1','t1','t6');i(43,'t1','s2',0x38);r(33,'a1','t5','zero')
mark('tail');r(8,'zero','a2','zero');code.append(0)
for n,label in fix:code[n]=(code[n]&0xffff0000)|((labels[label]-n-1)&65535)
helper=struct.pack('<'+'I'*len(code),*code);(out/'utf8_width_helper.bin').write_bytes(helper)
VA=0x4c0480;CALL=0x4fcc0;BIAS=0x80;REL=0x734bec
source=Path('PROJECT_ROOT/BIA_STAGE40K_CONTROLS_FONT_TEST.iso');target=Path('PROJECT_ROOT/BIA_STAGE40L_CONTROLS_UTF8_WIDTH_TEST.iso')
s=importlib.util.spec_from_file_location('m','PROJECT_ROOT/bia_stage40i_tools/bia_stage40i_actual_resource_trace.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);_,b=m.load_helpers()
_,boot=b.iso_read_file(source,['PSP_GAME','SYSDIR','BOOT.BIN']);_,biaon=b.iso_read_file(source,['PSP_GAME','USRDIR','SYSTEM','BIAON.PRX']);assert boot==biaon;assert boot[CALL+BIAS:CALL+BIAS+4]==bytes.fromhex('09f8c000');assert struct.unpack_from('<II',boot,REL)==(0x4c03f0,0)
new=bytearray(boot);disabled=[]
for off in range(0x5bf54c,0x5bf54c+0x177848,8):
 location,typ=struct.unpack_from('<II',boot,off)
 if VA<=location<VA+len(helper) and typ:
  assert typ in (5,6);struct.pack_into('<II',new,off,location,0);disabled.append({'record':hex(off),'offset':hex(location),'type':typ})
new[VA+BIAS:VA+BIAS+len(helper)]=helper;struct.pack_into('<I',new,CALL+BIAS,0x0c000000|(VA>>2));struct.pack_into('<II',new,REL,CALL,4)
assert new[0x16e360+BIAS:0x16e360+BIAS+4]==boot[0x16e360+BIAS:0x16e360+BIAS+4]
assert not target.exists();shutil.copy2(source,target)
for path in [['PSP_GAME','SYSDIR','BOOT.BIN'],['PSP_GAME','USRDIR','SYSTEM','BIAON.PRX']]:
 b.overwrite_iso_same_size(target,path,bytes(new));assert b.iso_read_file(target,path)[1]==bytes(new)
for path in [b.TARGET_MDI,b.TARGET_DSL,b.TARGET_DSX,['PSP_GAME','SYSDIR','EBOOT.BIN']]:assert b.iso_read_file(target,path)[1]==b.iso_read_file(source,path)[1]
report={'source':str(source),'test_iso':str(target),'helper_size':len(helper),'helper_va':hex(VA),'helper_runtime':hex(0x08804000+VA),'width_call_runtime':hex(0x08804000+CALL),'width_call_disk':hex(0x0c000000|(VA>>2)),'width_call_runtime_word':hex(0x0c000000|((0x08804000+VA)>>2)),'helper_sha1':hashlib.sha1(helper).hexdigest(),'source_boot_sha1':hashlib.sha1(boot).hexdigest(),'new_boot_sha1':hashlib.sha1(new).hexdigest(),'disabled_old_cjis_relocs':disabled,'reused_none_relocation_record':hex(REL),'resource_files_and_eboot_unchanged':True,'iso_readback_ok':True,'runtime_verified':False}
(out/'width_patch_report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
