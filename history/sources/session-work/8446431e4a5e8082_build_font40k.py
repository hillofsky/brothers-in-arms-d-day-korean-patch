import importlib.util,struct,json,shutil,hashlib
from pathlib import Path
s=importlib.util.spec_from_file_location('m','PROJECT_ROOT/bia_stage40i_tools/bia_stage40i_actual_resource_trace.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);_,b=m.load_helpers()
source=Path('PROJECT_ROOT/BIA_STAGE40J_LOCALIZATION_KEYS_RESTORED_TEST.iso');target=Path('PROJECT_ROOT/BIA_STAGE40K_CONTROLS_FONT_TEST.iso');out=Path('outputs/stage40k');parts=b.TARGET_MDI
_,blob=b.iso_read_file(source,parts);st={x['index']:bytes(x['decoded']) for x in b.parse_mdi(blob)}
main=0x0972385c-b.STREAM19_RAM_BASE;body=0x0972524c-b.STREAM19_RAM_BASE;d=bytearray(st[19]);assert struct.unpack_from('<H',d,main+0x50)[0]==847;assert struct.unpack_from('<H',d,body+0x50)[0]==151
ranges=[(0x50,0x458),(0x474,0x47c),(0x488,0x48c)]
changes=[]
for lo,hi in ranges:
 before=bytes(d[body+lo:body+hi]); after=bytes(d[main+lo:main+hi]);d[body+lo:body+hi]=after;changes.append({'offset':hex(lo),'size':hi-lo,'before_sha1':hashlib.sha1(before).hexdigest(),'after_sha1':hashlib.sha1(after).hexdigest()})
patched=b.rebuild_mdi(blob,{19:bytes(d)});check={x['index']:bytes(x['decoded']) for x in b.parse_mdi(patched)};assert check[19]==bytes(d);assert all(check[i]==v for i,v in st.items() if i!=19)
assert not target.exists();shutil.copy2(source,target);b.append_iso_file_and_repoint(target,parts,patched);assert b.iso_read_file(target,parts)[1]==patched
r={'source_iso':str(source),'test_iso':str(target),'font':hex(0x0972524c),'font_count_before':151,'font_count_after':847,'shared_with':hex(0x0972385c),'changed_ranges':changes,'all_other_streams_unchanged':True,'iso_readback_ok':True,'latin_glyph_style_note':'The controls font now shares the production font glyphs and atlas; font object layout/scaling fields are unchanged.','runtime_verified':False};(out/'font_patch_report.json').write_text(json.dumps(r,indent=2));print(json.dumps(r))
