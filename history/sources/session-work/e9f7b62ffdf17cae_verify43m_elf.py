from pathlib import Path
import struct,json,importlib.util
s=importlib.util.spec_from_file_location('m','PROJECT_ROOT/bia_stage40i_tools/bia_stage40i_actual_resource_trace.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);_,b=m.load_helpers();_,old=b.iso_read_file(Path('PROJECT_ROOT/BIA_STAGE43I_CAMPAIGN_HINT_FIT_TEST.iso'),['PSP_GAME','USRDIR','SYSTEM','BIAOFF.PRX']);new=Path('outputs/stage43m/patched.prx').read_bytes()
def sections(d):
 o=struct.unpack_from('<I',d,32)[0];z,n=struct.unpack_from('<HH',d,46);return [struct.unpack_from('<10I',d,o+i*z) for i in range(n)]
orig=sections(old);dest=sections(new);assert len(orig)==len(dest)==52 and not any(dest[0]);preserved=0
for i,(a,z) in enumerate(zip(orig,dest)):
 assert all(a[k]==z[k] for k in [0,1,2,3,6,7,8,9]);assert z[5]==a[5]+(24 if i==2 else 0)
 if a[1] in [0,8]:continue
 assert z[4]+z[5]<=len(new)
 if i==1:continue
 assert old[a[4]:a[4]+a[5]]==new[z[4]:z[4]+a[5]],i;preserved+=1
assert new[dest[2][4]+orig[2][5]:dest[2][4]+dest[2][5]]==b''.join(struct.pack('<II',v,4) for v in [0x1f1704,0x1f2614,0x1f1fc4])
Path('outputs/stage43m/elf_integrity_test.json').write_text(json.dumps({'section_headers_verified':52,'unchanged_section_payloads':preserved,'original_relocations_preserved':True,'new_jal_relocations_verified':3},indent=2));print('ELF headers 52, preserved payloads',preserved)
for name in ['width','decoders']:
 t=Path('work/test43l_'+name+'.py').read_text().replace('STAGE43L','STAGE43M').replace('stage43l','stage43m');Path('work/test43m_'+name+'.py').write_text(t)
s=Path('work/stage43l_live.py').read_text().replace('STAGE43L','STAGE43M').replace('stage43l','stage43m').replace('nav43l','nav43m');Path('work/stage43m_live.py').write_text(s)
s=Path('work/nav43l_auto.py').read_text().replace('stage43l','stage43m').replace('nav43l','nav43m');Path('work/nav43m_auto.py').write_text(s)
