import json,struct
from pathlib import Path
out=Path('outputs/stage40k');ram=(out/'controls_ram.bin').read_bytes();base=0x08000000
read=lambda p,n:ram[p-base:p-base+n]
r={}
for font in [0x0972385c,0x0972524c]:
 data=read(font,0x4a0);(out/(hex(font)+'_font.bin')).write_bytes(data);count=struct.unpack_from('<H',data,0x50)[0];ptr=struct.unpack_from('<I',data,0x54)[0]
 r[hex(font)]={'count':count,'glyph_ptr':hex(ptr)}
 for off in [0x474,0x478,0x488]:
  p=struct.unpack_from('<I',data,off)[0];r[hex(font)][hex(off)]={'ptr':hex(p),'data':read(p,16).hex()}
 for ch in ['A','유','형','조','준','반','전','보']:
  cp=ord(ch);page=struct.unpack_from('<I',data,0x58+(cp>>8)*4)[0];gi=struct.unpack('<H',read(page+(cp&255)*2,2))[0] if page else None
  r[hex(font)][ch]={'page':hex(page),'glyph_index':gi,'glyph':read(ptr+gi*24,24).hex() if gi is not None else None}
 (out/(hex(font)+'_glyphs.bin')).write_bytes(read(ptr,count*24))
(out/'font_comparison.json').write_text(json.dumps(r,ensure_ascii=False,indent=2));print(json.dumps(r,ensure_ascii=False))
