from pathlib import Path
import struct,json
old=Path('outputs/stage43o/patched.prx').read_bytes();new=Path('outputs/stage43q/patched.prx').read_bytes();oh=struct.unpack_from('<I',old,32)[0];nh=struct.unpack_from('<I',new,32)[0];en,n=struct.unpack_from('<HH',old,46);edits={int(a,16) for a in json.loads(Path('outputs/stage43q/patch_report.json').read_text())['hooks']};preserved=0
for i in range(n):
 a=struct.unpack_from('<10I',old,oh+i*en);z=struct.unpack_from('<10I',new,nh+i*en);assert a[:4]==z[:4] and a[6:]==z[6:]
 if a[1]==8 or not a[5]:continue
 x=old[a[4]:a[4]+a[5]];y=new[z[4]:z[4]+z[5]]
 if i==2:assert y[:len(x)]==x and len(y)==len(x)+24
 else:
  assert len(y)==len(x)
  for o,(b,c) in enumerate(zip(x,y)):
   if b!=c:assert (a[4]+o-0x80)&~3 in edits
  preserved+=1
assert old[0x5fef40+0x80:0x5fef64+0x80]==new[0x5fef40+0x80:0x5fef64+0x80]
Path('outputs/stage43q/elf_integrity_test.json').write_text(json.dumps({'section_headers_verified':n,'payloads_verified_except_relocation_extension':preserved,'existing_relocation_bytes_preserved':True,'new_relocation_records':3,'chapter_restart_helper_unchanged':True},indent=2));print('ELF PASS',n,preserved)
