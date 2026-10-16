import importlib.util,struct,json
from pathlib import Path
s=importlib.util.spec_from_file_location('m','PROJECT_ROOT/bia_stage40i_tools/bia_stage40i_actual_resource_trace.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);_,b=m.load_helpers();_,blob=b.iso_read_file(Path('PROJECT_ROOT/BIA_STAGE43O_RESTART_LIFETIME_TEST.iso'),['PSP_GAME','USRDIR','SYSTEM','D0_0130_.MDI']);st={x['index']:bytes(x['decoded']) for x in b.parse_mdi(blob)}
for si,off in [(3,0x58c80),(26,0x59aa0)]:
 print('Font',si,hex(off));print([(hex(i),hex(struct.unpack_from('<I',st[si],off+i)[0])) for i in range(0x28,0x80,4)])
Path('outputs/stage43p_probe/atlas_swizzled.bin').write_bytes(st[34][:131072])
plan=json.loads(Path('PROJECT_ROOT/bia_stage39a_tools/stage39a_font_plan.json').read_text(encoding='utf-8'))['layout'];print([x for x in plan if x['codepoint'] in map(ord,'모드시점자유')])
