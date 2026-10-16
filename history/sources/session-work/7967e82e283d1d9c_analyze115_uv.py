import importlib.util,struct,json
from pathlib import Path
s=importlib.util.spec_from_file_location('m','PROJECT_ROOT/bia_stage40i_tools/bia_stage40i_actual_resource_trace.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);_,b=m.load_helpers()
_,blob=b.iso_read_file(Path('PROJECT_ROOT/BIA_STEP114_MENU_COMPLETION_KO_TEST.iso'),['PSP_GAME','USRDIR','SYSTEM','ON_MEMU_O.MDI']);st={x['index']:bytes(x['decoded']) for x in b.parse_mdi(blob)};atlas=st[22][:0x20000];records=st[23];rows=[]
def pixel(x,y):
 if not(0<=x<512 and 0<=y<512):return 0
 bx=x//2;o=(y//8)*2048+(bx//16)*128+(y%8)*16+bx%16;return(atlas[o]>>(4*(x%2)))&15
for j in range(151,847):
 cp=struct.unpack_from('<H',records,j*24)[0];u,v,u1,v1=struct.unpack_from('<4f',records,j*24+8);x=round(u*128-.5);y=round(v*256-.5)
 rows.append({'char':chr(cp),'x':x,'y':y,'sample_right':u1*128,'cell_right_pixel_center':x+16.5,'sample_bottom':v1*256,'cell_bottom_pixel_center':y+15.5,'right_neighbor_nonzero':sum(pixel(x+17,yy)>0 for yy in range(y,min(y+16,512))),'bottom_neighbor_nonzero':sum(pixel(xx,y+16)>0 for xx in range(x,min(x+17,512)))})
out=Path('outputs/step115_font');out.mkdir(exist_ok=True);result={'font_glyphs_analyzed':len(rows),'right_endpoint_outside_cell':sum(z['sample_right']>z['cell_right_pixel_center']+.01 for z in rows),'bottom_endpoint_outside_cell':sum(z['sample_bottom']>z['cell_bottom_pixel_center']+.01 for z in rows),'glyphs_with_nonzero_adjacent_pixels':sum(z['right_neighbor_nonzero']+z['bottom_neighbor_nonzero']>0 for z in rows),'glyphs':rows};(out/'menu_uv_analysis.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print({k:v for k,v in result.items() if k!='glyphs'});print([z for z in rows if z['char'] in '스토리프로필뒤로'])
