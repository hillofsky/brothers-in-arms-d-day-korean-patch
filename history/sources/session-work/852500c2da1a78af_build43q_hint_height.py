import struct,json,importlib.util,shutil
from pathlib import Path
s=importlib.util.spec_from_file_location('m','PROJECT_ROOT/bia_stage40i_tools/bia_stage40i_actual_resource_trace.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);_,b=m.load_helpers();src=Path('PROJECT_ROOT/BIA_STAGE43O_RESTART_LIFETIME_TEST.iso');dst=Path('PROJECT_ROOT/BIA_STAGE43Q_HINT_HEIGHT_TEST.iso');path=['PSP_GAME','USRDIR','SYSTEM','BIAOFF.PRX'];_,old=b.iso_read_file(src,path);new=bytearray(old);helper=0x5fef70
# Preserve a0, t6 and ra; reuse the complete UTF-8 decoder with a2 output.
w=[0x27bdfff0,0xafbf0000,0xafae0004,0xafa40008,0x02402021,0x0c000000|(0x5fed00>>2),0x02207021,0x01c08821,0x8fa40008,0x8fae0004,0x8fbf0000,0x03e00008,0x27bd0010];code=struct.pack('<13I',*w);edits={0x20fb8:0x0c000000|(helper>>2),0x20fbc:0x34110000,0x20fc0:0x10c00000|((0x211e8-0x20fc0-4)//4),0x211d8:0x0c000000|(helper>>2),0x211dc:0x03119021}
for a,v in edits.items():struct.pack_into('<I',new,a+0x80,v)
phoff=struct.unpack_from('<I',old,28)[0];ph=phoff+32;typ,fo,va,pa,fs,ms,flags,align=struct.unpack_from('<8I',old,ph);assert va+fs==helper and fs==ms;extra=(len(code)+15)&~15;at=fo+fs;new[at:at]=code.ljust(extra,b'\0');struct.pack_into('<8I',new,ph,typ,fo,va,pa,fs+extra,ms+extra,flags,align)
shoff=struct.unpack_from('<I',old,32)[0];ent,n=struct.unpack_from('<HH',old,46);struct.pack_into('<I',new,32,shoff+extra)
for i in range(n):
 o=shoff+extra+i*ent;v=struct.unpack_from('<I',new,o+16)[0]
 if v>=at:struct.pack_into('<I',new,o+16,v+extra)
cur=shoff+extra;relsec=cur+2*ent;start,size=struct.unpack_from('<II',new,relsec+16);relat=start+size;relocs=[(0x20fb8,4),(0x211d8,4),(helper+20,4)];rp=b''.join(struct.pack('<II',*v) for v in relocs);new[relat:relat]=rp;newsh=cur+(len(rp) if cur>=relat else 0);struct.pack_into('<I',new,32,newsh)
for i in range(n):
 o=newsh+i*ent;v=struct.unpack_from('<I',new,o+16)[0]
 if v>=relat:struct.pack_into('<I',new,o+16,v+len(rp))
struct.pack_into('<I',new,newsh+2*ent+20,size+len(rp));assert 0x08804000+va+ms+extra<0x08e03020
out=Path('outputs/stage43q');out.mkdir(exist_ok=True);(out/'patched.prx').write_bytes(new);(out/'size_adapter.bin').write_bytes(code);(out/'patch_report.json').write_text(json.dumps({'source':str(src),'output':str(dst),'helper_va':hex(helper),'helper_bytes':len(code),'hooks':{hex(a):hex(v) for a,v in edits.items()},'module_end':hex(0x08804000+va+ms+extra),'new_relocations':[hex(a) for a,t in relocs],'chapter_restart_fix_preserved':True,'runtime_verified':False},indent=2));assert not dst.exists();shutil.copy2(src,dst);b.append_iso_file_and_repoint(dst,path,new);assert b.iso_read_file(dst,path)[1]==new;print('BUILT',dst)
