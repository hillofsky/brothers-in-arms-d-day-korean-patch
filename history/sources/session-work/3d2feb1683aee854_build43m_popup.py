import struct,json,importlib.util,shutil
from pathlib import Path
# Reuse the tested assembler without running the older build.
ns={};exec(Path('work/build43e_utf8.py').read_text(encoding='utf-8').split('s=importlib.util.spec_from_file_location')[0],ns);ns['REG'].update({'v1':3,'s0':16,'s4':20,'t9':25});I=ns['I'];R=ns['R'];decoder=ns['decoder']
s=importlib.util.spec_from_file_location('m','PROJECT_ROOT/bia_stage40i_tools/bia_stage40i_actual_resource_trace.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);_,b=m.load_helpers();src=Path('PROJECT_ROOT/BIA_STAGE43I_CAMPAIGN_HINT_FIT_TEST.iso');dst=Path('PROJECT_ROOT/BIA_STAGE43M_CAMPAIGN_OBJECTIVE_UTF8_TEST.iso');path=['PSP_GAME','USRDIR','SYSTEM','BIAOFF.PRX'];_,old=b.iso_read_file(src,path);new=bytearray(old);edits=[]
def put(va,w):
 o=va+0x80;edits.append({'va':hex(va),'before':hex(struct.unpack_from('<I',old,o)[0]),'after':hex(w)});struct.pack_into('<I',new,o,w)
# Popup drawing has its own UFont lookup and must retain both Unicode and glyph indices.
put(0x1f1704,0x0c000000|(0x5fec10>>2))
for a in [0x1f170c,0x1f1718,0x1f1724,0x1f1728,0x1f1730]:put(a,0)
put(0x1f17b4,I(13,'zero','t2',1));put(0x1f17c0,R(33,'a0','zero','a1'))
for a in [0x1f17c4,0x1f17cc,0x1f17d0,0x1f17d4]:put(a,0)
put(0x1f17c8,R(33,'a1','zero','a0'));put(0x1f17e4,I(12,'a0','a0',65535));put(0x1f19f4,I(12,'a0','a0',65535))
# Independent popup width lookup: same chained Unicode map, different argument registers.
put(0x1f0178,I(12,'a1','t2',65535))
for a in [0x1f017c,0x1f018c,0x1f0198,0x1f01a4,0x1f01a8,0x1f01b0]:put(a,0)
put(0x1f01a0,I(12,'t2','t2',65535));put(0x1f0218,I(13,'zero','t2',1));put(0x1f0224,R(33,'t0','zero','t1'));put(0x1f0228,0);put(0x1f022c,R(33,'t1','zero','t0'))
for a in [0x1f0230,0x1f0234,0x1f0238]:put(a,0)
put(0x1f023c,I(12,'t0','t2',65535))
# Text-size loop consumes one complete UTF-8 character before the shared width lookup.
size_code=decoder('a1','t9');size_va=0x5fedc0
put(0x1f2610,R(33,'s0','zero','a0'));put(0x1f2614,0x0c000000|(size_va>>2));put(0x1f2618,0)
# Wrapping loop keeps its byte count on a character boundary.
wrap=decoder('a1','v1');wrap=wrap[:-8]+struct.pack('<I',R(33,'s0','zero','a0'))+wrap[-8:];wrap_va=0x5feE80
put(0x1f1fc4,0x0c000000|(wrap_va>>2));put(0x1f1fc8,0)
# Safely append inside the existing executable segment; stay below the fixed MDI base.
phoff=struct.unpack_from('<I',old,28)[0];ph=phoff+32;typ,fo,va,pa,filesz,memsz,flags,align=struct.unpack_from('<8I',old,ph);assert filesz==memsz
end=(wrap_va+len(wrap)+15)&~15;assert 0x08804000+end<0x08e03020;extra=end-va-filesz;at=fo+filesz;payload=bytearray(extra)
for a,code in [(size_va,size_code),(wrap_va,wrap)]:payload[a-va-filesz:a-va-filesz+len(code)]=code
# Preserve original relocation records and append new JAL records to the text relocation section.
shoff=struct.unpack_from('<I',old,32)[0];entsize,count=struct.unpack_from('<HH',old,46);relocations=[(0x1f1704,4),(0x1f2614,4),(0x1f1fc4,4)]
new[at:at]=payload;struct.pack_into('<8I',new,ph,typ,fo,va,pa,end-va,end-va,flags,align);struct.pack_into('<I',new,32,shoff+extra)
for i in range(count):
 o=shoff+extra+i*entsize;v=struct.unpack_from('<I',new,o+16)[0]
 if v>=at:struct.pack_into('<I',new,o+16,v+extra)
# Extend the text relocation section without repurposing a live record.
current_shoff=struct.unpack_from('<I',new,32)[0];text_section=current_shoff+2*entsize;rel_start,rel_size=struct.unpack_from('<II',new,text_section+16);rel_at=rel_start+rel_size;rel_payload=b''.join(struct.pack('<II',*r) for r in relocations);new[rel_at:rel_at]=rel_payload;new_shoff=current_shoff+(len(rel_payload) if current_shoff>=rel_at else 0);struct.pack_into('<I',new,32,new_shoff)
for i in range(count):
 o=new_shoff+i*entsize;v=struct.unpack_from('<I',new,o+16)[0]
 if v>=rel_at:struct.pack_into('<I',new,o+16,v+len(rel_payload))
struct.pack_into('<I',new,new_shoff+2*entsize+20,rel_size+len(rel_payload))
assert not dst.exists();shutil.copy2(src,dst);b.append_iso_file_and_repoint(dst,path,bytes(new));assert b.iso_read_file(dst,path)[1]==bytes(new)
out=Path('outputs/stage43m');out.mkdir(exist_ok=True);(out/'size_decoder.bin').write_bytes(size_code);(out/'wrap_decoder.bin').write_bytes(wrap);(out/'patched.prx').write_bytes(new);r={'test_iso':str(dst),'patches':edits,'size_helper_va':hex(size_va),'wrap_helper_va':hex(wrap_va),'module_end':hex(0x08804000+end),'mdi_base':'0x08e03020','added_relocations':[hex(x[0]) for x in relocations],'iso_readback_verified':True,'runtime_verified':False};(out/'objective_patch_report.json').write_text(json.dumps(r,indent=2));print(json.dumps({k:v for k,v in r.items() if k!='patches'}))


