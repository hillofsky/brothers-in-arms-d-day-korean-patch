import importlib.util,struct,json,re
from pathlib import Path
s=importlib.util.spec_from_file_location('m','PROJECT_ROOT/bia_stage40i_tools/bia_stage40i_actual_resource_trace.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);_,b=m.load_helpers();src=Path('PROJECT_ROOT/BIA_STEP099_COMPLETION_SAVE_KO_TEST.iso');_,blob=b.iso_read_file(src,['PSP_GAME','USRDIR','SYSTEM','D1_0900_.MDI']);st={x['index']:bytes(x['decoded']) for x in b.parse_mdi(blob)};base=0x08e03020;stride=0x78000;hits=[]
for i,d in st.items():
 for h in re.finditer(b'ton\0',d):
  o=h.start();start=o
  while start>0 and 32<=d[start-1]<=126:start-=1
  print('STRING',i,hex(o),repr(d[start:o+4]))
  ptr=base+i*stride+o
  for j,t in st.items():
   for r in re.finditer(re.escape(struct.pack('<I',ptr)),t):
    k=r.start()
    if k%4==0 and k+12<=len(t):print('REF',j,hex(k),struct.unpack_from('<III',t,k))
# All applied localized mission dialogue values, including ending lines.
for p in [Path('PROJECT_ROOT/log/STEP_079/outputs/compiled967_patch_refs.tsv')]:
 import csv
 rows=list(csv.DictReader(p.open(encoding='utf-8-sig'),delimiter='\t'))
 for r in rows:
  if r['mdi']=='D1_0900_.MDI' and any(w in r['english'] for w in ['Risner:','Mac:','Allen:','Garnett:']):print('DIALOGUE',r['english'],r['korean'])
