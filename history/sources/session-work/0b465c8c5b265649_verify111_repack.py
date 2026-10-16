import json,hashlib,importlib.util
from pathlib import Path
s=importlib.util.spec_from_file_location('m','PROJECT_ROOT/bia_stage40i_tools/bia_stage40i_actual_resource_trace.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);_,b=m.load_helpers();out=Path('outputs/step111');r=json.loads((out/'build_report.json').read_text(encoding='utf-8'));prior=json.loads((out/'repack_check.json').read_text(encoding='utf-8'));expected={x['mdi']:x['mdi_sha256'] for x in r['maps']};iso=Path(r['output'])
with iso.open('rb') as f:
 for item in prior['files']:
  found=b.iso_find_record(iso,item['path']);f.seek(found['extent']*2048);left=found['size'];h=hashlib.sha256()
  while left:
   raw=f.read(min(left,1024*1024));assert raw;h.update(raw);left-=len(raw)
  assert h.hexdigest()==expected.get(item['path'][-1],item['sha256']),item['path']
r['all_1147_active_files_verified_after_repack_and_patch']=True;r['iso_size_bytes']=iso.stat().st_size;r['default_output_directory']='PROJECT_ROOT';(out/'build_report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8');print('ALL 1147 FILES VERIFIED; OUTPUT',iso)

