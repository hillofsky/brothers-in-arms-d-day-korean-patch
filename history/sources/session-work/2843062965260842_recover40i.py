import importlib.util,json,csv,zipfile
from pathlib import Path
p=Path(r'PROJECT_ROOT\bia_stage40i_tools\bia_stage40i_actual_resource_trace.py')
s=importlib.util.spec_from_file_location('trace40i',p); m=importlib.util.module_from_spec(s); s.loader.exec_module(m)
files=m.iso_inventory(m.SOURCE_ISO)
rows=m.parse_lbn_log(m.PPSSPP_LOG,files)
out=Path('outputs/stage40i_recovered'); out.mkdir(parents=True,exist_ok=True)
m.write_tsv(out/'stage40i_lbn_map.tsv',rows,['lbn','logged_size','logged_size_dec','iso_file','iso_file_size','size_matches'])
r=json.loads(m.REPORT_PATH.read_text(encoding='utf-8'))
r['recovery']={'postprocessing_completed':True,'runtime_rerun':False,'original_exception':r.get('exception'),'lbn_records':len(rows),'unmatched_lbn_records':sum(not x['iso_file'] for x in rows),'note':'Recovered existing trace; screen navigation and absence of probes do not establish that remaining entries are unused.'}
(out/'stage40i_recovered_report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
for f in m.OUT.iterdir():
 if f.is_file() and f.name!='FAILURE.txt': (out/f.name).write_bytes(f.read_bytes())
with zipfile.ZipFile('outputs/bia_stage40i_recovered.zip','w',zipfile.ZIP_DEFLATED) as z:
 for f in out.iterdir(): z.write(f,f.name)
print(json.dumps(r['recovery']))
for x in rows: print(x)
