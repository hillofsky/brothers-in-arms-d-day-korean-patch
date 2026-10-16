import importlib.util,json,re,hashlib
from pathlib import Path
s=importlib.util.spec_from_file_location('m','PROJECT_ROOT/bia_stage40i_tools/bia_stage40i_actual_resource_trace.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);_,b=m.load_helpers();iso=Path('PROJECT_ROOT/BIA_STEP123_SKIRMISH_KO_TEST.iso');out=Path('outputs/step123');inter=json.loads((out/'targets.json').read_text(encoding='utf-8'));alltext=inter;rec=b.iso_find_record(iso,['PSP_GAME','USRDIR','SYSTEM'])
with iso.open('rb') as f:names=[r['name'] for r in b.iso_list_dir(f,rec['extent'],rec['size']) if r['name'].endswith('.INT')]
reports=[]
for name in names:
 parts=['PSP_GAME','USRDIR','SYSTEM',name];_,old=b.iso_read_file(iso,parts);lines=old.splitlines(keepends=True);count=0
 for j,line in enumerate(lines):
  raw=line.rstrip(b'\r\n')
  if b'=' not in raw:continue
  key,val=raw.split(b'=',1)
  try:en=val.strip().strip(b'"').decode('utf-8')
  except UnicodeDecodeError:
   try:en=val.strip().strip(b'"').decode('cp1252')
   except UnicodeDecodeError:continue
  ko=alltext.get(en)
  if ko is None:continue
  # Exact display value; never replace class/section identifiers or resource paths.
  if en in inter and key.decode('ascii',errors='ignore') in ['Class','ObjectName','Name','Name4UMD','Name4PC','Name4PSP']:continue
  quotes=b'"' if val.strip().startswith(b'"') else b'';eol=b'\r\n' if line.endswith(b'\r\n') else b'\n';lines[j]=key+b'='+quotes+ko.encode('utf-8')+quotes+eol;count+=1
 if count:
  new=b''.join(lines);b.append_iso_file_and_repoint(iso,parts,new);assert b.iso_read_file(iso,parts)[1]==new;reports.append({'file':name,'display_values_translated':count})
(out/'fallback_translation_check.json').write_text(json.dumps(reports,indent=2));print('FALLBACK FILES',len(reports),'VALUES',sum(x['display_values_translated'] for x in reports))
