import struct,json,shutil,importlib.util
from pathlib import Path
s=importlib.util.spec_from_file_location('m','PROJECT_ROOT/bia_stage40i_tools/bia_stage40i_actual_resource_trace.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);_,b=m.load_helpers()
src=Path('PROJECT_ROOT/BIA_STAGE43M_CAMPAIGN_OBJECTIVE_UTF8_TEST.iso');dst=Path('PROJECT_ROOT/BIA_STAGE43O_RESTART_LIFETIME_TEST.iso');path=['PSP_GAME','USRDIR','SYSTEM','BIAOFF.PRX'];_,old=b.iso_read_file(src,path);new=bytearray(old)
helper=0x5fef40;call=0x17480;assert struct.unpack_from('<I',old,call+0x80)[0]==0x0c000000|(0x49c360>>2)
# Tail wrapper: invalidate the engine reference when resetting its owning heap.
# All addresses derive from the call's return address, preserving relocation independence.
ret=0x0881b488;g=0x08ce5b10;target=0x08ca0360
code=[]
for delta in [g-ret,target-ret]:
 code.extend([0x3c080000|((delta>>16)&65535),0x35080000|(delta&65535),0x011f4021])
 if delta==g-ret:code.append(0xad000000)
code.extend([0x01000008,0]);payload=struct.pack('<'+str(len(code))+'I',*code)
phoff=struct.unpack_from('<I',old,28)[0];ph=phoff+32;typ,fo,va,pa,fs,ms,flags,align=struct.unpack_from('<8I',old,ph);assert va+fs==helper and fs==ms
extra=(len(payload)+15)&~15;at=fo+fs;new[at:at]=payload.ljust(extra,b'\0');struct.pack_into('<8I',new,ph,typ,fo,va,pa,fs+extra,ms+extra,flags,align)
shoff=struct.unpack_from('<I',old,32)[0];ents,n=struct.unpack_from('<HH',old,46);struct.pack_into('<I',new,32,shoff+extra)
for i in range(n):
 o=shoff+extra+i*ents;v=struct.unpack_from('<I',new,o+16)[0]
 if v>=at:struct.pack_into('<I',new,o+16,v+extra)
struct.pack_into('<I',new,call+0x80,0x0c000000|(helper>>2));assert 0x08804000+va+ms+extra<0x08e03020
out=Path('outputs/stage43o');out.mkdir(exist_ok=True);(out/'patched.prx').write_bytes(new);(out/'heap_reset_helper.bin').write_bytes(payload)
# Preserve every existing section payload except the one instruction in .text.
for i in range(n):
 a=struct.unpack_from('<10I',old,shoff+i*ents);z=struct.unpack_from('<10I',new,shoff+extra+i*ents)
 assert a[:4]==z[:4] and a[5:]==z[5:]
 if a[1]!=8 and a[5]:
  x=old[a[4]:a[4]+a[5]];y=new[z[4]:z[4]+z[5]]
  if a[4]<=call+0x80<a[4]+a[5]:
   pos=call+0x80-a[4];assert x[:pos]==y[:pos] and x[pos+4:]==y[pos+4:]
  else:assert x==y
assert not dst.exists();shutil.copy2(src,dst);b.append_iso_file_and_repoint(dst,path,bytes(new));assert b.iso_read_file(dst,path)[1]==new
(out/'restart_patch_report.json').write_text(json.dumps({'source':str(src),'output':str(dst),'hook_va':hex(call),'helper_va':hex(helper),'helper_bytes':len(payload),'module_end':hex(0x08804000+va+ms+extra),'section_payloads_preserved':True,'existing_relocations_preserved':True,'iso_readback_verified':True,'runtime_verified':False},indent=2));print('BUILT',dst)
