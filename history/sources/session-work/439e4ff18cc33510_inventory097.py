import importlib.util,struct,json
from pathlib import Path
s=importlib.util.spec_from_file_location('m','PROJECT_ROOT/bia_stage40i_tools/bia_stage40i_actual_resource_trace.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);_,b=m.load_helpers();iso=Path('PROJECT_ROOT/BIA_STAGE79_COMPILED967_STRUCTURAL_TEST.iso');_,blob=b.iso_read_file(iso,['PSP_GAME','USRDIR','SYSTEM','D0_0700_.MDI']);st={x['index']:bytes(x['decoded']) for x in b.parse_mdi(blob)};base=0x08e03020;stride=0x78000
for a in [0x09a74150,0x08fc3ca0,0x09a69a90]:
 i,o=divmod(a-base,stride);d=st[i];print(hex(a),i,hex(o),d[o:o+0x80].hex());print([hex(x) for x in struct.unpack_from('<14I',d,o+0x28)])
for i in [34,35]:print('stream',i,'nonzero_end',hex(max(j for j,x in enumerate(st[i]) if x)))
Path('outputs/step097').mkdir(exist_ok=True);Path('outputs/step097/mission2.mdi').write_bytes(blob)
