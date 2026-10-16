import importlib.util,struct,json,shutil,hashlib
from pathlib import Path
s=importlib.util.spec_from_file_location('m','PROJECT_ROOT/bia_stage40i_tools/bia_stage40i_actual_resource_trace.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);_,b=m.load_helpers()
src=Path('PROJECT_ROOT/BIA_STEP114_MENU_COMPLETION_KO_TEST.iso');dst=Path('PROJECT_ROOT/BIA_STEP115_FONT_UV_INSET_TEST.iso');assert not dst.exists();shutil.copy2(src,dst);report=[]
names=[x['mdi'] for x in json.loads(Path('outputs/step098/inventory.json').read_text())]+['ON_MEMU_O.MDI']
for name in names:
 _,blob=b.iso_read_file(src,['PSP_GAME','USRDIR','SYSTEM',name]);st={x['index']:bytes(x['decoded']) for x in b.parse_mdi(blob)};si=23 if name=='ON_MEMU_O.MDI' else 35;old=st[si];d=bytearray(old);n=0
 for j in range(151,907):
  off=j*24
  if off+24>len(d):break
  cp=struct.unpack_from('<H',old,off)[0]
  if not(0xac00<=cp<=0xd7a3 or cp in (0x2018,0x2019)):continue
  u,v,u1,v1=struct.unpack_from('<4f',old,off+8)
  if abs((u1-u)*128-17)>.001 or abs((v1-v)*256-16)>.001:continue
  struct.pack_into('<2f',d,off+16,u1-1/128,v1-1/256);n+=1
 assert n>=696,(name,n)
 # Exactly the last two UV coordinates change; metadata sizes and all atlas pixels remain identical.
 new=b.rebuild_mdi(blob,{si:bytes(d)});check={x['index']:bytes(x['decoded']) for x in b.parse_mdi(new)};assert all(check[i]==(bytes(d) if i==si else z) for i,z in st.items());assert len(d)==len(old)
 b.append_iso_file_and_repoint(dst,['PSP_GAME','USRDIR','SYSTEM',name],new);assert b.iso_read_file(dst,['PSP_GAME','USRDIR','SYSTEM',name])[1]==new
 report.append({'mdi':name,'glyphs':n,'stream':si});print(name,n,flush=True)
for name in ['BIAOFF.PRX','BIAON.PRX','ON_MEMU.DSL','ON_MEMU.DSX']:
 assert b.iso_read_file(src,['PSP_GAME','USRDIR','SYSTEM',name])[1]==b.iso_read_file(dst,['PSP_GAME','USRDIR','SYSTEM',name])[1]
Path('outputs/step115_font/build_report.json').write_text(json.dumps({'source':str(src),'output':str(dst),'resources':report,'glyphs':sum(x['glyphs'] for x in report),'atlas_pixels_unchanged':True,'advances_and_line_height_unchanged':True,'decoded_stream_lengths_unchanged':True,'prx_unchanged':True,'iso_readback_verified':True,'runtime_visual_validation':False},indent=2));print('DONE',dst)
