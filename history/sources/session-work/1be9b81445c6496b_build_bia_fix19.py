from pathlib import Path
import importlib.util,struct,json,shutil,argparse
ap=argparse.ArgumentParser();ap.add_argument('--source',required=True);ap.add_argument('--output',required=True);ap.add_argument('--report',required=True);a=ap.parse_args()
sp=importlib.util.spec_from_file_location('base',r'PROJECT_ROOT\stage42g_fix3\build_stage42g_fix3.py');m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
src=Path(a.source);dst=Path(a.output);assert src.resolve()!=dst.resolve()
if dst.exists():raise FileExistsError(dst)
shutil.copyfile(src,dst);iso=m.ISO(dst);hits=[]
try:
 for name,node in iso.walk():
  if node['dir'] or not (name.upper().endswith('.PRX') or node['name'].upper() in ('BOOT.BIN','EBOOT.BIN')):continue
  data=iso.read(node['extent']*2048,node['size'])
  for off in m.all_occurrences(data,m.OLD_SIG):hits.append((name,node,data,off))
 assert {x[0] for x in hits}=={'/PSP_GAME/USRDIR/SYSTEM/BIAOFF.PRX','/PSP_GAME/USRDIR/SYSTEM/BIAON.PRX','/PSP_GAME/SYSDIR/BOOT.BIN'} and len(hits)==3
 report=[]
 for name,node,data,off in hits:
  new=bytearray(data);struct.pack_into('<II',new,off,m.NEW_H,m.NEW_W)
  iso.write(node['extent']*2048,new);assert iso.read(node['extent']*2048,len(new))==new
  report.append({'path':name,'offset':hex(off),'old_sha1':m.sha1(data),'new_sha1':m.sha1(new),'words':['34060200','34070200']})
 Path(a.report).write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report))
finally:iso.close()
