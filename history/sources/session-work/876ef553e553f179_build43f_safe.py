import struct,json,importlib.util,shutil,hashlib
from pathlib import Path
s=importlib.util.spec_from_file_location('m','PROJECT_ROOT/bia_stage40i_tools/bia_stage40i_actual_resource_trace.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);_,b=m.load_helpers();src=Path('PROJECT_ROOT/BIA_STAGE43D_CAMPAIGN_UFONT_EXPANSION_TEST.iso');dst=Path('PROJECT_ROOT/BIA_STAGE43F_CAMPAIGN_UTF8_SAFE_CODE_TEST.iso');path=['PSP_GAME','USRDIR','SYSTEM','BIAOFF.PRX'];_,old=b.iso_read_file(src,path);new=bytearray(old)
rep=json.loads(Path('outputs/stage43e/utf8_render_patch_report.json').read_text());targets=[0x5fec10,0x5fed00]
for item in rep['patches']:
 va=int(item['va'],0);assert struct.unpack_from('<I',old,va+0x80)[0]==int(item['before'],0)
 word=int(item['after'],0)
 if va in [0x23b04,0x208dc]:word=0x0c000000|(targets[[0x23b04,0x208dc].index(va)]>>2)
 struct.pack_into('<I',new,va+0x80,word)
for off,va in [(0x6f51c8,0x23b04),(0x6f51d0,0x208dc)]:assert struct.unpack_from('<I',old,off+4)[0]==0;struct.pack_into('<II',new,off,va,4)
phoff=struct.unpack_from('<I',old,28)[0];ph1=phoff+32;ptype,fo,va,pa,filesz,memsz,flags,align=struct.unpack_from('<8I',old,ph1);assert (fo,va,filesz,memsz)==(0x57e780,0x57e700,0x1b210,0x80504)
insert_at=fo+filesz;newsize=0x5fedc0-va;extra=newsize-filesz;payload=bytearray(extra)
for target,name in zip(targets,['0x49b780','0x49b900']):
 code=Path('outputs/stage43e/'+name+'_decoder.bin').read_bytes();p=target-va-filesz;assert p>=0;payload[p:p+len(code)]=code
new[insert_at:insert_at]=payload
struct.pack_into('<8I',new,ph1,ptype,fo,va,pa,newsize,newsize,7,align)
shoff=struct.unpack_from('<I',old,32)[0];entsize,count=struct.unpack_from('<HH',old,46);newshoff=shoff+extra;struct.pack_into('<I',new,32,newshoff)
for i in range(count):
 off=newshoff+i*entsize;fileoff=struct.unpack_from('<I',new,off+16)[0]
 if fileoff>=insert_at:struct.pack_into('<I',new,off+16,fileoff+extra)
assert not dst.exists();shutil.copy2(src,dst);b.append_iso_file_and_repoint(dst,path,bytes(new));assert b.iso_read_file(dst,path)[1]==bytes(new)
out=Path('outputs/stage43f');out.mkdir(exist_ok=True);r={'test_iso':str(dst),'helper_vas':[hex(x) for x in targets],'helper_runtime':[hex(x+0x08804000) for x in targets],'original_cjis_code_preserved':True,'original_bss_zero_initialized':True,'module_end_before':'0x08e02c04','module_end_after':'0x08e02dc0','first_mission_base':'0x08e03020','file_growth_bytes':extra,'memory_growth_bytes':newsize-memsz,'new_helpers_executable_segment':True,'iso_readback_verified':True,'runtime_verified':False};(out/'safe_code_patch_report.json').write_text(json.dumps(r,indent=2));print(json.dumps(r))
s=Path('work/stage43e_live.py').read_text(encoding='utf-8');s=s.replace('stage43e_validation','stage43f_validation').replace('nav43e_command.json','nav43f_command.json').replace('BIA_STAGE43E_CAMPAIGN_UTF8_RENDER_TEST.iso','BIA_STAGE43F_CAMPAIGN_UTF8_SAFE_CODE_TEST.iso');Path('work/stage43f_live.py').write_text(s,encoding='utf-8')
s=Path('work/nav43e_auto.py').read_text().replace('nav43e_','nav43f_');Path('work/nav43f_auto.py').write_text(s)
