exec(open('work/audit111_radio.py',encoding='utf-8-sig').read().split('allrefs=[]')[0]);files=[];dirs=[]
with src.open('rb') as f:
 root=b.iso_read_record(f,16*2048+156)
 def walk(rec,path):
  dirs.append(rec)
  for r in b.iso_list_dir(f,rec['extent'],rec['size']):
   if r['name'] in ['.','..']:continue
   if r['flags']&2:walk(r,path+[r['name']])
   else:files.append({'path':path+[r['name']],**r})
 walk(root,[]);prefix=max((d['extent']*2048+d['size']+2047)//2048 for d in dirs)*2048;size=prefix+sum((r['size']+2047)//2048*2048 for r in files);print('prefix',prefix,'files',len(files),'compact bytes',size)
Path('outputs/step111/repack_inventory.json').write_text(json.dumps({'prefix':prefix,'files':files,'dirs':dirs,'estimated_size':size},indent=2))
