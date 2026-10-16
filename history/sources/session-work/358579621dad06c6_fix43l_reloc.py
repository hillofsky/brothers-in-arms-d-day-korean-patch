from pathlib import Path
p=Path('work/build43l_popup.py');s=p.read_text(encoding='utf-8-sig');start=s.index('free=[]');end=s.index('new[at:at]=payload;');s=s[:start]+"relocations=[(0x1f1704,4),(0x1f2614,4),(0x1f1fc4,4)]\n"+s[end:];start=s.index('assert not dst.exists()');s=s[:start]+'''# Extend the text relocation section without repurposing a live record.
current_shoff=struct.unpack_from('<I',new,32)[0];text_section=current_shoff+2*entsize;rel_start,rel_size=struct.unpack_from('<II',new,text_section+16);rel_at=rel_start+rel_size;rel_payload=b''.join(struct.pack('<II',*r) for r in relocations);new[rel_at:rel_at]=rel_payload;new_shoff=current_shoff+len(rel_payload);struct.pack_into('<I',new,32,new_shoff)
for i in range(count):
 o=new_shoff+i*entsize;v=struct.unpack_from('<I',new,o+16)[0]
 if v>=rel_at:struct.pack_into('<I',new,o+16,v+len(rel_payload))
struct.pack_into('<I',new,new_shoff+2*entsize+20,rel_size+len(rel_payload))
'''+s[start:];s=s.replace("'added_relocations':[hex(x) for x in free[:3]]","'added_relocations':[hex(x[0]) for x in relocations]");p.write_text(s,encoding='utf-8')
