from pathlib import Path
import importlib.util,json,csv,shutil,hashlib
root=Path(r'PROJECT_ROOT');assets=root/'stage42h_local';assets.mkdir(exist_ok=True)
sp=importlib.util.spec_from_file_location('iso',root/'stage42g/build_stage42g.py');m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
j=json.loads((root/'stage42g/stage42g_token_dictionary.json').read_text(encoding='utf-8'))
rows=list(csv.DictReader((root/'translation/stage42b/movie_subtitles_ko.tsv').open(encoding='utf-8-sig'),delimiter='\t'))
lookup={t['key']:t['text'] for t in j['tokens']};lookup[92]='\\'
assert len(j['all_fields'])==len(rows)==133
source=root/'BIA_STAGE42G_FIX19_PERSISTENT_512_TEST.iso';dest=root/'BIA_STAGE42H_ALL8_MOVIES_512_TEST.iso'
if dest.exists():raise FileExistsError(dest)
iso=m.ISO(source);nodes={n['name']:(p,n) for p,n in iso.walk() if not n['dir']};patches={};field_reports=[]
try:
 for row,f in zip(rows,j['all_fields']):
  assert row['file']==f['file'] and int(row['field_index'])==f['field_index'] and row['korean']==f['korean']
  name=f['file'];p,n=nodes[name]
  if name not in patches:
   old=iso.read(n['extent']*2048,n['size']);patches[name]={'path':p,'node':n,'original':old,'patched':bytearray(old)}
  a=patches[name];off=int(f['offset_hex'],16);sz=f['field_bytes'];old=a['original'][off:off+sz]
  assert len(old)==sz and old[-1:]==b'^',(name,f['field_index'])
  enc=bytes.fromhex(f['encoded_hex']);assert len(enc)<=sz-1
  assert ''.join(lookup[c] for c in enc)==f['korean']
  assert old[:-1].rstrip(b' ') in (row['english'].encode('ascii'),enc),(name,f['field_index'],'source mismatch')
  new=enc.ljust(sz-1,b' ')+b'^';a['patched'][off:off+sz]=new
  field_reports.append({'file':name,'field':f['field_index'],'offset':hex(off),'budget':sz-1,'used':len(enc),'roundtrip':True})
 for name,a in patches.items():
  # Only original text field slices may change; control bytes and timing remain exact.
  allowed=set()
  for f in j['all_fields']:
   if f['file']==name:allowed.update(range(int(f['offset_hex'],16),int(f['offset_hex'],16)+f['field_bytes']-1))
  assert len(a['original'])==len(a['patched'])
  assert all(i in allowed for i,(x,y) in enumerate(zip(a['original'],a['patched'])) if x!=y)
  (assets/name).write_bytes(a['patched'])
 for name,asset in [('SUBTITLEHASHMAP.INI','SUBTITLEHASHMAP_42G.INI'),('SUBTITLETEXTURE.RAW','SUBTITLETEXTURE_42G_512.RAW')]:
  p,n=nodes[name];old=iso.read(n['extent']*2048,n['size']);new=(root/'stage42g'/asset).read_bytes();assert len(new)==len(old)
  patches[name]={'path':p,'node':n,'original':old,'patched':new}
finally:iso.close()
shutil.copyfile(source,dest);iso=m.ISO(dest);report=[]
try:
 for name,a in patches.items():
  n=a['node'];new=bytes(a['patched']);iso.write(n['extent']*2048,new);assert iso.read(n['extent']*2048,len(new))==new
  report.append({'file':name,'path':a['path'],'size':len(new),'before_sha1':hashlib.sha1(a['original']).hexdigest(),'after_sha1':hashlib.sha1(new).hexdigest()})
finally:iso.close()
rep={'stage':'42H_LOCAL','source':str(source),'output':str(dest),'subtitle_files':8,'fields':133,'field_verification':field_reports,'patches':report,'static_verified':True,'runtime_verified':False,'full_campaign_verified':False}
(assets/'stage42h_build_report.json').write_text(json.dumps(rep,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'files':8,'fields':133,'output':str(dest),'static_verified':True}))
