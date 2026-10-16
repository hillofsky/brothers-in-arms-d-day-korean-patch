import importlib.util,struct,json,csv,re
from pathlib import Path
s=importlib.util.spec_from_file_location('m','PROJECT_ROOT/bia_stage40i_tools/bia_stage40i_actual_resource_trace.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);_,b=m.load_helpers();src=Path('PROJECT_ROOT/BIA_STEP097_MISSION2_UFONT_TEST.iso');rows=list(csv.DictReader(Path('PROJECT_ROOT/log/STEP_079/outputs/mdi_build_report.tsv').open(encoding='utf-8-sig'),delimiter='\t'));base=0x08e03020;stride=0x78000;reports=[]
for row in rows:
 name=row['mdi'];_,blob=b.iso_read_file(src,['PSP_GAME','USRDIR','SYSTEM',name]);st={x['index']:bytes(x['decoded']) for x in b.parse_mdi(blob)};fonts=[]
 for i,d in st.items():
  for hit in re.finditer(re.escape(struct.pack('<I',0x08d68be8)),d):
   o=hit.start()
   if o%4 or o+0x64>len(d):continue
   gp,n,cap,tp,tn,tc,rp,rn,rc,bp,bn=struct.unpack_from('<11I',d,o+0x28)
   if not (n==cap==rn==rc and 1<=n<=2000 and tn==tc and 1<=tn<=4 and bn in [8,1024]):continue
   fonts.append({'runtime':hex(base+i*stride+o),'stream':i,'offset':hex(o),'glyph_count':n,'texture_array':hex(tp),'glyphs':hex(gp),'remap':hex(rp)})
 reports.append({'mdi':name,'fonts':fonts,'native_font_counts':[f['glyph_count'] for f in fonts],'rfont_mode':row['font_mode'],'metadata_used_end':hex(max(j for j,x in enumerate(st[35]) if x))})
 print(name,[f['glyph_count'] for f in fonts])
out=Path('outputs/step098');out.mkdir(exist_ok=True);(out/'inventory.json').write_text(json.dumps(reports,indent=2));print('TOTAL',len(reports),sum(len(r['fonts']) for r in reports))
