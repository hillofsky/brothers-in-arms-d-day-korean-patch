import importlib.util,json,hashlib
from pathlib import Path
s=importlib.util.spec_from_file_location('m','PROJECT_ROOT/bia_stage40i_tools/bia_stage40i_actual_resource_trace.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);_,b=m.load_helpers();src=Path('PROJECT_ROOT/BIA_STAGE79_COMPILED967_STRUCTURAL_TEST.iso');dst=Path('PROJECT_ROOT/BIA_STEP097_MISSION2_UFONT_TEST.iso');parts=['PSP_GAME','USRDIR','SYSTEM'];files=['BIAOFF.PRX','BIAON.PRX','D0_0130_.MDI','D0_0130_.DSL','D0_0130_.DSX','D0_0700_.DSL','D0_0700_.DSX','ON_MEMU_O.MDI','ON_MEMU.DSL','ON_MEMU.DSX'];report={}
for f in files:
 a=b.iso_read_file(src,parts+[f])[1];z=b.iso_read_file(dst,parts+[f])[1];assert a==z;report[f]=hashlib.sha256(z).hexdigest()
a={x['index']:bytes(x['decoded']) for x in b.parse_mdi(b.iso_read_file(src,parts+['D0_0700_.MDI'])[1])};z={x['index']:bytes(x['decoded']) for x in b.parse_mdi(b.iso_read_file(dst,parts+['D0_0700_.MDI'])[1])};assert a[34]==z[34];changed={i for i in a if a[i]!=z[i]};assert changed=={3,26,35}
# Existing font object bytes outside the eleven metadata fields are unchanged.
for i,o in [(3,0x58c80),(26,0x41130)]:
 expected=bytearray(a[i]);expected[o+0x28:o+0x54]=z[i][o+0x28:o+0x54];assert expected==z[i]
# All preexisting text payloads and RFont metadata remain byte-identical.
assert a[35][:0x17000]==z[35][:0x17000]
Path('outputs/step097/integrity_check.json').write_text(json.dumps({'unchanged_files_sha256':report,'changed_mission_streams':sorted(changed),'original_native_font_object_fields_preserved':True,'latin_glyph_bytes_preserved':True,'existing_strings_and_rfont_metadata_preserved':True,'atlas_pixels_preserved':True},indent=2));print('INTEGRITY VERIFIED')
