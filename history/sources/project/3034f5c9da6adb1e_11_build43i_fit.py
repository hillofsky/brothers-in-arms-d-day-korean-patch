import importlib.util,json,struct,shutil,csv,re,collections
from pathlib import Path
s=importlib.util.spec_from_file_location('m','PROJECT_ROOT/bia_stage40i_tools/bia_stage40i_actual_resource_trace.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);_,b=m.load_helpers()
src=Path('PROJECT_ROOT/BIA_STAGE43H_CAMPAIGN_ALL_TEXT_FONTS_TEST.iso');dst=Path('PROJECT_ROOT/BIA_STAGE43I_CAMPAIGN_HINT_FIT_TEST.iso');parts=['PSP_GAME','USRDIR','SYSTEM','D0_0130_.MDI'];_,blob=b.iso_read_file(src,parts);st={x['index']:bytes(x['decoded']) for x in b.parse_mdi(blob)};mu={i:bytearray(d) for i,d in st.items()};base=0x08e03020;stride=0x78000
p=Path('work/campaign_first_ko.json');tr=json.loads(p.read_text(encoding='utf-8'));old=tr['BIA-01454'];new='나침반 %icon_compass_arrow%는 다음 목표 방향을 가리킨다.';assert collections.Counter(re.findall(r'%[^%]+%',old))==collections.Counter(re.findall(r'%[^%]+%',new));raw=new.encode('utf-8')+b'\0';actions=json.loads(Path('outputs/stage43a/campaign_actions.json').read_text(encoding='utf-8'));changed=[]
for a in actions:
 if a['id']!='BIA-01454':continue
 i=a['stream'];o=int(a['offset'],16);ptr,n,cap=struct.unpack_from('<III',st[i],o);j,k=divmod(ptr-base,stride);assert st[j][k:k+n]==old.encode('utf-8')+b'\0' and len(raw)<=n;mu[j][k:k+n]=raw+bytes(n-len(raw));struct.pack_into('<III',mu[i],o,ptr,len(raw),len(raw));changed.append({'stream':i,'offset':hex(o),'pointer':hex(ptr)})
assert len(changed)==5
patched=b.rebuild_mdi(blob,{i:bytes(d) for i,d in mu.items() if bytes(d)!=st[i]});assert not dst.exists();shutil.copy2(src,dst);b.append_iso_file_and_repoint(dst,parts,patched);assert b.iso_read_file(dst,parts)[1]==patched
tr['BIA-01454']=new;p.write_text(json.dumps(tr,ensure_ascii=False,indent=2),encoding='utf-8');out=Path('outputs/stage43i');out.mkdir(exist_ok=True);r={'test_iso':str(dst),'id':'BIA-01454','before':old,'after':new,'updated_references':changed,'control_tokens_preserved':True,'iso_readback_verified':True,'runtime_verified':False};(out/'hint_fit_report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
rows=json.loads(Path('work/first_campaign_units.json').read_text(encoding='utf-8'))
with (out/'campaign_first_mission_ko.tsv').open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.DictWriter(f,list(rows[0]),delimiter='\t');w.writeheader();w.writerows({**row,'한국어':tr[row['id']]} for row in rows)
s=Path('work/stage43h_live.py').read_text(encoding='utf-8').replace('stage43h_validation','stage43i_validation').replace('nav43h_command','nav43i_command').replace('BIA_STAGE43H_CAMPAIGN_ALL_TEXT_FONTS_TEST.iso','BIA_STAGE43I_CAMPAIGN_HINT_FIT_TEST.iso');Path('work/stage43i_live.py').write_text(s,encoding='utf-8');print(json.dumps(r,ensure_ascii=True))
