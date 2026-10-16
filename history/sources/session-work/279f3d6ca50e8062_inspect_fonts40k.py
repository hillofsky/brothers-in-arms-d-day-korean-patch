import importlib.util,json,struct,base64
from pathlib import Path
s=importlib.util.spec_from_file_location('m','PROJECT_ROOT/bia_stage40i_tools/bia_stage40i_actual_resource_trace.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);_,b=m.load_helpers();out=Path('outputs/stage40k');ws,_=b.connect_debugger(int((out/'debugger_port.txt').read_text()))
r={}
try:
 for font in [0x0972385c,0x0972524c]:
  data=m.read_ws(ws,font,0x4a0);(out/(hex(font)+'_font.bin')).write_bytes(data)
  count=struct.unpack_from('<H',data,0x50)[0];ptr=struct.unpack_from('<I',data,0x54)[0]
  r[hex(font)]={'count':count,'glyph_ptr':hex(ptr),'widths_ptr':hex(struct.unpack_from('<I',data,0x474)[0]),'heights_ptr':hex(struct.unpack_from('<I',data,0x478)[0]),'texptrs_ptr':hex(struct.unpack_from('<I',data,0x488)[0])}
  for off in [0x474,0x478,0x488]:
   p=struct.unpack_from('<I',data,off)[0];r[hex(font)][hex(off)]=m.read_ws(ws,p,16).hex()
  (out/(hex(font)+'_glyphs.bin')).write_bytes(m.read_ws(ws,ptr,count*16))
 (out/'font_comparison.json').write_text(json.dumps(r,indent=2));print(json.dumps(r))
finally:ws.close()
