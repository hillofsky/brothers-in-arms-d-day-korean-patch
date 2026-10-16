import importlib.util,struct,json,hashlib,shutil
from pathlib import Path
s=importlib.util.spec_from_file_location('m','PROJECT_ROOT/bia_stage40i_tools/bia_stage40i_actual_resource_trace.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);_,b=m.load_helpers();src=Path('outputs/step110/BIA_STEP110_PAUSE_MENU_KO_TEST.iso').resolve();dst=Path('PROJECT_ROOT/BIA_STEP111_RADIO_SUBTITLE_KO_TEST.iso');out=Path('outputs/step111');inv=json.loads((out/'repack_inventory.json').read_text());assert not dst.exists();assert shutil.disk_usage(dst.parent).free>inv['estimated_size']+40*1024*1024;hashes=[]
with src.open('rb') as f,dst.open('w+b') as z:
 prefix=bytearray(f.read(inv['prefix']));assert len(prefix)==inv['prefix'];assert prefix[17*2048]==255,'additional volume descriptors require separate directory handling';z.write(prefix);cursor=inv['prefix']
 for rec in inv['files']:
  f.seek(rec['extent']*2048);z.seek(cursor);left=rec['size'];h=hashlib.sha256()
  while left:
   data=f.read(min(left,1024*1024));assert data;z.write(data);h.update(data);left-=len(data)
  start=cursor//2048;cursor=((cursor+rec['size']+2047)//2048)*2048;off=rec['record_offset'];struct.pack_into('<I',prefix,off+2,start);struct.pack_into('>I',prefix,off+6,start);hashes.append({'path':rec['path'],'extent':start,'size':rec['size'],'sha256':h.hexdigest()})
 z.truncate(cursor);struct.pack_into('<I',prefix,16*2048+80,cursor//2048);struct.pack_into('>I',prefix,16*2048+84,cursor//2048);z.seek(0);z.write(prefix)
# Verify every active file's bytes and both directory extent fields after repacking.
with dst.open('rb') as f:
 for rec in hashes:
  found=b.iso_find_record(dst,rec['path']);assert found['extent']==rec['extent'] and found['size']==rec['size'];f.seek(found['extent']*2048);left=found['size'];h=hashlib.sha256()
  while left:
   data=f.read(min(left,1024*1024));assert data;h.update(data);left-=len(data)
  assert h.hexdigest()==rec['sha256'],rec['path']
(out/'repack_check.json').write_text(json.dumps({'source':str(src),'output':str(dst),'files_verified':len(hashes),'file_contents_preserved':True,'compact_iso_size':dst.stat().st_size,'files':hashes},indent=2));print('REPACK VERIFIED',len(hashes),'files',dst.stat().st_size,flush=True)
p=Path('work/build110_pause.py').read_text(encoding='utf-8-sig');a=p.index('src=Path(');e=p.index(';dst=',a);p=p[:a]+"src=Path('"+str(src).replace('\\','/')+"')"+p[e:];a=p.index('dst=Path(');e=p.index(';out=',a);p=p[:a]+"dst=Path('PROJECT_ROOT/BIA_STEP111_RADIO_SUBTITLE_KO_TEST.iso')"+p[e:];p=p.replace('outputs/step110','outputs/step111').replace("'STEP110'","'STEP111'").replace('0x44000','0x45000').replace('assert not dst.exists()','assert dst.exists()').replace('shutil.copy2(src,dst);','');Path('work/build111_radio.py').write_text(p,encoding='utf-8')
