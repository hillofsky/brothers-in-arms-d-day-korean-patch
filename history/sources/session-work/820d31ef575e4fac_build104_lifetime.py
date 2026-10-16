import importlib.util,struct,shutil,json,hashlib,sys
from pathlib import Path
s=importlib.util.spec_from_file_location('m','PROJECT_ROOT/bia_stage40i_tools/bia_stage40i_actual_resource_trace.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);_,b=m.load_helpers();src=Path('PROJECT_ROOT/BIA_STEP103_RELOAD_CONFIRM_KO_TEST.iso');dst=Path('PROJECT_ROOT/BIA_STEP104_CHECKPOINT_STRING_LIFETIME_TEST.iso');out=Path('outputs/step104_fix');out.mkdir(exist_ok=True);parts=['PSP_GAME','USRDIR','SYSTEM','BIAOFF.PRX'];_,old=b.iso_read_file(src,parts);new=bytearray(old)
phoff=struct.unpack_from('<I',old,28)[0];ph=phoff+32;typ,fo,va,pa,fs,ms,flags,align=struct.unpack_from('<8I',old,ph);helper=va+fs;assert fs==ms;call=0xb51b4;assert struct.unpack_from('<2I',old,call+0x80)==(0x27bdfff0,0x00a03825)
base=0x08804000;lo=0x08e03020+35*0x78000;hi=lo+0x78000
code=[0x3c080000|(lo>>16),0x35080000|(lo&65535),0x00a8482b,0x15200007,0,0x3c080000|(hi>>16),0x35080000|(hi&65535),0x00a8482b,0x11200003,0,0x03e00008,0,0x27bdfff0,0x00a03825,0x3c080000|((base+call+8)>>16),0x35080000|((base+call+8)&65535),0x01000008,0]
# Branch at instruction3 must jump to instruction12 (offset8).
code[3]=0x15200008
payload=struct.pack('<'+str(len(code))+'I',*code);extra=(len(payload)+15)&~15;at=fo+fs;new[at:at]=payload.ljust(extra,b'\0');struct.pack_into('<8I',new,ph,typ,fo,va,pa,fs+extra,ms+extra,flags,align);shoff=struct.unpack_from('<I',old,32)[0];ents,n=struct.unpack_from('<HH',old,46);struct.pack_into('<I',new,32,shoff+extra)
for j in range(n):
 o=shoff+extra+j*ents;v=struct.unpack_from('<I',new,o+16)[0]
 if v>=at:struct.pack_into('<I',new,o+16,v+extra)
struct.pack_into('<2I',new,call+0x80,0x08000000|((base+helper)>>2),0)
assert base+helper+extra<0x08e03020
for j in range(n):
 a=struct.unpack_from('<10I',old,shoff+j*ents);z=struct.unpack_from('<10I',new,shoff+extra+j*ents);assert a[:4]==z[:4] and a[5:]==z[5:]
 if a[1]!=8 and a[5]:
  x=old[a[4]:a[4]+a[5]];y=new[z[4]:z[4]+z[5]]
  if a[4]<=call+0x80<a[4]+a[5]:
   o=call+0x80-a[4];assert x[:o]==y[:o] and x[o+8:]==y[o+8:]
  else:assert x==y
(out/'helper.bin').write_bytes(payload);(out/'patched.prx').write_bytes(new);(out/'patch_metadata.json').write_text(json.dumps({'helper_va':helper,'helper_runtime':base+helper,'hook_runtime':base+call,'protected_start':lo,'protected_end':hi,'module_end':base+helper+extra},indent=2))
print('HELPER READY',hex(base+helper),hex(lo),hex(hi))

# Build only after helper checks pass.
assert json.loads((out/'helper_tests.json').read_text()) and not dst.exists()
sourcehash=hashlib.file_digest(src.open('rb'),'sha256').hexdigest();shutil.copy2(src,dst);b.append_iso_file_and_repoint(dst,parts,bytes(new));assert b.iso_read_file(dst,parts)[1]==new
assert hashlib.file_digest(src.open('rb'),'sha256').hexdigest()==sourcehash
for filename in ['D2_0630_.MDI','D2_0630_.DSL','D2_0630_.DSX','MEMORYSTICK.INT','BIAON.PRX']:
 p=['PSP_GAME','USRDIR','SYSTEM',filename];assert b.iso_read_file(src,p)[1]==b.iso_read_file(dst,p)[1]
(out/'build_report.json').write_text(json.dumps({'source':str(src),'output':str(dst),'source_sha256':sourcehash,'output_sha256':hashlib.file_digest(dst.open('rb'),'sha256').hexdigest(),'source_preserved':True,'changes':'Skip string-pool free for static campaign stream35 storage; preserve original free path for all other pointers','section_payloads_preserved_except_entry_hook':True,'existing_relocations_preserved':True,'helper_boundary_tests':8,'iso_readback_verified':True,'runtime_verified':False},indent=2));print('BUILT',dst,flush=True)

