import struct,hashlib,json,shutil,importlib.util
from pathlib import Path
out=Path('outputs/stage40r');out.mkdir(exist_ok=True)
s=importlib.util.spec_from_file_location('m','PROJECT_ROOT/bia_stage40i_tools/bia_stage40i_actual_resource_trace.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);_,b=m.load_helpers();src=Path('PROJECT_ROOT/BIA_STAGE40O_CONTROLS_UTF8_COMPLETE_TEST.iso');dst=Path('PROJECT_ROOT/BIA_STAGE40R_CAMPAIGN_RENDERER_TEST.iso');path=['PSP_GAME','USRDIR','SYSTEM','BIAOFF.PRX'];_,old=b.iso_read_file(src,path);new=bytearray(old)
renderer=bytearray(Path('PROJECT_ROOT/bia_stage39u_tools/utf8_widened_renderer_helper.bin').read_bytes());delta=0x458ed4-(0x18a354+8);struct.pack_into('<II',renderer,len(renderer)-20,0x3c0b0000|(delta>>16),0x356b0000|(delta&65535))
helpers=[(0x49b468,bytes(renderer)),(0x49b560,Path('outputs/stage40l/utf8_width_helper.bin').read_bytes()),(0x49b660,Path('outputs/stage40o/utf8_width_helper.bin').read_bytes())];calls=[(0x18a354,0x49b468,0x0c1163b5),(0x4eb3c,0x49b560,0x00c0f809),(0x4e0c0,0x49b660,0x00e0f809)]
for a,target,word in calls:assert struct.unpack_from('<I',old,a+0x80)[0]==word;struct.pack_into('<I',new,a+0x80,0x0c000000|(target>>2))
disabled=[]
for p in range(0x59a558,0x59a558+0x15cdd8,8):
 a,t=struct.unpack_from('<II',old,p)
 if any(start<=a<start+len(code) for start,code in helpers) and t:
  assert t in [5,6];struct.pack_into('<II',new,p,a,0);disabled.append({'record':hex(p),'address':hex(a),'type':t})
assert len(disabled)==6
for p,a in [(0x6f51b8,0x4eb3c),(0x6f51c0,0x4e0c0)]:assert struct.unpack_from('<I',new,p+4)[0]==0;struct.pack_into('<II',new,p,a,4)
for a,code in helpers:new[a+0x80:a+0x80+len(code)]=code;(out/(hex(a)+'_helper.bin')).write_bytes(code)
assert struct.unpack_from('<II',new,0x629798)==(0x18a354,4);assert not dst.exists();shutil.copy2(src,dst);b.overwrite_iso_same_size(dst,path,bytes(new));assert b.iso_read_file(dst,path)[1]==bytes(new)
report={'source':str(src),'test_iso':str(dst),'modified_file':'BIAOFF.PRX','original_sha1':hashlib.sha1(old).hexdigest(),'patched_sha1':hashlib.sha1(new).hexdigest(),'helpers':[{'va':hex(a),'runtime':hex(0x08804000+a),'size':len(code),'sha1':hashlib.sha1(code).hexdigest()} for a,code in helpers],'calls':[{'runtime':hex(0x08804000+a),'target':hex(0x08804000+t),'expected_word':hex(0x0c000000|((0x08804000+t)>>2))} for a,t,w in calls],'disabled_old_cjis_relocations':disabled,'renderer_tail_delta':hex(delta),'iso_readback_ok':True,'runtime_verified':False};(out/'campaign_renderer_patch_report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
