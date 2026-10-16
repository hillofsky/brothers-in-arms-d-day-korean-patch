import importlib.util,struct,json
from pathlib import Path
s=importlib.util.spec_from_file_location('m','PROJECT_ROOT/bia_stage40i_tools/bia_stage40i_actual_resource_trace.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);_,b=m.load_helpers();_,blob=b.iso_read_file(Path('PROJECT_ROOT/BIA_STAGE43I_CAMPAIGN_HINT_FIT_TEST.iso'),['PSP_GAME','USRDIR','SYSTEM','D0_0130_.MDI']);st={x['index']:bytes(x['decoded']) for x in b.parse_mdi(blob)};base=0x08e03020;stride=0x78000
found=[]
for i,d in st.items():
 for o in range(0,len(d)-0x58,4):
  gp,n,c,tp,tn,tc,rp,rn,rc,bp,bn=struct.unpack_from('<11I',d,o+0x28)
  if not(10<=n<=1200 and n<=c<=2048 and 1<=tn<=4 and tn<=tc<=8 and 10<=rn<=n and rn<=rc<=2048 and 1<=bn<=2048):continue
  if not all(base<=v<base+len(st)*stride for v in [gp,tp,rp,bp]):continue
  j,k=divmod(gp-base,stride)
  if j not in st or k+n*20>len(st[j]):continue
  a=struct.unpack_from('<4IB3x',st[j],k);a2=struct.unpack_from('<4IB3x',st[j],k+20)
  if not all(v<=512 for v in a[:4]+a2[:4]) or a[4]>=tn or a2[4]>=tn:continue
  found.append({'address':hex(base+i*stride+o),'stream':i,'offset':hex(o),'class':hex(struct.unpack_from('<I',d,o)[0]),'glyphs':n,'capacity':c,'rect0':a,'rect1':a2})
print(json.dumps(found));Path('outputs/stage43k_trace/font_inventory_relaxed.json').write_text(json.dumps(found,indent=2))
