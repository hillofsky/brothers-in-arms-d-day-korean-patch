import importlib.util,struct,json,shutil,hashlib
from pathlib import Path
s=importlib.util.spec_from_file_location('m','PROJECT_ROOT/bia_stage40i_tools/bia_stage40i_actual_resource_trace.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);_,b=m.load_helpers();src=Path('PROJECT_ROOT/BIA_STEP105_MORTAR_PICKUP_KO_TEST.iso');dst=Path('outputs/step106_fix/BIA_STEP106_FONT_RENDER_OWNER_TEST.iso').resolve();out=Path('outputs/step106_fix');out.mkdir(exist_ok=True);assert not dst.exists();shutil.copy2(src,dst);rows=[];base=0x08e03020;stride=0x78000;meta=base+35*stride;clone=meta+0x17200;descriptor=meta+0x17400
for item in json.loads(Path('outputs/step098/inventory.json').read_text()):
 name=item['mdi'];parts=['PSP_GAME','USRDIR','SYSTEM',name];_,blob=b.iso_read_file(src,parts);st={e['index']:bytes(e['decoded']) for e in b.parse_mdi(blob)};d=bytearray(st[35]);assert not any(d[0x17400:0x17420]);assert struct.unpack_from('<I',d,0x17200)[0]==0x08d70f48
 # FTexture: vtable, padding, 64-bit cache ID, owning UTexture, revision.
 # Dedicated fixed descriptor owns the clone, independent of the donor's disposable render interface.
 cache_id=(clone<<8)|0xe0;payload=struct.pack('<IIQII',0x08d70ea0,0,cache_id,clone,1);d[0x17400:0x17400+24]=payload;oldptr=struct.unpack_from('<I',d,0x172e0)[0];struct.pack_into('<I',d,0x172e0,descriptor)
 rebuilt=b.rebuild_mdi(blob,{35:bytes(d)});b.append_iso_file_and_repoint(dst,parts,rebuilt);check={e['index']:bytes(e['decoded']) for e in b.parse_mdi(b.iso_read_file(dst,parts)[1])};assert check[35]==bytes(d) and all(check[i]==v for i,v in st.items() if i!=35);rows.append({'mdi':name,'previous_render_interface':hex(oldptr),'descriptor':hex(descriptor),'owner':hex(clone),'cache_id':hex(cache_id)});print(name,flush=True)
for f in ['BIAOFF.PRX','BIAON.PRX','MEMORYSTICK.INT','ON_MEMU_O.MDI']:
 parts=['PSP_GAME','USRDIR','SYSTEM',f];assert b.iso_read_file(src,parts)[1]==b.iso_read_file(dst,parts)[1]
(out/'build_report.json').write_text(json.dumps({'source':str(src),'output':str(dst),'maps':rows,'only_clone_render_pointer_and_empty_descriptor_space_changed':True,'atlas_glyphs_translations_prx_unchanged':True,'iso_readback_verified':True,'runtime_verified':False,'output_sha256':hashlib.file_digest(dst.open('rb'),'sha256').hexdigest()},indent=2));print('BUILT',dst)

