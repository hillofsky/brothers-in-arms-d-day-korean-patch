import importlib.util,struct,json,shutil,hashlib
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
s=importlib.util.spec_from_file_location('m','PROJECT_ROOT/bia_stage40i_tools/bia_stage40i_actual_resource_trace.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);_,b=m.load_helpers();src=Path('PROJECT_ROOT/BIA_STEP117_NEW_OBJECTIVE_KO_TEST.iso');dst=Path('PROJECT_ROOT/BIA_STEP118_FONT_GUTTER_TEST.iso');assert not dst.exists();shutil.copy2(src,dst);font=ImageFont.truetype('LOCAL_PATH',14);report=[]
names=[x['mdi'] for x in json.loads(Path('outputs/step098/inventory.json').read_text())]+['ON_MEMU_O.MDI'];out=Path('outputs/step118_font')
for name in names:
 _,blob=b.iso_read_file(src,['PSP_GAME','USRDIR','SYSTEM',name]);st={x['index']:bytes(x['decoded']) for x in b.parse_mdi(blob)};mi,ai=(23,22) if name=='ON_MEMU_O.MDI' else (35,34);cells=[]
 for j in range(151,907):
  cp=struct.unpack_from('<H',st[mi],j*24)[0]
  if not 0xac00<=cp<=0xd7a3:continue
  u,v,u1,v1=struct.unpack_from('<4f',st[mi],j*24+8)
  if abs((u1-u)*128-16)>.001 or abs((v1-v)*256-15)>.001:continue
  x=round(u*128-.5);y=round(v*256-.5);assert 0<=x<=495 and 0<=y<=496;cells.append((cp,x,y))
 assert len(cells)>=696
 atlas=bytearray(st[ai]);allowed=set()
 for cp,x,y in cells:
  im=Image.new('L',(17,16),0);dr=ImageDraw.Draw(im);box=font.getbbox(chr(cp));w,h=box[2]-box[0],box[3]-box[1];assert w<=15 and h<=14;dr.text(((17-w)//2-box[0],(16-h)//2-box[1]),chr(cp),font=font,fill=255);p=im.load();assert all(p[xx,yy]==0 for xx in range(17) for yy in range(16) if xx in [0,16] or yy in [0,15])
  for yy in range(16):
   for xx in range(17):
    gx,gy=x+xx,y+yy;bx=gx//2;o=(gy//8)*2048+(bx//16)*128+(gy%8)*16+bx%16;sh=4*(gx%2);val=(p[xx,yy]+8)//17;mask=15<<sh;atlas[o]=(atlas[o]&~mask)|(val<<sh);allowed.add((o,sh))
 for o,(a,z) in enumerate(zip(st[ai],atlas)):
  if a!=z:
   assert ((a^z)&15)==0 or (o,0) in allowed
   assert ((a^z)&240)==0 or (o,4) in allowed
 new=b.rebuild_mdi(blob,{ai:bytes(atlas)});decoded={x['index']:bytes(x['decoded']) for x in b.parse_mdi(new)};assert all(decoded[i]==(bytes(atlas) if i==ai else v) for i,v in st.items());b.append_iso_file_and_repoint(dst,['PSP_GAME','USRDIR','SYSTEM',name],new);assert b.iso_read_file(dst,['PSP_GAME','USRDIR','SYSTEM',name])[1]==new;report.append({'mdi':name,'hangul_cells':len(cells),'transparent_border_verified':True});print(name,len(cells),flush=True)
for name in ['BIAOFF.PRX','BIAON.PRX','ON_MEMU.DSL','ON_MEMU.DSX']:
 assert b.iso_read_file(src,['PSP_GAME','USRDIR','SYSTEM',name])[1]==b.iso_read_file(dst,['PSP_GAME','USRDIR','SYSTEM',name])[1]
(out/'build_report.json').write_text(json.dumps({'output':str(dst),'source':str(src),'resources':report,'raster_font_size':14,'previous_size':16,'minimum_clear_border_pixels':1,'latin_and_icon_pixels_unchanged':True,'all_metadata_metrics_and_uv_unchanged':True,'iso_readback_verified':True,'runtime_visual_validation':False},indent=2));print('DONE',dst)
