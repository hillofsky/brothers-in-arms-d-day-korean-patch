import importlib.util,csv,struct,json,re,shutil
from pathlib import Path
s=importlib.util.spec_from_file_location('m',r'PROJECT_ROOT\bia_stage40i_tools\bia_stage40i_actual_resource_trace.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);_,b=m.load_helpers()
parts='PSP_GAME/USRDIR/SYSTEM/ON_MEMU_O.MDI'.split('/')
_,orig=b.iso_read_file(Path(r'PROJECT_ROOT\BIA_STAGE39U_BOOT_RENDER_UTF8_TEST.iso'),parts); _,mass=b.iso_read_file(m.SOURCE_ISO,parts)
a={x['index']:bytes(x['decoded']) for x in b.parse_mdi(orig)}; c={x['index']:bytes(x['decoded']) for x in b.parse_mdi(mass)}
base=0x08e2d020; stride=0x78000
keys=set()
for p in Path(r'PROJECT_ROOT\extracted\PSP_GAME\USRDIR\SYSTEM').glob('*.INT'):
 for line in p.read_text(encoding='cp1252',errors='replace').splitlines():
  if '=' in line: keys.add(line.split('=',1)[0].strip())
rows=list(csv.DictReader(open(r'PROJECT_ROOT\bia_stage40g_tools\stage40g_on_memu_plan.tsv',encoding='utf-8-sig'),delimiter='\t'))
restored=[]; dst=bytearray(c[16])
for r in rows:
 si=int(r['source_stream']); off=int(r['source_offset'],0); mi=int(r['metadata_stream']); mo=int(r['metadata_offset'],0); eng=r['english']
 if si!=11 or mi!=16 or not (0x44000<=mo<0x46000) or eng not in keys or not re.fullmatch('[A-Z][A-Z0-9_]*',eng): continue
 p,n,cap=struct.unpack_from('<III',a[16],mo+12); vi=(p-base)//stride; vo=(p-base)%stride
 val=a.get(vi,b'')[vo:vo+n]
 if not (1<n<300 and val.endswith(b'\0') and all(32<=x<127 for x in val[:-1])):continue
 assert a[si][off:off+len(eng)+1]==eng.encode()+b'\0'
 dst[mo:mo+12]=a[16][mo:mo+12]; restored.append({'key':eng,'value':val[:-1].decode(),'metadata_offset':hex(mo),'source_offset':hex(off)})
assert {'GAME','TYPE'}.issubset({r['key'] for r in restored})
blob=b.rebuild_mdi(mass,{16:bytes(dst)}); check={x['index']:bytes(x['decoded']) for x in b.parse_mdi(blob)}
assert check[16]==bytes(dst)
assert all(check[i]==d for i,d in c.items() if i!=16)
target=Path(r'PROJECT_ROOT\BIA_STAGE40J_LOCALIZATION_KEYS_RESTORED_TEST.iso'); assert not target.exists(); shutil.copy2(m.SOURCE_ISO,target); b.append_iso_file_and_repoint(target,parts,blob); assert b.iso_read_file(target,parts)[1]==blob
report={'test_iso':str(target),'restored_keys':restored,'restored_count':len(restored),'only_stream16_changed':True,'iso_readback_ok':True,'runtime_verified':False}
Path('outputs/stage40j/key_restore_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(report,ensure_ascii=False))
