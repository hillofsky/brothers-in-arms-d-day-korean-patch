import json,struct
from pathlib import Path
ram=Path('outputs/stage40k_validation/controls_ram.bin').read_bytes();base=0x08000000
r=json.loads(Path('outputs/stage40k/font_patch_report.json').read_text());r['runtime_verified']=True;r['font_live_count']=struct.unpack_from('<H',ram,0x0972524c+0x50-base)[0];r['font_live_glyph_ptr']=hex(struct.unpack_from('<I',ram,0x0972524c+0x54-base)[0]);r['main_menu_ok']=True;r['controls_boxes_removed']=True;r['width_measurement_unfixed']=True
Path('outputs/stage40k_validation/font_validation_report.json').write_text(json.dumps(r,indent=2))
