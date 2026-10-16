import importlib.util,struct,json
from pathlib import Path
s=importlib.util.spec_from_file_location('m','PROJECT_ROOT/bia_stage40i_tools/bia_stage40i_actual_resource_trace.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);_,b=m.load_helpers();iso=Path('PROJECT_ROOT/BIA_STAGE40O_CONTROLS_UTF8_COMPLETE_TEST.iso');_,on=b.iso_read_file(iso,['PSP_GAME','SYSDIR','BOOT.BIN']);_,off=b.iso_read_file(iso,['PSP_GAME','USRDIR','SYSTEM','BIAOFF.PRX']);Path('work/BIAOFF.PRX').write_bytes(off)
for name,va,pre,post in [('lookup',0x47b2fc,0,32),('renderer_call',0x16e360,24,32),('width_call1',0x4fcc0,24,32),('width_call2',0x4f244,24,32)]:
 needle=on[va+0x80-pre:va+0x80];tail=on[va+0x84:va+0x80+post];hits=[]
 if name=='lookup':needle=on[va+0x80:va+0x80+post]
 pos=0
 while True:
  i=off.find(needle,pos)
  if i<0:break
  pos=i+1
  if name=='lookup' or off[i+pre+4:i+pre+post]==tail:hits.append(hex(i+pre-0x80))
 print(name,hits)
print('elf',off[:16].hex())
helper=Path('PROJECT_ROOT/bia_stage39u_tools/utf8_widened_renderer_helper.bin').read_bytes();print('renderhelper',len(helper),[hex(x) for x in struct.unpack('<'+str(len(helper)//4)+'I',helper)[-8:]])
